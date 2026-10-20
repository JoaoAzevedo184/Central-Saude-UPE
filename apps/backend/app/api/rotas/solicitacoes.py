"""Área do paciente: filas, solicitações (UC-002) e resposta à proposta (UC-004, UC-005).

ADR-007: nenhuma resposta daqui traz posição, tamanho da fila, nota, pontos, pesos,
classificação de risco nem `data_entrada_fila`. Toda consulta filtra pelo paciente da sessão
dentro da query; solicitação de outro paciente responde 404 (AM-001).
"""

import logging
from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import exists, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_relogio, get_session, ip_do_cliente, paciente_da_sessao
from app.config import get_settings
from app.dominio.agendamento.estados import cancelar_pelo_paciente as cancelar_agendamento
from app.dominio.agendamento.estados import confirmar as confirmar_agendamento
from app.dominio.agendamento.estados import recusar as recusar_agendamento
from app.dominio.erros import EntradaInvalida, NaoElegivel, SemConsentimento, SolicitacaoDuplicada
from app.dominio.fila.criterios import ORIGENS_DO_PACIENTE, calcular_nota, pontuar_respostas
from app.dominio.fila.elegibilidade import DadosPaciente, RestricoesFila, motivo_inelegivel
from app.dominio.relogio import Relogio
from app.dominio.solicitacao import cancelar as cancelar_solicitacao
from app.dominio.solicitacao import confirmar_proposta, evento_criada, recusar_proposta
from app.infra.agendamentos import (
    ATIVOS,
    aplicar_agendamento,
    contar_recusas,
    para_dominio_agendamento,
    travar_agendamento,
)
from app.infra.modelos import (
    Agenda,
    Agendamento,
    Consentimento,
    CriterioFila,
    Especialidade,
    Fila,
    HistoricoSolicitacao,
    Paciente,
    RespostaCriterio,
    Solicitacao,
    Unidade,
    Vaga,
)
from app.infra.solicitacoes import criterios_da_fila, gravar_transicao, para_dominio

logger = logging.getLogger(__name__)

router = APIRouter(tags=["paciente"])

PacienteDep = Annotated[Paciente, Depends(paciente_da_sessao)]
SessionDep = Annotated[Session, Depends(get_session)]
RelogioDep = Annotated[Relogio, Depends(get_relogio)]
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]

ENCERRADAS = ("ATENDIDA", "CANCELADA")
INDICE_SOLICITACAO_ATIVA = "ux_solicitacao_ativa_por_fila"


# --- schemas ------------------------------------------------------------------------------


class UnidadeSaida(BaseModel):
    id: UUID
    sigla: str
    nome: str


class EspecialidadeSaida(BaseModel):
    id: UUID
    nome: str


class FilaSaida(BaseModel):
    id: UUID
    nome: str
    descricao_paciente: str
    unidade: UnidadeSaida
    especialidade: EspecialidadeSaida
    elegivel: bool
    motivo_inelegivel: str | None


class CriterioPacienteSaida(BaseModel):
    """Sem peso, fatores nem pontos: o paciente só vê a pergunta."""

    id: UUID
    codigo: str
    descricao: str
    tipo: str
    opcoes: list[str] | None


class FilaDetalheSaida(FilaSaida):
    criterios: list[CriterioPacienteSaida]


class RespostaEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    criterio_id: UUID
    valor: bool | int | float | Annotated[str, Field(max_length=200)]


