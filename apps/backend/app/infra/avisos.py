"""Persistência dos avisos: consumo da outbox, envio dos e-mails e lembretes (ADR-006).

Cada função de item trava a sua linha com `SKIP LOCKED` e devolve se fez algo; o commit é do
job. A falha de um item é tratada aqui dentro, para a contagem de tentativas ser gravada no
mesmo commit (o `_por_item` do job desfaria tudo). Log só com IDs e o tipo do erro: nunca
endereço de e-mail nem corpo da mensagem (AM-008).
"""

import logging
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import ColumnElement, and_, exists, or_, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.config import Settings
from app.dominio.notificacoes.avisos import (
    TIPO_LEMBRETE,
    TIPOS_EVENTO_OUTBOX,
    Aviso,
    Contexto,
    montar_avisos,
    proxima_tentativa,
)
from app.dominio.notificacoes.canal import CanalNotificacao, Mensagem
from app.infra.modelos import (
    Agenda,
    Agendamento,
    Consentimento,
    Fila,
    Notificacao,
    Outbox,
    Paciente,
    Solicitacao,
    Unidade,
    Usuario,
    Vaga,
)
from app.logging import resumo_do_erro

logger = logging.getLogger(__name__)


def _destinatario(session: Session, solicitacao_id: UUID) -> tuple[UUID, UUID, str | None]:
    """(paciente_id, usuario_id, e-mail) do dono da solicitação."""
    return session.execute(
        select(Paciente.id, Usuario.id, Usuario.email)
        .join(Usuario, Usuario.id == Paciente.usuario_id)
        .join(Solicitacao, Solicitacao.paciente_id == Paciente.id)
        .where(Solicitacao.id == solicitacao_id)
    ).one()


def _contexto(session: Session, agendamento_id: UUID | None) -> Contexto:
    if agendamento_id is None:
        return Contexto()
    a, inicio, profissional, unidade = session.execute(
        select(Agendamento, Vaga.inicio, Agenda.profissional, Unidade.nome)
        .join(Vaga, Vaga.id == Agendamento.vaga_id)
        .join(Agenda, Agenda.id == Vaga.agenda_id)
        .join(Fila, Fila.id == Agenda.fila_id)
        .join(Unidade, Unidade.id == Fila.unidade_id)
        .where(Agendamento.id == agendamento_id)
    ).one()
    return Contexto(
        inicio=inicio,
        expira_em=a.expira_em,
        unidade=unidade,
        profissional=profissional,
    )


def _consentiu_lembrete(session: Session, paciente_id: UUID) -> bool:
    return bool(
        session.scalar(
            select(
                exists().where(
                    Consentimento.paciente_id == paciente_id,
                    Consentimento.finalidade == "LEMBRETE_EMAIL",
                    Consentimento.revogado_em.is_(None),
                )
            )
        )
    )


def _linhas(avisos: list[Aviso], agora: datetime, **comuns: Any) -> list[dict[str, Any]]:
    """O aviso do site já nasce entregue; o e-mail nasce pendente para o `enviar_emails`."""
    return [
        comuns
        | {
            "canal": a.canal,
            "titulo": a.titulo,
            "corpo": a.corpo,
            "status_envio": "ENVIADA" if a.canal == "IN_APP" else "PENDENTE",
            "enviada_em": agora if a.canal == "IN_APP" else None,
            "proximo_retry_em": None if a.canal == "IN_APP" else agora,
        }
        for a in avisos
    ]


# --- processar_outbox ---------------------------------------------------------------------


def _evento_vencido(agora: datetime) -> ColumnElement[bool]:
    """Evento novo está sempre vencido: `proximo_retry_em` nasce com o `now()` do banco, não
    com o `Relogio`. A espera só vale para as novas tentativas, que o Worker agenda."""
    return and_(
        Outbox.status == "PENDENTE",
        or_(Outbox.tentativas == 0, Outbox.proximo_retry_em <= agora),
    )


def eventos_pendentes(session: Session, agora: datetime, limite: int) -> list[UUID]:
    return list(
        session.scalars(
            select(Outbox.id)
            .where(_evento_vencido(agora))
            .order_by(Outbox.criado_em, Outbox.id)
            .limit(limite)
        )
    )


