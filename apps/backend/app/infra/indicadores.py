"""Consultas dos indicadores do gestor (UC de leitura, sem escrita).

Tudo é agregado no banco, num número fixo de consultas (sem N+1). Cada família de contagens
tem a própria âncora de tempo e vem agrupada por semana de Recife (segunda-feira); o total é a
soma das semanas. Nenhuma consulta devolve dado de paciente.
"""

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import Date, and_, cast, exists, func, not_, select, text, true
from sqlalchemy.orm import Session, aliased

from app.infra.modelos import Agenda, Agendamento, Fila, HistoricoSolicitacao, Solicitacao, Vaga

OCUPAM_A_VAGA = ("CONFIRMADO", "REALIZADO", "FALTOU")
RECUSA = "RECUSADO_PELO_PACIENTE"

Semanas = dict[date, dict[str, int]]
CONTAGENS = (
    "confirmadas",
    "recusadas",
    "expiradas",
    "propostas_canceladas_sem_resposta",
    "realizadas",
    "faltas",
    "solicitacoes_criadas",
    "desistencias",
    "vagas_ofertadas",
    "vagas_ocupadas",
    "vagas_reaproveitadas",
    "vagas_perdidas",
)


def filas_do_escopo(
    session: Session, escopo: frozenset[UUID], unidade_id: UUID | None, fila_id: UUID | None
) -> list[UUID]:
    """Filas do escopo que casam com os filtros; os filtros só encolhem o escopo."""
    consulta = select(Fila.id).where(Fila.id.in_(escopo))
    if unidade_id is not None:
        consulta = consulta.where(Fila.unidade_id == unidade_id)
    if fila_id is not None:
        consulta = consulta.where(Fila.id == fila_id)
    return list(session.scalars(consulta))


def sem_jit(session: Session) -> None:
    """O JIT custava 3 a 5 vezes a própria consulta nos EXPLAIN com 100 mil agendamentos.
    Vale só até o fim da transação."""
    session.execute(text("SET LOCAL jit = off"))


def _semana(coluna, fuso: str):
    return cast(func.date_trunc("week", func.timezone(fuso, coluna)), Date)


def _agrupar(session: Session, consulta, nomes: tuple[str, ...]) -> Semanas:
    saida: Semanas = {}
    for semana, *valores in session.execute(consulta):
        saida[semana] = dict(zip(nomes, valores, strict=True))
    return saida


def propostas(session: Session, filas: list[UUID], inicio: datetime, fim: datetime, fuso: str):
    """Propostas feitas no período (âncora `proposto_em`)."""
    semana = _semana(Agendamento.proposto_em, fuso)
    recusada = and_(Agendamento.status == "CANCELADO", Agendamento.motivo_cancelamento == RECUSA)
    sem_resposta = and_(
        Agendamento.status == "CANCELADO",
        Agendamento.confirmado_em.is_(None),
        Agendamento.motivo_cancelamento.is_distinct_from(RECUSA),
    )
    consulta = (
        select(
            semana,
            func.count().filter(Agendamento.confirmado_em.is_not(None)),
            func.count().filter(recusada),
            func.count().filter(Agendamento.status == "EXPIRADO"),
            func.count().filter(sem_resposta),
        )
        .join(Vaga, Vaga.id == Agendamento.vaga_id)
        .join(Agenda, Agenda.id == Vaga.agenda_id)
        .where(
            Agenda.fila_id.in_(filas),
            Agendamento.proposto_em >= inicio,
            Agendamento.proposto_em < fim,
        )
        .group_by(semana)
    )
    nomes = ("confirmadas", "recusadas", "expiradas", "propostas_canceladas_sem_resposta")
    return _agrupar(session, consulta, nomes)


def presencas(session: Session, filas: list[UUID], inicio: datetime, fim: datetime, fuso: str):
    """Atendimentos registrados com vaga no período (âncora `vaga.inicio`)."""
    semana = _semana(Vaga.inicio, fuso)
    consulta = (
        select(
            semana,
            func.count().filter(Agendamento.status == "REALIZADO"),
            func.count().filter(Agendamento.status == "FALTOU"),
        )
        .join(Vaga, Vaga.id == Agendamento.vaga_id)
        .join(Agenda, Agenda.id == Vaga.agenda_id)
        .where(
            Agenda.fila_id.in_(filas),
            Vaga.inicio >= inicio,
            Vaga.inicio < fim,
            Agendamento.status.in_(("REALIZADO", "FALTOU")),
        )
        .group_by(semana)
    )
    return _agrupar(session, consulta, ("realizadas", "faltas"))


