"""Implementações de `app.dominio.relogio.Relogio` (ADR-008)."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


class RelogioReal:
    def agora(self) -> datetime:
        return datetime.now(UTC)


@dataclass
class RelogioFixo:
    """Relógio parado, para testes. Só aceita datetime com fuso."""

    instante: datetime

    def __post_init__(self) -> None:
        if self.instante.tzinfo is None:
            raise ValueError("RelogioFixo exige datetime com fuso")

    def agora(self) -> datetime:
        return self.instante

    def avancar(self, delta: timedelta) -> None:
        self.instante += delta
