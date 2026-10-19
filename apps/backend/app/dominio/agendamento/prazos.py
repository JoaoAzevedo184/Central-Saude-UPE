"""Prazos da proposta e do comparecimento (ADR-021, ADR-026, RN-008)."""

from datetime import datetime, timedelta


def calcular_expira_em(
    proposto_em: datetime,
    vaga_inicio: datetime,
    prazo_confirmacao_horas: int,
    antecedencia_minima_horas: int,
    *,
    janela_minima_horas: int,
) -> datetime | None:
    """Fim do prazo para o paciente confirmar a vaga.

    É o menor entre `proposto_em + prazo da fila` e `vaga_inicio − antecedência mínima`.
    Se sobrar menos de `janela_minima_horas` (PROPOSTA_JANELA_MINIMA_HORAS) para o paciente
    responder, devolve `None`: a vaga não é proposta e fica livre no painel (ADR-021).
    """
    expira_em = min(
        proposto_em + timedelta(hours=prazo_confirmacao_horas),
        vaga_inicio - timedelta(hours=antecedencia_minima_horas),
    )
    if expira_em <= proposto_em or expira_em - proposto_em < timedelta(hours=janela_minima_horas):
        return None
    return expira_em


def pode_marcar_falta(vaga_inicio: datetime, agora: datetime, tolerancia_atraso_min: int) -> bool:
    """A falta só pode ser registrada depois de esgotada a tolerância de atraso (ADR-026)."""
    return agora > vaga_inicio + timedelta(minutes=tolerancia_atraso_min)
