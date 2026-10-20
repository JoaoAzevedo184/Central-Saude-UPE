"""Persistência do agendamento: travas, auditoria e o trabalho de cada item dos jobs.

Ordem das travas em todo caminho (API e Worker): vaga (só o matching, que trava a
solicitação com SKIP LOCKED), depois solicitação, depois agendamento. Os outros caminhos
só leem a vaga. Ordem diferente em dois caminhos pode travar em deadlock (cancelar enquanto o
Worker expira). Os jobs usam `SKIP LOCKED` e nunca esperam.
"""

import logging
from collections.abc import Iterable
from datetime import datetime
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import ColumnElement, exists, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.config import Settings
from app.dominio.agendamento.estados import Agendamento as AgendamentoDominio
from app.dominio.agendamento.estados import expirar
from app.dominio.agendamento.proposta import (
    Candidata,
    Proposta,
    VagaLivre,
    propor_vaga,
    turnos_compativeis,
)
from app.dominio.agendamento.vagas import GradeAgenda, horarios_da_agenda
from app.dominio.solicitacao import expirar_proposta
from app.infra.modelos import Agenda, Agendamento, Auditoria, Fila, Solicitacao, Vaga
from app.infra.solicitacoes import gravar_transicao, ordem_da_fila, para_dominio, para_json

logger = logging.getLogger(__name__)

ATIVOS = ("PROPOSTO", "CONFIRMADO")
# Índices que decidem a corrida entre propostas (RN-001, RN-002).
INDICES_DE_OCUPACAO = ("ux_agendamento_vaga_ativa", "ux_agendamento_solicitacao_ativa")
# ponytail: o matching olha só as primeiras da fila; aumentar se muitas forem descartadas
# (já receberam esta vaga ou estão travadas por outro Worker).
CANDIDATAS_POR_VAGA = 50
# Vagas que já geraram o aviso do teto neste processo: avisa uma vez, não a cada rodada.
# ponytail: em memória, zera ao reiniciar o Worker (e cada réplica avisa uma vez).
_TETO_AVISADO: set[UUID] = set()


def para_dominio_agendamento(a: Agendamento) -> AgendamentoDominio:
    return AgendamentoDominio(a.id, a.status, a.expira_em, a.respondido_em, a.motivo_cancelamento)


def vaga_ocupada(vaga_id: Any) -> ColumnElement[bool]:
    """Ocupação derivada do agendamento ativo (ADR-004)."""
    return exists().where(Agendamento.vaga_id == vaga_id, Agendamento.status.in_(ATIVOS))


def aplicar_agendamento(
    session: Session,
    modelo: Agendamento,
    novo: AgendamentoDominio,
    *,
    ator_id: UUID | None,
    acao: str,
    ip: str | None,
) -> None:
    """Aplica a transição do domínio e grava a auditoria do agendamento (RN-010)."""
    campos = ("status", "respondido_em", "motivo_cancelamento")
    antes = {c: getattr(modelo, c) for c in campos}
    for campo in campos:
        setattr(modelo, campo, getattr(novo, campo))
    mudou = [c for c in campos if antes[c] != getattr(modelo, c)]
    session.add(
        Auditoria(
            ator_usuario_id=ator_id,
            acao=acao,
            entidade="agendamento",
            entidade_id=modelo.id,
            dados_antes=para_json({c: antes[c] for c in mudou}),
            dados_depois=para_json({c: getattr(modelo, c) for c in mudou}),
            ip=ip,
        )
    )


def travar_agendamento(
    session: Session,
    agendamento_id: UUID,
    *filtros: ColumnElement[bool],
    skip_locked: bool = False,
) -> tuple[Solicitacao, Agendamento] | None:
    """Trava a solicitação e depois o agendamento, nessa ordem.

    `filtros` restringem a solicitação dentro da query (dono ou escopo): fora deles, `None`.
    """
    da_solicitacao = (
        select(Agendamento.solicitacao_id).where(Agendamento.id == agendamento_id).scalar_subquery()
    )
    s = session.scalar(
        select(Solicitacao)
        .where(Solicitacao.id == da_solicitacao, *filtros)
        .with_for_update(skip_locked=skip_locked)
        .execution_options(populate_existing=True)
    )
    if s is None:
        return None
    a = session.scalar(
        select(Agendamento)
        .where(Agendamento.id == agendamento_id)
        .with_for_update(skip_locked=skip_locked)
        .execution_options(populate_existing=True)
    )
    return None if a is None else (s, a)


