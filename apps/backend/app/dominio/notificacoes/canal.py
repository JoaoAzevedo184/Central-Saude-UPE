"""Interface do canal de envio (ADR-010). Implementação SMTP em app/infra/email.py.

O aviso no site não passa por aqui: ele é a própria linha de `notificacao`.
"""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Mensagem:
    destino: str  # endereço de e-mail: nunca vai para o log
    assunto: str
    corpo: str


class CanalNotificacao(Protocol):
    """Entrega uma mensagem ou levanta exceção. Quem chama cuida das novas tentativas."""

    def enviar(self, mensagem: Mensagem) -> None: ...