def solicitacoes(session: Session, filas: list[UUID], inicio: datetime, fim: datetime, fuso: str):
    """Solicitações criadas no período (`criada_em`); desistência = cancelada pelo paciente."""
    semana = _semana(Solicitacao.criada_em, fuso)
    desistiu = and_(Solicitacao.status == "CANCELADA", Solicitacao.motivo_cancelamento.is_not(None))
    consulta = (
        select(semana, func.count(), func.count().filter(desistiu))
        .where(
            Solicitacao.fila_id.in_(filas),
            Solicitacao.criada_em >= inicio,
            Solicitacao.criada_em < fim,
        )
        .group_by(semana)
    )
    return _agrupar(session, consulta, ("solicitacoes_criadas", "desistencias"))


def vagas(
    session: Session, filas: list[UUID], inicio: datetime, fim: datetime, agora: datetime, fuso: str
):
    """Vagas ATIVAS com início no período. A ocupação é derivada do agendamento (ADR-004)."""
    semana = _semana(Vaga.inicio, fuso)
    ocupada = exists().where(Agendamento.vaga_id == Vaga.id, Agendamento.status.in_(OCUPAM_A_VAGA))
    anterior, confirmada = aliased(Agendamento), aliased(Agendamento)
    # Proposta desfeita (cancelada ou expirada) e, depois, outra solicitação confirmou a vaga.
    reaproveitada = exists().where(
        confirmada.vaga_id == Vaga.id,
        confirmada.status.in_(OCUPAM_A_VAGA),
        confirmada.confirmado_em.is_not(None),
        exists().where(
            anterior.vaga_id == confirmada.vaga_id,
            anterior.status.in_(("CANCELADO", "EXPIRADO")),
            anterior.solicitacao_id != confirmada.solicitacao_id,
            anterior.proposto_em < confirmada.proposto_em,
        ),
    )
    consulta = (
        select(
            semana,
            func.count(),
            func.count().filter(ocupada),
            func.count().filter(reaproveitada),
            func.count().filter(and_(Vaga.inicio < agora, not_(ocupada))),
        )
        .join(Agenda, Agenda.id == Vaga.agenda_id)
        .where(
            Agenda.fila_id.in_(filas),
            Vaga.status_admin == "ATIVA",
            Vaga.inicio >= inicio,
            Vaga.inicio < fim,
        )
        .group_by(semana)
    )
    nomes = ("vagas_ofertadas", "vagas_ocupadas", "vagas_reaproveitadas", "vagas_perdidas")
    return _agrupar(session, consulta, nomes)


def tempo_de_espera(session: Session, filas: list[UUID], inicio: datetime, fim: datetime):
    """Entrada na fila até a primeira confirmação, das solicitações cuja primeira confirmação cai
    no período. Devolve (quantidade, mediana em dias, p90 em dias)."""
    anterior = aliased(Agendamento)
    entrada = (
        select(func.min(HistoricoSolicitacao.ocorrido_em).label("em"))
        .where(
            HistoricoSolicitacao.solicitacao_id == Agendamento.solicitacao_id,
            HistoricoSolicitacao.tipo == "ENTROU_NA_FILA",
        )
        .lateral()
    )
    primeira = ~exists().where(
        anterior.solicitacao_id == Agendamento.solicitacao_id,
        anterior.confirmado_em < Agendamento.confirmado_em,
    )
    dias = (func.extract("epoch", Agendamento.confirmado_em - entrada.c.em) / 86400).label("dias")
    espera = (
        select(dias)
        .join(Vaga, Vaga.id == Agendamento.vaga_id)
        .join(Agenda, Agenda.id == Vaga.agenda_id)
        .join(entrada, true())
        .where(
            Agenda.fila_id.in_(filas),
            Agendamento.confirmado_em >= inicio,
            Agendamento.confirmado_em < fim,
            primeira,
            entrada.c.em.is_not(None),
        )
        .subquery()
    )
    n, mediana, p90 = session.execute(
        select(
            func.count(),
            func.percentile_cont(0.5).within_group(espera.c.dias),
            func.percentile_cont(0.9).within_group(espera.c.dias),
        )
    ).one()
    dias = [None if v is None else round(float(v), 2) for v in (mediana, p90)]
    return n, *dias


def fila_atual(session: Session, filas: list[UUID]) -> dict[str, int]:
    """Solicitações NA_FILA agora, por cor de risco."""
    consulta = (
        select(Solicitacao.classificacao_risco, func.count())
        .where(Solicitacao.fila_id.in_(filas), Solicitacao.status == "NA_FILA")
        .group_by(Solicitacao.classificacao_risco)
    )
    return {risco: n for risco, n in session.execute(consulta)}
