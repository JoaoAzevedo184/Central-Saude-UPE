"""Configuração de logs.

Nunca registre nome, CPF, e-mail, telefone nem corpo de requisição: use IDs.
"""

import logging


def configurar_logging(nivel: str) -> None:
    logging.basicConfig(
        level=nivel,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        force=True,
    )
