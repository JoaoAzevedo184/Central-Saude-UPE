"""Interface do relógio (ADR-008). Implementações em app/infra/relogio.py."""

from datetime import datetime
from typing import Protocol


class Relogio(Protocol):
    """Fonte única de "agora", sempre com fuso. Nada de datetime.now() solto no código."""

    def agora(self) -> datetime: ...