def processar_evento(session: Session, outbox_id: UUID, agora: datetime, cfg: Settings) -> bool:
    """Cria os avisos do evento e o marca PROCESSADO. Tipo desconhecido → FALHOU."""
    evento = session.scalar(
        select(Outbox)
        .where(Outbox.id == outbox_id, _evento_vencido(agora))
        .with_for_update(skip_locked=True)
    )
    if evento is None:
        return False  # outro Worker pegou, ou já foi processado
    if evento.tipo_evento not in TIPOS_EVENTO_OUTBOX:
        logger.warning("processar_outbox: evento %s com tipo desconhecido", evento.id)
        evento.status = "FALHOU"
        return False
    try:
        with session.begin_nested():
            _criar_avisos_do_evento(session, evento, agora, cfg)
    except Exception as exc:
        evento.tentativas += 1
        proxima = proxima_tentativa(evento.tentativas, cfg.outbox_max_tentativas, agora)
        if proxima is None:
            evento.status = "FALHOU"
        else:
            evento.proximo_retry_em = proxima
        logger.error(
            "processar_outbox: evento %s falhou (tentativa %d): %s",
            evento.id,
            evento.tentativas,
            resumo_do_erro(exc),
        )
        return False
    evento.status = "PROCESSADO"
    evento.processado_em = agora
    return True


def _criar_avisos_do_evento(session: Session, evento: Outbox, agora: datetime, cfg: Settings):
    payload = evento.payload
    solicitacao_id = UUID(payload["solicitacao_id"])
    agendamento_id = UUID(payload["agendamento_id"]) if payload.get("agendamento_id") else None
    _, usuario_id, email = _destinatario(session, solicitacao_id)
    avisos = montar_avisos(
        evento.tipo_evento,
        _contexto(session, agendamento_id),
        com_email=email is not None,  # finalidade AGENDAMENTO (data-protection.md)
        link=cfg.app_url_publica,
        fuso=ZoneInfo(cfg.timezone_exibicao),
    )
    # ADR-006: o mesmo evento duas vezes não duplica (uq_notificacao_outbox_usuario_canal).
    session.execute(
        insert(Notificacao)
        .values(
            _linhas(
                avisos,
                agora,
                usuario_id=usuario_id,
                solicitacao_id=solicitacao_id,
                agendamento_id=agendamento_id,
                outbox_id=evento.id,
                tipo=evento.tipo_evento,
            )
        )
        .on_conflict_do_nothing(constraint="uq_notificacao_outbox_usuario_canal")
    )


# --- enviar_emails ------------------------------------------------------------------------


def emails_pendentes(session: Session, agora: datetime, limite: int) -> list[UUID]:
    return list(
        session.scalars(
            select(Notificacao.id)
            .where(
                Notificacao.canal == "EMAIL",
                Notificacao.status_envio == "PENDENTE",
                Notificacao.proximo_retry_em <= agora,
            )
            .order_by(Notificacao.proximo_retry_em, Notificacao.id)
            .limit(limite)
        )
    )


def enviar_email(
    session: Session,
    notificacao_id: UUID,
    agora: datetime,
    canal: CanalNotificacao,
    cfg: Settings,
) -> bool:
    """Envia pelo canal. Falha → nova tentativa com espera crescente, até FALHOU.

    O lembrete é conferido de novo na hora: agendamento ainda CONFIRMADO e `LEMBRETE_EMAIL`
    vigente; senão, CANCELADA. Pelo menos uma vez: se o Worker cair depois de enviar e antes
    do commit, o e-mail sai de novo na próxima rodada.
    """
    n = session.scalar(
        select(Notificacao)
        .where(
            Notificacao.id == notificacao_id,
            Notificacao.canal == "EMAIL",
            Notificacao.status_envio == "PENDENTE",
            Notificacao.proximo_retry_em <= agora,
        )
        .with_for_update(skip_locked=True)
    )
    if n is None:
        return False
    paciente_id, email = session.execute(
        select(Paciente.id, Usuario.email)
        .join(Paciente, Paciente.usuario_id == Usuario.id)
        .where(Usuario.id == n.usuario_id)
    ).one()
    if email is None or (n.tipo == TIPO_LEMBRETE and not _lembrete_vale(session, n, paciente_id)):
        n.status_envio = "CANCELADA"
        logger.info("enviar_emails: notificacao %s cancelada", n.id)
        return False
    try:
        canal.enviar(Mensagem(destino=email, assunto=n.titulo, corpo=n.corpo))
    except Exception as exc:
        n.tentativas += 1
        proxima = proxima_tentativa(n.tentativas, cfg.outbox_max_tentativas, agora)
        if proxima is None:
            n.status_envio = "FALHOU"
        else:
            n.proximo_retry_em = proxima
        logger.error(
            "enviar_emails: notificacao %s falhou (tentativa %d): %s",
            n.id,
            n.tentativas,
            resumo_do_erro(exc),
        )
        return False
    n.status_envio = "ENVIADA"
    n.enviada_em = agora
    return True


