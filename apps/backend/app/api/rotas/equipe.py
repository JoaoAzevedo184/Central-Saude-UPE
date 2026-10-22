"""Área da equipe: filas do escopo, painel ordenado, classificação, critérios, agenda do dia,
presença (UC-008) e painel de vagas.

Toda consulta filtra por `fila_id IN escopo` dentro da query (ADR-025); fila ou solicitação
fora do escopo responde 404. Leitura: ATENDENTE, GESTOR e ADMIN. Escrita: só ATENDENTE.
As consultas ao painel e ao detalhe são auditadas (AM-007), sem nome, CPF nem respostas.
"""

import logging
from datetime import date, datetime, time, timedelta
from typing import Annotated, Any, Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select, true
from sqlalchemy.orm import Session

from app.api.deps import escopo_da_equipe, exige_papel, get_relogio, get_session, ip_do_cliente
from app.api.paginacao import Limit, Offset, Pagina
from app.api.problemas import CSRF, NAO_AUTENTICADO, SEM_PERMISSAO, erros
from app.api.tipos import (
    ClassificacaoRisco,
    OrigemCriterio,
    SituacaoVaga,
    StatusAgendamento,
    StatusSolicitacao,
    TipoCriterio,
    TipoEventoLinhaDoTempo,
    Turno,
)
from app.config import get_settings
from app.dominio.agendamento.estados import registrar_presenca
from app.dominio.agendamento.vagas import situacao_da_vaga
from app.dominio.cadastro import abreviar_nome, mascarar_cpf
from app.dominio.erros import EntradaInvalida
from app.dominio.fila.criterios import ORIGENS_DA_EQUIPE, calcular_nota, pontuar_respostas
from app.dominio.relogio import Relogio
from app.dominio.solicitacao import classificar as classificar_solicitacao
from app.dominio.solicitacao import (
    exigir_aceita_respostas,
    recalcular_nota,
    registrar_atendimento,
    registrar_falta,
)
from app.dominio.vocabulario import STATUS_SOLICITACAO
from app.infra.agendamentos import (
    ATIVOS,
    aplicar_agendamento,
    para_dominio_agendamento,
    travar_agendamento,
)
from app.infra.modelos import (
    Agenda,
    Agendamento,
    Auditoria,
    CriterioFila,
    Especialidade,
    Fila,
    HistoricoSolicitacao,
    Paciente,
    RespostaCriterio,
    Solicitacao,
    Unidade,
    Usuario,
    Vaga,
)
from app.infra.solicitacoes import (
    TIPOS_MUDANCA_DE_POSICAO,
    criterios_da_fila,
    gravar_transicao,
    ordem_da_fila,
    para_dominio,
    posicoes_na_fila,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/equipe", tags=["equipe"])

LeitorDep = Annotated[Usuario, Depends(exige_papel("ATENDENTE", "GESTOR", "ADMIN"))]
AtendenteDep = Annotated[Usuario, Depends(exige_papel("ATENDENTE"))]
EscopoDep = Annotated[frozenset[UUID], Depends(escopo_da_equipe)]
SessionDep = Annotated[Session, Depends(get_session)]
RelogioDep = Annotated[Relogio, Depends(get_relogio)]
# Limites evitam OverflowError em `data + 1 dia` (9999-12-31 viraria 500).
Dia = Annotated[date, Query(ge=date(2000, 1, 1), le=date(2100, 12, 31))]

# Erros comuns: sessão (401), papel (403) e, nas escritas, CSRF (403). Fora do escopo é 404.
EQUIPE_LEITURA = (NAO_AUTENTICADO, SEM_PERMISSAO, 422)
EQUIPE_ESCRITA = (*EQUIPE_LEITURA, CSRF)


# --- schemas ------------------------------------------------------------------------------


class FilaEquipeSaida(BaseModel):
    id: UUID
    nome: str
    unidade_sigla: str
    especialidade: str
    ativa: bool
    contagem_por_status: dict[StatusSolicitacao, int]


class UltimaMudanca(BaseModel):
    """Sem motivo: texto livre da reclassificação fica só no detalhe, que é auditado."""

    tipo: TipoEventoLinhaDoTempo
    ocorrido_em: datetime


class ItemPainel(BaseModel):
    id: UUID
    status: StatusSolicitacao
    posicao: int | None  # só NA_FILA; calculada na consulta, nunca gravada
    classificacao_risco: ClassificacaoRisco | None
    nota: int
    data_entrada_fila: datetime | None
    paciente_nome: str  # abreviado
    paciente_cpf: str  # mascarado
    ultima_mudanca: UltimaMudanca | None


class PainelSaida(Pagina[ItemPainel]):
    pass


class PaginaFilasEquipe(Pagina[FilaEquipeSaida]):
    pass


class RespostaEquipeSaida(BaseModel):
    criterio_id: UUID
    codigo: str
    descricao: str
    origem: OrigemCriterio
    valor: Any
    pontos: int


class EventoEquipe(BaseModel):
    tipo: TipoEventoLinhaDoTempo
    status_anterior: StatusSolicitacao | None
    status_novo: StatusSolicitacao | None
    motivo: str | None
    visivel_paciente: bool
    ator_usuario_id: UUID | None
    ocorrido_em: datetime


class SolicitacaoEquipeSaida(BaseModel):
    id: UUID
    status: StatusSolicitacao
    fila_id: UUID
    paciente_nome: str
    paciente_cpf: str
    classificacao_risco: ClassificacaoRisco | None
    nota: int
    data_entrada_fila: datetime | None
    data_pedido: date
    turno_preferido: Turno
    origem_encaminhamento: str | None
    respostas: list[RespostaEquipeSaida]
    historico: list[EventoEquipe]


class ClassificacaoEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, use_enum_values=True)

    classificacao_risco: ClassificacaoRisco
    motivo: str | None = Field(default=None, min_length=3, max_length=500)


class RespostaEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    criterio_id: UUID
    valor: bool | int | float | Annotated[str, Field(max_length=200)]


class RespostasEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    respostas: list[RespostaEntrada] = Field(min_length=1, max_length=50)


class FaixaCriterio(BaseModel):
    """Faixa de um critério `NUMERO` (limites inclusivos e opcionais). Sem o fator: o peso fica
    com o protocolo."""

    min: float | None = None
    max: float | None = None


class CriterioEquipeSaida(BaseModel):
    """Pergunta que a equipe responde para montar o formulário. Sem peso, fator nem pontos."""

    id: UUID
    codigo: str
    descricao: str
    tipo: TipoCriterio
    origem: Literal["REGULACAO", "EQUIPE"]
    opcoes: list[str] | None  # só OPCAO
    faixas: list[FaixaCriterio] | None  # só NUMERO


class AgendamentoDoDia(BaseModel):
    id: UUID
    solicitacao_id: UUID
    inicio: datetime
    fim: datetime
    profissional: str
    paciente_nome: str  # abreviado
    status: StatusAgendamento
    presenca_registrada: bool


class PresencaEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    compareceu: bool


class VagaPainel(BaseModel):
    id: UUID
    inicio: datetime
    fim: datetime
    profissional: str
    situacao: SituacaoVaga


class PainelVagasSaida(BaseModel):
    total: int
    sem_proposta: int  # livres sem janela para propor: candidatas a encaixe manual (ADR-021)
    itens: list[VagaPainel]


# --- apoio --------------------------------------------------------------------------------


def _auditar_leitura(
    session: Session,
    usuario: Usuario,
    request: Request,
    acao: str,
    entidade: str,
    entidade_id: UUID,
    filtros: dict[str, Any] | None = None,
) -> None:
    session.add(
        Auditoria(
            ator_usuario_id=usuario.id,
            acao=acao,
            entidade=entidade,
            entidade_id=entidade_id,
            dados_depois=filtros,
            ip=ip_do_cliente(request),
        )
    )
    session.commit()