def contar_recusas(session: Session, solicitacao: Solicitacao) -> int:
    """Recusas desde a última entrada na fila (UC-005): voltar ao fim zera a contagem.

    `>` estrito: a recusa que mandou para o fim tem `respondido_em == data_entrada_fila`.
    """
    return session.scalar(
        select(func.count()).where(
            Agendamento.solicitacao_id == solicitacao.id,
            Agendamento.motivo_cancelamento == "RECUSADO_PELO_PACIENTE",
            Agendamento.respondido_em > solicitacao.data_entrada_fila,
        )
    )


# --- gerar_vagas --------------------------------------------------------------------------


def agendas_ativas(session: Session) -> list[UUID]:
    return list(
        session.scalars(
            select(Agenda.id)
            .join(Fila, Fila.id == Agenda.fila_id)
            .where(Agenda.ativa, Fila.ativa)
            .order_by(Agenda.id)
        )
    )


def gerar_vagas_da_agenda(session: Session, agenda_id: UUID, agora: datetime, cfg: Settings) -> int:
    """Insere as vagas que faltam no horizonte. `ON CONFLICT DO NOTHING`: rodar de novo não
    duplica. Devolve quantas vagas novas."""
    agenda = session.scalar(
        select(Agenda).where(Agenda.id == agenda_id, Agenda.ativa).with_for_update(skip_locked=True)
    )
    if agenda is None:
        return 0
    grade = GradeAgenda(
        agenda.dias_semana,
        agenda.hora_inicio,
        agenda.hora_fim,
        agenda.duracao_min,
        agenda.vigencia_inicio,
        agenda.vigencia_fim,
    )
    horarios = horarios_da_agenda(
        grade, agora, cfg.vagas_horizonte_dias, ZoneInfo(cfg.timezone_exibicao)
    )
    if not horarios:
        return 0
    inseridas = session.execute(
        insert(Vaga)
        .values([{"agenda_id": agenda.id, "inicio": i, "fim": f} for i, f in horarios])
        .on_conflict_do_nothing(index_elements=["agenda_id", "inicio"])
        .returning(Vaga.id)
    )
    return len(inseridas.all())


# --- propor_vagas -------------------------------------------------------------------------


def _filtro_vaga_livre(agora: datetime) -> list[ColumnElement[bool]]:
    tem_fila = exists().where(Solicitacao.fila_id == Fila.id, Solicitacao.status == "NA_FILA")
    return [
        Vaga.status_admin == "ATIVA",
        Vaga.inicio > agora,
        Agenda.ativa,
        Fila.ativa,
        ~vaga_ocupada(Vaga.id),
        tem_fila,
    ]


def vagas_livres(session: Session, agora: datetime) -> list[UUID]:
    """Vagas livres no futuro, de filas com alguém `NA_FILA`, na ordem do início."""
    return list(
        session.scalars(
            select(Vaga.id)
            .join(Agenda, Agenda.id == Vaga.agenda_id)
            .join(Fila, Fila.id == Agenda.fila_id)
            .where(*_filtro_vaga_livre(agora))
            .order_by(Vaga.inicio, Vaga.id)
        )
    )