def _lembrete_vale(session: Session, n: Notificacao, paciente_id: UUID) -> bool:
    # Sem trava: cancelamento gravado logo depois desta leitura ainda deixa sair o e-mail
    # (pelo menos uma vez, aceito no SDD).
    confirmado = session.scalar(
        select(
            exists().where(Agendamento.id == n.agendamento_id, Agendamento.status == "CONFIRMADO")
        )
    )
    return bool(confirmado) and _consentiu_lembrete(session, paciente_id)


# --- enviar_lembretes ---------------------------------------------------------------------


def agendamentos_para_lembrar(
    session: Session, agora: datetime, horas: int, limite: int
) -> list[UUID]:
    """CONFIRMADO, com início entre agora e agora + `horas`, ainda sem lembrete."""
    return list(
        session.scalars(
            select(Agendamento.id)
            .join(Vaga, Vaga.id == Agendamento.vaga_id)
            .where(
                Agendamento.status == "CONFIRMADO",
                Vaga.inicio > agora,
                Vaga.inicio <= agora + timedelta(hours=horas),
                ~exists().where(
                    Notificacao.agendamento_id == Agendamento.id,
                    Notificacao.tipo == TIPO_LEMBRETE,
                ),
            )
            .order_by(Vaga.inicio, Agendamento.id)
            .limit(limite)
        )
    )


def criar_lembrete(session: Session, agendamento_id: UUID, agora: datetime, cfg: Settings) -> bool:
    """Lembrete no site sempre; por e-mail só com e-mail cadastrado e `LEMBRETE_EMAIL` (RN-009).

    Trava para leitura (`FOR SHARE SKIP LOCKED`) na ordem das rotas: solicitação, depois
    agendamento. Ordem inversa travaria com o cancelamento, porque o INSERT do aviso pede
    `KEY SHARE` na solicitação pela FK. Cancelamento em curso: o item fica para a próxima
    rodada; se o agendamento mudar depois, o `enviar_emails` cancela o e-mail.
    """
    s = session.scalar(
        select(Solicitacao.id)
        .where(
            Solicitacao.id
            == select(Agendamento.solicitacao_id)
            .where(Agendamento.id == agendamento_id)
            .scalar_subquery()
        )
        .with_for_update(read=True, skip_locked=True)
    )
    a = (
        session.scalar(
            select(Agendamento)
            .where(Agendamento.id == agendamento_id, Agendamento.status == "CONFIRMADO")
            .with_for_update(read=True, skip_locked=True)
        )
        if s
        else None
    )
    if a is None:
        return False
    paciente_id, usuario_id, email = _destinatario(session, a.solicitacao_id)
    avisos = montar_avisos(
        TIPO_LEMBRETE,
        _contexto(session, a.id),
        com_email=email is not None and _consentiu_lembrete(session, paciente_id),
        link=cfg.app_url_publica,
        fuso=ZoneInfo(cfg.timezone_exibicao),
    )
    resultado = session.execute(
        insert(Notificacao)
        .values(
            _linhas(
                avisos,
                agora,
                usuario_id=usuario_id,
                solicitacao_id=a.solicitacao_id,
                agendamento_id=a.id,
                tipo=TIPO_LEMBRETE,
            )
        )
        .on_conflict_do_nothing(
            index_elements=["agendamento_id", "tipo", "canal"],
            index_where=text("tipo = 'LEMBRETE'"),
        )
        .returning(Notificacao.id)  # rowcount não vale em insert de várias linhas
    )
    return bool(resultado.all())
