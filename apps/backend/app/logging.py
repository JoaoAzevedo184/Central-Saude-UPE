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


def resumo_do_erro(exc: BaseException) -> str:
    """Tipo da exceção e SQLSTATE, nunca a mensagem nem o traceback.

    A mensagem do Postgres pode repetir valores (ex.: "Key (cpf)=(...) already exists").
    """
    sqlstate = getattr(getattr(exc, "orig", None), "sqlstate", None)
    return f"{type(exc).__name__} sqlstate={sqlstate}" if sqlstate else type(exc).__name__
