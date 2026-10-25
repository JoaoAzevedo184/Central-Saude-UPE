"""Transições do agendamento (business-rules.md, ciclo de vida do agendamento)."""

from dataclasses import dataclass, replace
from datetime import datetime
from uuid import UUID

from app.dominio.agendamento.prazos import pode_marcar_falta
from app.dominio.erros import PropostaExpirada, ToleranciaNaoEncerrada, TransicaoInvalida


@dataclass(frozen=True)
class Agendamento:
    id: UUID
    status: str
    expira_em: datetime
    respondido_em: datetime | None = None
    motivo_cancelamento: str | None = None
    confirmado_em: datetime | None = None


def _exigir_proposta_no_prazo(agendamento: Agendamento, agora: datetime) -> None:
    if agendamento.status != "PROPOSTO":
        raise TransicaoInvalida("A proposta não está mais aguardando resposta.")
    # UC-004: o prazo é conferido aqui, sem depender de o Worker já ter expirado a proposta.
    if agora >= agendamento.expira_em:
        raise PropostaExpirada(
            "O prazo para responder acabou. Sua solicitação volta para o fim da fila."
        )


def confirmar(agendamento: Agendamento, agora: datetime) -> Agendamento:
    """PROPOSTO → CONFIRMADO, só antes de `expira_em` (UC-004)."""
    _exigir_proposta_no_prazo(agendamento, agora)
    return replace(agendamento, status="CONFIRMADO", respondido_em=agora, confirmado_em=agora)


def recusar(agendamento: Agendamento, agora: datetime) -> Agendamento:
    """PROPOSTO → CANCELADO com `RECUSADO_PELO_PACIENTE` (UC-005), só antes de `expira_em`."""
    _exigir_proposta_no_prazo(agendamento, agora)
    return replace(
        agendamento,
        status="CANCELADO",
        respondido_em=agora,
        motivo_cancelamento="RECUSADO_PELO_PACIENTE",
    )


def expirar(agendamento: Agendamento, agora: datetime) -> Agendamento:
    """PROPOSTO → EXPIRADO quando `expira_em <= agora` (UC-006)."""
    if agendamento.status != "PROPOSTO" or agora < agendamento.expira_em:
        raise TransicaoInvalida("A proposta não está vencida.")
    return replace(agendamento, status="EXPIRADO")


def cancelar_pelo_paciente(
    agendamento: Agendamento, vaga_inicio: datetime, agora: datetime
) -> Agendamento:
    """PROPOSTO ou CONFIRMADO → CANCELADO com `CANCELADO_PELO_PACIENTE`, só antes do início
    da vaga. A vaga fica livre para o próximo da fila (RN-005)."""
    if agendamento.status not in ("PROPOSTO", "CONFIRMADO"):
        raise TransicaoInvalida("O agendamento não pode mais ser cancelado.")
    if agora >= vaga_inicio:
        raise TransicaoInvalida("A consulta já começou e não pode mais ser cancelada.")
    return replace(
        agendamento,
        status="CANCELADO",
        respondido_em=agendamento.respondido_em or agora,
        motivo_cancelamento="CANCELADO_PELO_PACIENTE",
    )


def registrar_presenca(
    agendamento: Agendamento,
    compareceu: bool,
    vaga_inicio: datetime,
    tolerancia_atraso_min: int,
    agora: datetime,
) -> Agendamento:
    """CONFIRMADO → REALIZADO (a partir do início da vaga) ou FALTOU (só depois da
    tolerância, `pode_marcar_falta`, RN-013)."""
    if agendamento.status != "CONFIRMADO":
        raise TransicaoInvalida("Só se registra presença de consulta confirmada.")
    if compareceu:
        if agora < vaga_inicio:
            raise TransicaoInvalida("A consulta ainda não começou.")
        return replace(agendamento, status="REALIZADO")
    if not pode_marcar_falta(vaga_inicio, agora, tolerancia_atraso_min):
        raise ToleranciaNaoEncerrada("A tolerância de atraso ainda não acabou.")
    return replace(agendamento, status="FALTOU")