class SolicitacaoEntrada(BaseModel):
    """AM-013: sem status, risco, nota nem pontos; o servidor calcula."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    fila_id: UUID
    turno_preferido: Literal["MANHA", "TARDE", "QUALQUER"] = "QUALQUER"
    origem_encaminhamento: str = Field(min_length=2, max_length=200)
    respostas: list[RespostaEntrada] = Field(default_factory=list, max_length=50)


class CancelamentoEntrada(BaseModel):
    """Sem texto livre: só o código (`MOTIVOS_CANCELAMENTO`), validado pelo domínio."""

    model_config = ConfigDict(extra="forbid")

    motivo_codigo: str = Field(max_length=40)


class FilaResumo(BaseModel):
    id: UUID
    nome: str
    unidade: UnidadeSaida


class SolicitacaoResumo(BaseModel):
    id: UUID
    status: str
    fila: FilaResumo
    data_pedido: date
    criada_em: datetime


class EventoPaciente(BaseModel):
    """Só o dia, sem hora: a hora de ENTROU_NA_FILA revelaria `data_entrada_fila` (ADR-007)."""

    tipo: str
    data: date
    motivo: str | None


class RespostaPaciente(BaseModel):
    descricao: str
    valor: bool | int | float | str


class AgendamentoPaciente(BaseModel):
    """Proposta (com `expira_em`) ou consulta confirmada. Horários no fuso de Recife."""

    id: UUID
    status: Literal["PROPOSTO", "CONFIRMADO"]
    inicio: datetime
    fim: datetime
    profissional: str  # UC-004: o paciente vê o profissional
    unidade: UnidadeSaida
    endereco: str | None
    expira_em: datetime | None  # só na proposta


class SolicitacaoDetalhe(SolicitacaoResumo):
    turno_preferido: str
    origem_encaminhamento: str | None
    respostas: list[RespostaPaciente]
    linha_do_tempo: list[EventoPaciente]
    agendamento_ativo: AgendamentoPaciente | None


# --- apoio --------------------------------------------------------------------------------


def _hoje(relogio: Relogio) -> date:
    return relogio.agora().astimezone(ZoneInfo(get_settings().timezone_exibicao)).date()


def _motivo(paciente: Paciente, fila: Fila, hoje: date) -> str | None:
    return motivo_inelegivel(
        DadosPaciente(paciente.sexo, paciente.data_nascimento),
        RestricoesFila(fila.sexo_elegivel, fila.idade_minima, fila.idade_maxima),
        hoje,
    )


def _fila_saida(fila: Fila, unidade: Unidade, especialidade: Especialidade, motivo: str | None):
    return {
        "id": fila.id,
        "nome": fila.nome,
        "descricao_paciente": fila.descricao_paciente,
        "unidade": UnidadeSaida(id=unidade.id, sigla=unidade.sigla, nome=unidade.nome),
        "especialidade": EspecialidadeSaida(id=especialidade.id, nome=especialidade.nome),
        "elegivel": motivo is None,
        "motivo_inelegivel": motivo,
    }


def _filas_ativas():
    return (
        select(Fila, Unidade, Especialidade)
        .join(Unidade, Unidade.id == Fila.unidade_id)
        .join(Especialidade, Especialidade.id == Fila.especialidade_id)
        .where(Fila.ativa)
    )


def _resumo(s: Solicitacao, fila: Fila, unidade: Unidade) -> dict:
    return {
        "id": s.id,
        "status": s.status,
        "fila": FilaResumo(
            id=fila.id,
            nome=fila.nome,
            unidade=UnidadeSaida(id=unidade.id, sigla=unidade.sigla, nome=unidade.nome),
        ),
        "data_pedido": s.data_pedido,
        "criada_em": s.criada_em,
    }


def _detalhe(session: Session, paciente_id: UUID, solicitacao_id: UUID) -> SolicitacaoDetalhe:
    linha = session.execute(
        select(Solicitacao, Fila, Unidade)
        .join(Fila, Fila.id == Solicitacao.fila_id)
        .join(Unidade, Unidade.id == Fila.unidade_id)
        .where(Solicitacao.id == solicitacao_id, Solicitacao.paciente_id == paciente_id)
    ).one_or_none()
    if linha is None:
        raise HTTPException(404, "Solicitação não encontrada.")
    s, fila, unidade = linha
    fuso = ZoneInfo(get_settings().timezone_exibicao)
    respostas = session.execute(
        select(CriterioFila.descricao, RespostaCriterio.valor)
        .join(CriterioFila, CriterioFila.id == RespostaCriterio.criterio_id)
        .where(RespostaCriterio.solicitacao_id == s.id, CriterioFila.origem == "PACIENTE")
        .order_by(CriterioFila.codigo)
    )
    eventos = session.execute(
        select(
            HistoricoSolicitacao.tipo, HistoricoSolicitacao.ocorrido_em, HistoricoSolicitacao.motivo
        )
        .where(HistoricoSolicitacao.solicitacao_id == s.id, HistoricoSolicitacao.visivel_paciente)
        .order_by(HistoricoSolicitacao.ocorrido_em, HistoricoSolicitacao.seq)
    )
    ativo = session.execute(
        select(Agendamento, Vaga, Agenda.profissional)
        .join(Vaga, Vaga.id == Agendamento.vaga_id)
        .join(Agenda, Agenda.id == Vaga.agenda_id)
        .where(Agendamento.solicitacao_id == s.id, Agendamento.status.in_(ATIVOS))
    ).one_or_none()
    return SolicitacaoDetalhe(
        **_resumo(s, fila, unidade),
        turno_preferido=s.turno_preferido,
        origem_encaminhamento=s.origem_encaminhamento,
        respostas=[RespostaPaciente(descricao=d, valor=v) for d, v in respostas],
        linha_do_tempo=[
            EventoPaciente(tipo=t, data=o.astimezone(fuso).date(), motivo=m) for t, o, m in eventos
        ],
        agendamento_ativo=_agendamento_paciente(*ativo, unidade, fuso) if ativo else None,
    )


def _agendamento_paciente(
    a: Agendamento, vaga: Vaga, profissional: str, unidade: Unidade, fuso: ZoneInfo
) -> AgendamentoPaciente:
    return AgendamentoPaciente(
        id=a.id,
        status=a.status,
        inicio=vaga.inicio.astimezone(fuso),
        fim=vaga.fim.astimezone(fuso),
        profissional=profissional,
        unidade=UnidadeSaida(id=unidade.id, sigla=unidade.sigla, nome=unidade.nome),
        endereco=unidade.endereco,
        expira_em=a.expira_em.astimezone(fuso) if a.status == "PROPOSTO" else None,
    )


# --- filas --------------------------------------------------------------------------------


@router.get("/filas")
def listar_filas(
    paciente: PacienteDep,
    session: SessionDep,
    relogio: RelogioDep,
    limit: Limit = 50,
    offset: Offset = 0,
) -> list[FilaSaida]:
    """Filas ativas, com a elegibilidade do paciente (RN-017). Sem contagem de pessoas."""
    hoje = _hoje(relogio)
    linhas = session.execute(
        _filas_ativas().order_by(Unidade.sigla, Fila.nome, Fila.id).limit(limit).offset(offset)
    )
    return [FilaSaida(**_fila_saida(f, u, e, _motivo(paciente, f, hoje))) for f, u, e in linhas]


@router.get("/filas/{fila_id}")
def detalhar_fila(
    fila_id: UUID, paciente: PacienteDep, session: SessionDep, relogio: RelogioDep
) -> FilaDetalheSaida:
    """Fila e as perguntas de origem PACIENTE do protocolo, sem peso nem pontos."""
    linha = session.execute(_filas_ativas().where(Fila.id == fila_id)).one_or_none()
    if linha is None:
        raise HTTPException(404, "Fila não encontrada.")
    fila, unidade, especialidade = linha
    criterios = session.scalars(
        select(CriterioFila)
        .where(
            CriterioFila.fila_id == fila.id, CriterioFila.ativo, CriterioFila.origem == "PACIENTE"
        )
        .order_by(CriterioFila.codigo)
    )
    return FilaDetalheSaida(
        **_fila_saida(fila, unidade, especialidade, _motivo(paciente, fila, _hoje(relogio))),
        criterios=[
            CriterioPacienteSaida(
                id=c.id,
                codigo=c.codigo,
                descricao=c.descricao,
                tipo=c.tipo,
                opcoes=sorted(c.parametros.get("opcoes", {})) if c.tipo == "OPCAO" else None,
            )
            for c in criterios
        ],
    )


# --- solicitações -------------------------------------------------------------------------


@router.post("/solicitacoes", status_code=201)
def criar(
    dados: SolicitacaoEntrada,
    request: Request,
    paciente: PacienteDep,
    session: SessionDep,
    relogio: RelogioDep,
) -> SolicitacaoDetalhe:
    """UC-002: cria a solicitação em EM_ANALISE, com a nota das respostas (RN-006)."""
    consentimento = session.scalar(
        select(
            exists().where(
                Consentimento.paciente_id == paciente.id,
                Consentimento.finalidade == "AGENDAMENTO",
                Consentimento.revogado_em.is_(None),
            )
        )
    )
    if not consentimento:
        raise SemConsentimento("É preciso consentir com o uso dos dados para agendamento.")
    fila = session.scalar(select(Fila).where(Fila.id == dados.fila_id, Fila.ativa))
    if fila is None:
        raise EntradaInvalida("Fila inexistente ou inativa.")
    hoje = _hoje(relogio)
    if motivo := _motivo(paciente, fila, hoje):
        raise NaoElegivel(motivo)

    criterios = criterios_da_fila(session, fila.id)
    respostas = [(r.criterio_id, r.valor) for r in dados.respostas]
    pontos = pontuar_respostas(criterios, respostas, ORIGENS_DO_PACIENTE)
    nota = calcular_nota((criterios[c], v) for c, v in respostas)

    agora = relogio.agora()
    try:
        with session.begin_nested():
            s = Solicitacao(
                paciente_id=paciente.id,
                fila_id=fila.id,
                status="EM_ANALISE",
                nota=nota,
                turno_preferido=dados.turno_preferido,
                origem_encaminhamento=dados.origem_encaminhamento,
                data_pedido=hoje,
                criada_em=agora,
            )
            session.add(s)
            session.flush()
    except IntegrityError as exc:
        if getattr(getattr(exc.orig, "diag", None), "constraint_name", None) != (
            INDICE_SOLICITACAO_ATIVA
        ):
            raise
        existente = session.scalar(
            select(Solicitacao.id).where(
                Solicitacao.paciente_id == paciente.id,
                Solicitacao.fila_id == fila.id,
                Solicitacao.status.not_in(ENCERRADAS),
            )
        )
        raise SolicitacaoDuplicada(existente) from None
    gravar_transicao(
        session,
        s,
        para_dominio(s),
        [evento_criada(agora)],
        ator_id=paciente.usuario_id,
        acao="CRIAR_SOLICITACAO",
        ip=ip_do_cliente(request),
        evento_outbox="SOLICITACAO_CRIADA",
        criacao=True,
    )
    session.add_all(
        RespostaCriterio(
            solicitacao_id=s.id,
            criterio_id=c,
            fila_id=fila.id,
            valor=v,
            pontos=pontos[c],
            respondido_por_usuario_id=paciente.usuario_id,
            respondido_em=agora,
        )
        for c, v in respostas
    )
    session.commit()
    logger.info("solicitacao criada: id=%s fila=%s", s.id, fila.id)
    return _detalhe(session, paciente.id, s.id)


@router.get("/solicitacoes")
def listar(
    paciente: PacienteDep,
    session: SessionDep,
    situacao: Literal["abertas", "encerradas"] | None = None,
    limit: Limit = 50,
    offset: Offset = 0,
) -> list[SolicitacaoResumo]:
    """Solicitações do paciente. `encerradas` alimenta o "Histórico de atendimentos"."""
    consulta = (
        select(Solicitacao, Fila, Unidade)
        .join(Fila, Fila.id == Solicitacao.fila_id)
        .join(Unidade, Unidade.id == Fila.unidade_id)
        .where(Solicitacao.paciente_id == paciente.id)
    )
    if situacao == "abertas":
        consulta = consulta.where(Solicitacao.status.not_in(ENCERRADAS))
    elif situacao == "encerradas":
        consulta = consulta.where(Solicitacao.status.in_(ENCERRADAS))
    linhas = session.execute(
        consulta.order_by(Solicitacao.criada_em.desc(), Solicitacao.id).limit(limit).offset(offset)
    )
    return [SolicitacaoResumo(**_resumo(s, f, u)) for s, f, u in linhas]


@router.get("/solicitacoes/{solicitacao_id}")
def detalhar(
    solicitacao_id: UUID, paciente: PacienteDep, session: SessionDep
) -> SolicitacaoDetalhe:
    """Status, fila e linha do tempo só com os eventos visíveis ao paciente (RN-007)."""
    return _detalhe(session, paciente.id, solicitacao_id)


@router.post("/solicitacoes/{solicitacao_id}/cancelar")
def cancelar(
    solicitacao_id: UUID,
    request: Request,
    paciente: PacienteDep,
    session: SessionDep,
    relogio: RelogioDep,
    dados: CancelamentoEntrada,
) -> SolicitacaoDetalhe:
    """Cancelamento ("não vou precisar"): EM_ANALISE, NA_FILA, EM_PROPOSTA ou AGENDADA.

    Com proposta ou consulta ativa, o agendamento é cancelado junto, só antes do início da
    vaga; a vaga fica livre e o Worker a oferece ao próximo (RN-005). Outros estados → 409.
    Travas: solicitação, depois agendamento (a vaga só é lida).
    """
    s = session.scalar(
        select(Solicitacao)
        .where(Solicitacao.id == solicitacao_id, Solicitacao.paciente_id == paciente.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if s is None:
        raise HTTPException(404, "Solicitação não encontrada.")
    agora = relogio.agora()
    ativo = session.execute(
        select(Agendamento, Vaga.inicio)
        .join(Vaga, Vaga.id == Agendamento.vaga_id)
        .where(Agendamento.solicitacao_id == s.id, Agendamento.status.in_(ATIVOS))
        .with_for_update(of=Agendamento)
        .execution_options(populate_existing=True)
    ).one_or_none()
    nova, evento = cancelar_solicitacao(
        para_dominio(s), dados.motivo_codigo, agora, tem_agendamento_ativo=ativo is not None
    )
    if ativo:
        a, inicio = ativo
        aplicar_agendamento(
            session,
            a,
            cancelar_agendamento(para_dominio_agendamento(a), inicio, agora),
            ator_id=paciente.usuario_id,
            acao="CANCELAR_AGENDAMENTO",
            ip=ip_do_cliente(request),
        )
    s.motivo_cancelamento = dados.motivo_codigo
    gravar_transicao(
        session,
        s,
        nova,
        [evento],
        ator_id=paciente.usuario_id,
        acao="CANCELAR_SOLICITACAO",
        ip=ip_do_cliente(request),
        evento_outbox="AGENDAMENTO_CANCELADO" if ativo else "SOLICITACAO_CANCELADA",
        auditoria_depois={"motivo_cancelamento": dados.motivo_codigo},
        agendamento_id=ativo[0].id if ativo else None,
    )
    session.commit()
    logger.info("solicitacao cancelada: id=%s", s.id)
    return _detalhe(session, paciente.id, s.id)


# --- resposta à proposta ------------------------------------------------------------------


def _travar_do_paciente(
    session: Session, agendamento_id: UUID, paciente: Paciente
) -> tuple[Solicitacao, Agendamento]:
    """Trava solicitação e agendamento do próprio paciente; de outro paciente, 404 (AM-001)."""
    par = travar_agendamento(session, agendamento_id, Solicitacao.paciente_id == paciente.id)
    if par is None:
        raise HTTPException(404, "Agendamento não encontrado.")
    return par


@router.post("/agendamentos/{agendamento_id}/confirmar")
def confirmar(
    agendamento_id: UUID,
    request: Request,
    paciente: PacienteDep,
    session: SessionDep,
    relogio: RelogioDep,
) -> SolicitacaoDetalhe:
    """UC-004: PROPOSTO → CONFIRMADO e solicitação AGENDADA, só antes de `expira_em`."""
    s, a = _travar_do_paciente(session, agendamento_id, paciente)
    agora = relogio.agora()
    novo = confirmar_agendamento(para_dominio_agendamento(a), agora)
    nova, evento = confirmar_proposta(para_dominio(s), agora)
    aplicar_agendamento(
        session,
        a,
        novo,
        ator_id=paciente.usuario_id,
        acao="CONFIRMAR_AGENDAMENTO",
        ip=ip_do_cliente(request),
    )
    gravar_transicao(
        session,
        s,
        nova,
        [evento],
        ator_id=paciente.usuario_id,
        acao="CONFIRMAR_AGENDAMENTO",
        ip=ip_do_cliente(request),
        evento_outbox="AGENDAMENTO_CONFIRMADO",
        agendamento_id=a.id,
    )
    session.commit()
    logger.info("agendamento confirmado: id=%s", a.id)
    return _detalhe(session, paciente.id, s.id)


@router.post("/agendamentos/{agendamento_id}/recusar")
def recusar(
    agendamento_id: UUID,
    request: Request,
    paciente: PacienteDep,
    session: SessionDep,
    relogio: RelogioDep,
) -> SolicitacaoDetalhe:
    """UC-005 ("esta data não serve"): só PROPOSTO. A vaga fica livre para o próximo."""
    s, a = _travar_do_paciente(session, agendamento_id, paciente)
    agora = relogio.agora()
    novo = recusar_agendamento(para_dominio_agendamento(a), agora)
    nova, eventos = recusar_proposta(
        para_dominio(s),
        contar_recusas(session, s),
        get_settings().recusas_mantendo_posicao,
        agora,
    )
    aplicar_agendamento(
        session,
        a,
        novo,
        ator_id=paciente.usuario_id,
        acao="RECUSAR_PROPOSTA",
        ip=ip_do_cliente(request),
    )
    gravar_transicao(
        session,
        s,
        nova,
        eventos,
        ator_id=paciente.usuario_id,
        acao="RECUSAR_PROPOSTA",
        ip=ip_do_cliente(request),
        evento_outbox="PROPOSTA_RECUSADA",
        agendamento_id=a.id,
    )
    session.commit()
    logger.info("proposta recusada: id=%s", a.id)
    return _detalhe(session, paciente.id, s.id)