def _travar(session: Session, solicitacao_id: UUID, escopo: frozenset[UUID]) -> Solicitacao:
    s = session.scalar(
        select(Solicitacao)
        .where(Solicitacao.id == solicitacao_id, Solicitacao.fila_id.in_(escopo))
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if s is None:
        raise HTTPException(404, "Solicitação não encontrada.")
    return s


def _detalhe(
    session: Session, solicitacao_id: UUID, escopo: frozenset[UUID]
) -> SolicitacaoEquipeSaida:
    linha = session.execute(
        select(Solicitacao, Paciente.nome, Paciente.cpf)
        .join(Paciente, Paciente.id == Solicitacao.paciente_id)
        .where(Solicitacao.id == solicitacao_id, Solicitacao.fila_id.in_(escopo))
    ).one_or_none()
    if linha is None:
        raise HTTPException(404, "Solicitação não encontrada.")
    s, nome, cpf = linha
    respostas = session.execute(
        select(RespostaCriterio, CriterioFila)
        .join(CriterioFila, CriterioFila.id == RespostaCriterio.criterio_id)
        .where(RespostaCriterio.solicitacao_id == s.id)
        .order_by(CriterioFila.codigo)
    )
    historico = session.scalars(
        select(HistoricoSolicitacao)
        .where(HistoricoSolicitacao.solicitacao_id == s.id)
        .order_by(HistoricoSolicitacao.ocorrido_em, HistoricoSolicitacao.seq)
    )
    return SolicitacaoEquipeSaida(
        id=s.id,
        status=s.status,
        fila_id=s.fila_id,
        paciente_nome=nome,
        paciente_cpf=mascarar_cpf(cpf),
        classificacao_risco=s.classificacao_risco,
        nota=s.nota,
        data_entrada_fila=s.data_entrada_fila,
        data_pedido=s.data_pedido,
        turno_preferido=s.turno_preferido,
        origem_encaminhamento=s.origem_encaminhamento,
        respostas=[
            RespostaEquipeSaida(
                criterio_id=c.id,
                codigo=c.codigo,
                descricao=c.descricao,
                origem=c.origem,
                valor=r.valor,
                pontos=r.pontos,
            )
            for r, c in respostas
        ],
        historico=[
            EventoEquipe(
                tipo=h.tipo,
                status_anterior=h.status_anterior,
                status_novo=h.status_novo,
                motivo=h.motivo,
                visivel_paciente=h.visivel_paciente,
                ator_usuario_id=h.ator_usuario_id,
                ocorrido_em=h.ocorrido_em,
            )
            for h in historico
        ],
    )


# --- leitura ------------------------------------------------------------------------------


@router.get("/filas", responses=erros(*EQUIPE_LEITURA))
def listar_filas(
    _: LeitorDep, escopo: EscopoDep, session: SessionDep, limit: Limit = 50, offset: Offset = 0
) -> PaginaFilasEquipe:
    """Filas do escopo, com a contagem de solicitações por status."""
    linhas = session.execute(
        select(Fila, Unidade.sigla, Especialidade.nome)
        .join(Unidade, Unidade.id == Fila.unidade_id)
        .join(Especialidade, Especialidade.id == Fila.especialidade_id)
        .where(Fila.id.in_(escopo))
        .order_by(Unidade.sigla, Fila.nome, Fila.id)
        .limit(limit)
        .offset(offset)
    ).all()
    contagens: dict[UUID, dict[str, int]] = {
        f.id: dict.fromkeys(STATUS_SOLICITACAO, 0) for f, *_ in linhas
    }
    for fila_id, status, n in session.execute(
        select(Solicitacao.fila_id, Solicitacao.status, func.count())
        .where(Solicitacao.fila_id.in_(contagens))
        .group_by(Solicitacao.fila_id, Solicitacao.status)
    ):
        contagens[fila_id][status] = n
    return PaginaFilasEquipe(
        total=session.scalar(select(func.count()).select_from(Fila).where(Fila.id.in_(escopo)))
        or 0,
        itens=[
            FilaEquipeSaida(
                id=f.id,
                nome=f.nome,
                unidade_sigla=sigla,
                especialidade=especialidade,
                ativa=f.ativa,
                contagem_por_status=contagens[f.id],
            )
            for f, sigla, especialidade in linhas
        ],
    )


@router.get("/filas/{fila_id}/solicitacoes", responses=erros(*EQUIPE_LEITURA, 404))
def painel(
    fila_id: UUID,
    request: Request,
    usuario: LeitorDep,
    escopo: EscopoDep,
    session: SessionDep,
    status: StatusSolicitacao | None = None,
    ordenacao: Literal["prioridade", "chegada"] = "prioridade",
    limit: Limit = 50,
    offset: Offset = 0,
) -> PainelSaida:
    """Painel da fila (RF-031, RF-032). A posição vem de `ROW_NUMBER()` sobre todas as
    solicitações NA_FILA da fila, antes da paginação, na ordem de `ordenar_fila()`."""
    if fila_id not in escopo:
        raise HTTPException(404, "Fila não encontrada.")
    posicoes = posicoes_na_fila(fila_id)
    ultima = (
        select(HistoricoSolicitacao.tipo, HistoricoSolicitacao.ocorrido_em)
        .where(
            HistoricoSolicitacao.solicitacao_id == Solicitacao.id,
            HistoricoSolicitacao.tipo.in_(TIPOS_MUDANCA_DE_POSICAO),
        )
        .order_by(HistoricoSolicitacao.ocorrido_em.desc(), HistoricoSolicitacao.seq.desc())
        .limit(1)
        .lateral()
    )
    filtros = [Solicitacao.fila_id == fila_id, Solicitacao.fila_id.in_(escopo)]
    if status:
        filtros.append(Solicitacao.status == status)
    ordem = (
        ordem_da_fila()
        if ordenacao == "prioridade"
        else [
            Solicitacao.data_entrada_fila.asc().nulls_last(),
            Solicitacao.criada_em,
            Solicitacao.id,
        ]
    )
    linhas = session.execute(
        select(
            Solicitacao,
            Paciente.nome,
            Paciente.cpf,
            posicoes.c.posicao,
            ultima.c.tipo,
            ultima.c.ocorrido_em,
        )
        .join(Paciente, Paciente.id == Solicitacao.paciente_id)
        .outerjoin(posicoes, posicoes.c.id == Solicitacao.id)
        .outerjoin(ultima, true())
        .where(*filtros)
        .order_by(*ordem)
        .limit(limit)
        .offset(offset)
    ).all()
    total = session.scalar(select(func.count()).select_from(Solicitacao).where(*filtros))
    _auditar_leitura(
        session,
        usuario,
        request,
        "CONSULTAR_PAINEL",
        "fila",
        fila_id,
        {"status": status, "ordenacao": ordenacao, "limit": limit, "offset": offset},
    )
    return PainelSaida(
        total=total or 0,
        itens=[
            ItemPainel(
                id=s.id,
                status=s.status,
                posicao=posicao,
                classificacao_risco=s.classificacao_risco,
                nota=s.nota,
                data_entrada_fila=s.data_entrada_fila,
                paciente_nome=abreviar_nome(nome),
                paciente_cpf=mascarar_cpf(cpf),
                ultima_mudanca=UltimaMudanca(tipo=tipo, ocorrido_em=quando) if tipo else None,
            )
            for s, nome, cpf, posicao, tipo, quando in linhas
        ],
    )


@router.get("/solicitacoes/{solicitacao_id}", responses=erros(*EQUIPE_LEITURA, 404))
def detalhar(
    solicitacao_id: UUID,
    request: Request,
    usuario: LeitorDep,
    escopo: EscopoDep,
    session: SessionDep,
) -> SolicitacaoEquipeSaida:
    """Detalhe com respostas (critério, valor, pontos), nota e histórico completo."""
    detalhe = _detalhe(session, solicitacao_id, escopo)
    _auditar_leitura(
        session, usuario, request, "CONSULTAR_SOLICITACAO", "solicitacao", solicitacao_id
    )
    return detalhe


@router.get("/filas/{fila_id}/criterios", responses=erros(*EQUIPE_LEITURA, 404))
def criterios_da_equipe(
    fila_id: UUID, _: LeitorDep, escopo: EscopoDep, session: SessionDep
) -> list[CriterioEquipeSaida]:
    """Critérios ativos de origem REGULACAO e EQUIPE da fila, para montar o formulário de
    `PUT /equipe/solicitacoes/{id}/respostas`. Sem peso, fator nem pontos: a matriz de acesso
    não os libera para a leitura da equipe. Sem auditoria: não traz dado de paciente."""
    if fila_id not in escopo:
        raise HTTPException(404, "Fila não encontrada.")
    criterios = session.scalars(
        select(CriterioFila)
        .where(
            CriterioFila.fila_id == fila_id,
            CriterioFila.ativo,
            CriterioFila.origem.in_(ORIGENS_DA_EQUIPE),
        )
        .order_by(CriterioFila.codigo)
    )
    return [
        CriterioEquipeSaida(
            id=c.id,
            codigo=c.codigo,
            descricao=c.descricao,
            tipo=c.tipo,
            origem=c.origem,
            opcoes=sorted(c.parametros.get("opcoes", {})) if c.tipo == "OPCAO" else None,
            faixas=(
                [FaixaCriterio(min=f.get("min"), max=f.get("max")) for f in c.parametros["faixas"]]
                if c.tipo == "NUMERO" and "faixas" in c.parametros
                else None
            ),
        )
        for c in criterios
    ]


# --- escrita (só ATENDENTE) ---------------------------------------------------------------


@router.post(
    "/solicitacoes/{solicitacao_id}/classificar",
    responses=erros(*EQUIPE_ESCRITA, 404, (409, "transicao-invalida")),
)
def classificar(
    solicitacao_id: UUID,
    dados: ClassificacaoEntrada,
    request: Request,
    atendente: AtendenteDep,
    escopo: EscopoDep,
    session: SessionDep,
    relogio: RelogioDep,
) -> SolicitacaoEquipeSaida:
    """Classificação de risco, simulando a regulação. EM_ANALISE → NA_FILA; em NA_FILA só
    reclassifica, com motivo obrigatório. Outros estados → 409."""
    s = _travar(session, solicitacao_id, escopo)
    primeira = s.status == "EM_ANALISE"
    nova, eventos = classificar_solicitacao(
        para_dominio(s), dados.classificacao_risco, dados.motivo, relogio.agora()
    )
    gravar_transicao(
        session,
        s,
        nova,
        eventos,
        ator_id=atendente.id,
        acao="CLASSIFICAR" if primeira else "RECLASSIFICAR",
        ip=ip_do_cliente(request),
        evento_outbox="SOLICITACAO_NA_FILA" if primeira else None,
    )
    session.commit()
    logger.info("solicitacao classificada: id=%s", s.id)
    return _detalhe(session, s.id, escopo)


@router.put(
    "/solicitacoes/{solicitacao_id}/respostas",
    responses=erros(*EQUIPE_ESCRITA, 404, (409, "transicao-invalida")),
)
def responder_criterios(
    solicitacao_id: UUID,
    dados: RespostasEntrada,
    request: Request,
    atendente: AtendenteDep,
    escopo: EscopoDep,
    session: SessionDep,
    relogio: RelogioDep,
) -> SolicitacaoEquipeSaida:
    """Critérios de origem REGULACAO ou EQUIPE; a nota é recalculada por `calcular_nota()`.
    Na fila, nota diferente grava RECLASSIFICADA (só equipe)."""
    s = _travar(session, solicitacao_id, escopo)
    exigir_aceita_respostas(para_dominio(s))  # estado de origem antes de validar a entrada
    criterios = criterios_da_fila(session, s.fila_id)
    novas = [(r.criterio_id, r.valor) for r in dados.respostas]
    pontos = pontuar_respostas(criterios, novas, ORIGENS_DA_EQUIPE)

    gravadas = {
        r.criterio_id: r
        for r in session.scalars(
            select(RespostaCriterio).where(RespostaCriterio.solicitacao_id == s.id)
        )
    }
    valores = {c: r.valor for c, r in gravadas.items() if c in criterios} | dict(novas)
    nota = calcular_nota((criterios[c], v) for c, v in valores.items())
    agora = relogio.agora()
    nova, evento = recalcular_nota(para_dominio(s), nota, agora)
    # RN-010: quais respostas mudaram, sem nome nem CPF.
    respostas_antes = {str(c): gravadas[c].valor if c in gravadas else None for c, _ in novas}

    for criterio_id, valor in novas:
        resposta = gravadas.get(criterio_id) or RespostaCriterio(
            solicitacao_id=s.id, criterio_id=criterio_id, fila_id=s.fila_id
        )
        resposta.valor = valor
        resposta.pontos = pontos[criterio_id]
        resposta.respondido_por_usuario_id = atendente.id
        resposta.respondido_em = agora
        session.add(resposta)
    gravar_transicao(
        session,
        s,
        nova,
        [evento] if evento else [],
        ator_id=atendente.id,
        acao="RESPONDER_CRITERIOS",
        ip=ip_do_cliente(request),
        auditoria_antes={"respostas": respostas_antes},
        auditoria_depois={"respostas": {str(c): v for c, v in novas}},
    )
    session.commit()
    logger.info("criterios respondidos: solicitacao=%s", s.id)
    return _detalhe(session, s.id, escopo)


# --- agenda do dia, presença e painel de vagas --------------------------------------------

# Agendamentos que aparecem na agenda do dia: os ativos e os já encerrados pela presença.
STATUS_NA_AGENDA = ("PROPOSTO", "CONFIRMADO", "REALIZADO", "FALTOU")
MAX_DIAS_PAINEL_VAGAS = 31


def _dia_local(dia: date, fuso: ZoneInfo) -> datetime:
    """Meia-noite de `dia` em Recife, como instante com fuso (ADR-008)."""
    return datetime.combine(dia, time(0), fuso)


@router.get("/filas/{fila_id}/agendamentos", responses=erros(*EQUIPE_LEITURA, 404))
def agendamentos_do_dia(
    fila_id: UUID,
    data: Dia,
    request: Request,
    usuario: LeitorDep,
    escopo: EscopoDep,
    session: SessionDep,
) -> list[AgendamentoDoDia]:
    """Agenda do dia (UC-008): hora, paciente abreviado, status e se a presença foi registrada.
    `data` é o dia em Recife. Leitura auditada."""
    if fila_id not in escopo:
        raise HTTPException(404, "Fila não encontrada.")
    fuso = ZoneInfo(get_settings().timezone_exibicao)
    linhas = session.execute(
        select(Agendamento, Vaga, Agenda.profissional, Paciente.nome)
        .join(Vaga, Vaga.id == Agendamento.vaga_id)
        .join(Agenda, Agenda.id == Vaga.agenda_id)
        .join(Solicitacao, Solicitacao.id == Agendamento.solicitacao_id)
        .join(Paciente, Paciente.id == Solicitacao.paciente_id)
        .where(
            Agenda.fila_id == fila_id,
            Agenda.fila_id.in_(escopo),
            Agendamento.status.in_(STATUS_NA_AGENDA),
            Vaga.inicio >= _dia_local(data, fuso),
            Vaga.inicio < _dia_local(data + timedelta(days=1), fuso),
        )
        .order_by(Vaga.inicio, Agendamento.id)
    ).all()
    itens = [
        AgendamentoDoDia(
            id=a.id,
            solicitacao_id=a.solicitacao_id,
            inicio=v.inicio.astimezone(fuso),
            fim=v.fim.astimezone(fuso),
            profissional=profissional,
            paciente_nome=abreviar_nome(nome),
            status=a.status,
            presenca_registrada=a.status in ("REALIZADO", "FALTOU"),
        )
        for a, v, profissional, nome in linhas
    ]
    _auditar_leitura(
        session,
        usuario,
        request,
        "CONSULTAR_AGENDAMENTOS",
        "fila",
        fila_id,
        {"data": data.isoformat()},
    )
    return itens


@router.post(
    "/agendamentos/{agendamento_id}/presenca",
    responses=erros(*EQUIPE_ESCRITA, 404, (409, "transicao-invalida", "tolerancia-nao-encerrada")),
)
def presenca(
    agendamento_id: UUID,
    dados: PresencaEntrada,
    request: Request,
    atendente: AtendenteDep,
    escopo: EscopoDep,
    session: SessionDep,
    relogio: RelogioDep,
) -> SolicitacaoEquipeSaida:
    """UC-008. Compareceu: a partir do início da vaga, REALIZADO e solicitação ATENDIDA.
    Faltou: só depois da tolerância (RN-013), FALTOU e solicitação no fim da fila (RN-014).
    Só de CONFIRMADO; fora do escopo → 404."""
    par = travar_agendamento(session, agendamento_id, Solicitacao.fila_id.in_(escopo))
    if par is None:
        raise HTTPException(404, "Agendamento não encontrado.")
    s, a = par
    inicio, tolerancia = session.execute(
        select(Vaga.inicio, Fila.tolerancia_atraso_min)
        .join(Agenda, Agenda.id == Vaga.agenda_id)
        .join(Fila, Fila.id == Agenda.fila_id)
        .where(Vaga.id == a.vaga_id)
    ).one()
    agora = relogio.agora()
    novo = registrar_presenca(
        para_dominio_agendamento(a), dados.compareceu, inicio, tolerancia, agora
    )
    if dados.compareceu:
        nova, evento = registrar_atendimento(para_dominio(s), agora)
        eventos, acao, outbox = [evento], "REGISTRAR_COMPARECIMENTO", "ATENDIMENTO_REGISTRADO"
    else:
        nova, eventos = registrar_falta(para_dominio(s), agora)
        acao, outbox = "REGISTRAR_FALTA", "FALTA_REGISTRADA"
    aplicar_agendamento(
        session, a, novo, ator_id=atendente.id, acao=acao, ip=ip_do_cliente(request)
    )
    gravar_transicao(
        session,
        s,
        nova,
        eventos,
        ator_id=atendente.id,
        acao=acao,
        ip=ip_do_cliente(request),
        evento_outbox=outbox,
        agendamento_id=a.id,
    )
    session.commit()
    logger.info("presenca registrada: agendamento=%s status=%s", a.id, a.status)
    return _detalhe(session, s.id, escopo)


@router.get("/filas/{fila_id}/vagas", responses=erros(*EQUIPE_LEITURA, 404))
def painel_de_vagas(
    fila_id: UUID,
    de: Dia,
    ate: Dia,
    request: Request,
    usuario: LeitorDep,
    escopo: EscopoDep,
    session: SessionDep,
    relogio: RelogioDep,
) -> PainelVagasSaida:
    """Vagas de `de` a `ate` (dias em Recife, inclusivos, até 31 dias) com a situação
    derivada por `situacao_da_vaga()`. Nada é gravado. Leitura auditada."""
    if fila_id not in escopo:
        raise HTTPException(404, "Fila não encontrada.")
    if ate < de or (ate - de).days >= MAX_DIAS_PAINEL_VAGAS:
        raise EntradaInvalida(f"Informe um período de 1 a {MAX_DIAS_PAINEL_VAGAS} dias.")
    cfg = get_settings()
    fuso = ZoneInfo(cfg.timezone_exibicao)
    agora = relogio.agora()
    fila = session.get(Fila, fila_id)
    ativo = (
        select(Agendamento.status)
        .where(Agendamento.vaga_id == Vaga.id, Agendamento.status.in_(ATIVOS))
        .scalar_subquery()
    )
    linhas = session.execute(
        select(Vaga, Agenda.profissional, ativo)
        .join(Agenda, Agenda.id == Vaga.agenda_id)
        .where(
            Agenda.fila_id == fila_id,
            Agenda.fila_id.in_(escopo),
            Vaga.inicio >= _dia_local(de, fuso),
            Vaga.inicio < _dia_local(ate + timedelta(days=1), fuso),
        )
        .order_by(Vaga.inicio, Vaga.id)
    ).all()
    itens = [
        VagaPainel(
            id=v.id,
            inicio=v.inicio.astimezone(fuso),
            fim=v.fim.astimezone(fuso),
            profissional=profissional,
            situacao=situacao_da_vaga(
                v.inicio,
                v.status_admin,
                status_ativo,
                agora,
                fila.prazo_confirmacao_horas,
                cfg.proposta_antecedencia_minima_horas,
                janela_minima_horas=cfg.proposta_janela_minima_horas,
            ),
        )
        for v, profissional, status_ativo in linhas
    ]
    _auditar_leitura(
        session,
        usuario,
        request,
        "CONSULTAR_VAGAS",
        "fila",
        fila_id,
        {"de": de.isoformat(), "ate": ate.isoformat()},
    )
    return PainelVagasSaida(
        total=len(itens),
        sem_proposta=sum(i.situacao == "LIVRE_SEM_PROPOSTA" for i in itens),
        itens=itens,
    )
