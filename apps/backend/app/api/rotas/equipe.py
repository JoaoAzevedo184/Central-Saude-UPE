"""Área da equipe: filas do escopo, painel ordenado, classificação e critérios.

Toda consulta filtra por `fila_id IN escopo` dentro da query (ADR-025); fila ou solicitação
fora do escopo responde 404. Leitura: ATENDENTE, GESTOR e ADMIN. Escrita: só ATENDENTE.
As consultas ao painel e ao detalhe são auditadas (AM-007), sem nome, CPF nem respostas.
"""

import logging
from datetime import date, datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select, true
from sqlalchemy.orm import Session

from app.api.deps import escopo_da_equipe, exige_papel, get_relogio, get_session, ip_do_cliente
from app.dominio.cadastro import abreviar_nome, mascarar_cpf
from app.dominio.fila.criterios import ORIGENS_DA_EQUIPE, calcular_nota, pontuar_respostas
from app.dominio.relogio import Relogio
from app.dominio.solicitacao import classificar as classificar_solicitacao
from app.dominio.solicitacao import exigir_aceita_respostas, recalcular_nota
from app.infra.modelos import (
    STATUS_SOLICITACAO,
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
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]
StatusSolicitacao = Literal[
    "EM_ANALISE", "NA_FILA", "EM_PROPOSTA", "AGENDADA", "ATENDIDA", "CANCELADA"
]


# --- schemas ------------------------------------------------------------------------------


class FilaEquipeSaida(BaseModel):
    id: UUID
    nome: str
    unidade_sigla: str
    especialidade: str
    ativa: bool
    contagem_por_status: dict[str, int]


class UltimaMudanca(BaseModel):
    """Sem motivo: texto livre da reclassificação fica só no detalhe, que é auditado."""

    tipo: str
    ocorrido_em: datetime


class ItemPainel(BaseModel):
    id: UUID
    status: str
    posicao: int | None  # só NA_FILA; calculada na consulta, nunca gravada
    classificacao_risco: str | None
    nota: int
    data_entrada_fila: datetime | None
    paciente_nome: str  # abreviado
    paciente_cpf: str  # mascarado
    ultima_mudanca: UltimaMudanca | None


class PainelSaida(BaseModel):
    total: int
    itens: list[ItemPainel]


class RespostaEquipeSaida(BaseModel):
    criterio_id: UUID
    codigo: str
    descricao: str
    origem: str
    valor: Any
    pontos: int


class EventoEquipe(BaseModel):
    tipo: str
    status_anterior: str | None
    status_novo: str | None
    motivo: str | None
    visivel_paciente: bool
    ator_usuario_id: UUID | None
    ocorrido_em: datetime


class SolicitacaoEquipeSaida(BaseModel):
    id: UUID
    status: str
    fila_id: UUID
    paciente_nome: str
    paciente_cpf: str
    classificacao_risco: str | None
    nota: int
    data_entrada_fila: datetime | None
    data_pedido: date
    turno_preferido: str
    origem_encaminhamento: str | None
    respostas: list[RespostaEquipeSaida]
    historico: list[EventoEquipe]


class ClassificacaoEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    classificacao_risco: Literal["VERMELHO", "AMARELO", "VERDE"]
    motivo: str | None = Field(default=None, min_length=3, max_length=500)


class RespostaEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    criterio_id: UUID
    valor: bool | int | float | Annotated[str, Field(max_length=200)]


class RespostasEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    respostas: list[RespostaEntrada] = Field(min_length=1, max_length=50)


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
        .order_by(HistoricoSolicitacao.ocorrido_em, HistoricoSolicitacao.id)
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


@router.get("/filas")
def listar_filas(
    _: LeitorDep, escopo: EscopoDep, session: SessionDep, limit: Limit = 50, offset: Offset = 0
) -> list[FilaEquipeSaida]:
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
    return [
        FilaEquipeSaida(
            id=f.id,
            nome=f.nome,
            unidade_sigla=sigla,
            especialidade=especialidade,
            ativa=f.ativa,
            contagem_por_status=contagens[f.id],
        )
        for f, sigla, especialidade in linhas
    ]


@router.get("/filas/{fila_id}/solicitacoes")
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
        .order_by(HistoricoSolicitacao.ocorrido_em.desc(), HistoricoSolicitacao.id.desc())
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


@router.get("/solicitacoes/{solicitacao_id}")
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


# --- escrita (só ATENDENTE) ---------------------------------------------------------------


@router.post("/solicitacoes/{solicitacao_id}/classificar")
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


@router.put("/solicitacoes/{solicitacao_id}/respostas")
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