def propor_na_vaga(session: Session, vaga_id: UUID, agora: datetime, cfg: Settings) -> bool:
    """Trava a vaga e as primeiras da fila (`SKIP LOCKED`) e grava a proposta, se houver.

    A violação dos índices de ocupação sobe como `IntegrityError` no flush; quem chama desfaz.
    """
    linha = session.execute(
        select(Vaga, Fila)
        .join(Agenda, Agenda.id == Vaga.agenda_id)
        .join(Fila, Fila.id == Agenda.fila_id)
        .where(Vaga.id == vaga_id, *_filtro_vaga_livre(agora))
        .with_for_update(of=Vaga, skip_locked=True)
    ).one_or_none()
    if linha is None:
        return False
    vaga, fila = linha
    fuso = ZoneInfo(cfg.timezone_exibicao)
    ja_teve = exists().where(
        Agendamento.vaga_id == vaga.id, Agendamento.solicitacao_id == Solicitacao.id
    )
    # Leitura sem trava; só a escolhida é travada (SKIP LOCKED). Travar todas as candidatas
    # faria o outro Worker pular a fila inteira e deixar vagas sem proposta nesta rodada.
    linhas = session.execute(
        select(Solicitacao, ja_teve)
        .where(
            Solicitacao.fila_id == fila.id,
            Solicitacao.status == "NA_FILA",
            Solicitacao.turno_preferido.in_(turnos_compativeis(vaga.inicio, fuso)),
        )
        .order_by(*ordem_da_fila())
        .limit(CANDIDATAS_POR_VAGA)
    ).all()
    teto = len(linhas) == CANDIDATAS_POR_VAGA and all(teve for _, teve in linhas)
    if teto and vaga.id not in _TETO_AVISADO:
        # Teto atingido: pode haver alguém elegível depois das primeiras. Só IDs no log.
        _TETO_AVISADO.add(vaga.id)
        logger.warning(
            "propor_vagas: vaga %s sem proposta: as %d primeiras da fila já receberam esta vaga",
            vaga.id,
            CANDIDATAS_POR_VAGA,
        )
    candidatas = {s.id: Candidata(para_dominio(s), s.turno_preferido, teve) for s, teve in linhas}
    livre = VagaLivre(vaga.id, vaga.inicio, fila.prazo_confirmacao_horas)

    def escolher(opcoes: Iterable[Candidata]) -> Proposta | None:
        return propor_vaga(
            opcoes,
            livre,
            agora,
            antecedencia_minima_horas=cfg.proposta_antecedencia_minima_horas,
            janela_minima_horas=cfg.proposta_janela_minima_horas,
            fuso=fuso,
        )

    while (proposta := escolher(candidatas.values())) is not None:
        escolhida = candidatas.pop(proposta.solicitacao.id)
        s = session.scalar(
            select(Solicitacao)
            .where(Solicitacao.id == escolhida.solicitacao.id, Solicitacao.status == "NA_FILA")
            .with_for_update(skip_locked=True)
            .execution_options(populate_existing=True)
        )
        if s is None:
            continue  # travada por outro Worker ou já mudou de estado: a próxima da ordem
        # Revalida no domínio com a linha travada (a leitura acima pode estar defasada).
        proposta = escolher(
            [Candidata(para_dominio(s), s.turno_preferido, escolhida.ja_teve_esta_vaga)]
        )
        if proposta is not None:
            break
    if proposta is None:
        return False
    agendamento = Agendamento(
        solicitacao_id=s.id,
        vaga_id=vaga.id,
        status="PROPOSTO",
        proposto_por_usuario_id=None,  # automático (ADR-021)
        proposto_em=agora,
        expira_em=proposta.expira_em,
    )
    session.add(agendamento)
    session.flush()
    gravar_transicao(
        session,
        s,
        proposta.solicitacao,
        [proposta.evento],
        ator_id=None,
        acao="PROPOR_VAGA",
        ip=None,
        evento_outbox="PROPOSTA_ENVIADA",
        agendamento_id=agendamento.id,
    )
    session.add(
        Auditoria(
            ator_usuario_id=None,
            acao="PROPOR_VAGA",
            entidade="agendamento",
            entidade_id=agendamento.id,
            dados_antes=None,
            dados_depois=para_json(
                {
                    "status": "PROPOSTO",
                    "solicitacao_id": str(s.id),
                    "vaga_id": str(vaga.id),
                    "expira_em": proposta.expira_em,
                }
            ),
            ip=None,
        )
    )
    return True


# --- expirar_propostas --------------------------------------------------------------------


def propostas_vencidas(session: Session, agora: datetime) -> list[UUID]:
    return list(
        session.scalars(
            select(Agendamento.id)
            .where(Agendamento.status == "PROPOSTO", Agendamento.expira_em <= agora)
            .order_by(Agendamento.expira_em, Agendamento.id)
        )
    )


def expirar_agendamento(session: Session, agendamento_id: UUID, agora: datetime) -> bool:
    """UC-006: EXPIRADO e solicitação no fim da fila. Já resolvida ou travada: nada a fazer."""
    par = travar_agendamento(session, agendamento_id, skip_locked=True)
    if par is None:
        return False
    s, a = par
    if a.status != "PROPOSTO" or a.expira_em > agora:
        return False  # o paciente respondeu antes (UC-006 E1)
    aplicar_agendamento(
        session,
        a,
        expirar(para_dominio_agendamento(a), agora),
        ator_id=None,
        acao="EXPIRAR_PROPOSTA",
        ip=None,
    )
    nova, eventos = expirar_proposta(para_dominio(s), agora)
    gravar_transicao(
        session,
        s,
        nova,
        eventos,
        ator_id=None,
        acao="EXPIRAR_PROPOSTA",
        ip=None,
        evento_outbox="PROPOSTA_EXPIRADA",
        agendamento_id=a.id,
    )
    return True
