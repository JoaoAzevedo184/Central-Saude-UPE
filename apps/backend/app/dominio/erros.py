"""Erros de domínio. A API traduz para Problem Details (RFC 9457).

A mensagem vai para o cliente: nunca coloque dados pessoais nela.
"""


class ErroDeDominio(Exception):
    """Regra de negócio violada. Responde 409."""

    tipo = "/problemas/erro-de-dominio"


class TransicaoInvalida(ErroDeDominio):
    """Estado de origem não permite a transição pedida. Responde 409."""

    tipo = "/problemas/transicao-invalida"
