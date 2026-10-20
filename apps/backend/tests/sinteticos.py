"""Documentos fictícios para os testes. Nunca use CPF ou cartão do SUS de pessoas reais."""

from app.dominio.cadastro import cpf_com_digitos


def _pesos(cns: str) -> int:
    return sum(int(d) * (15 - i) for i, d in enumerate(cns))


def cpf(base: str) -> str:
    """CPF válido e fictício a partir de 9 dígitos."""
    return cpf_com_digitos(base)


def cns_definitivo(pis: str) -> str:
    """Cartão do SUS definitivo (começa com 1 ou 2) a partir de 11 dígitos fictícios.

    Construído pela propriedade da soma ponderada (múltipla de 11), independente do código.
    """
    for meio in ("000", "001"):
        for dv in range(10):
            if _pesos(candidato := f"{pis}{meio}{dv}") % 11 == 0:
                return candidato
    raise ValueError(pis)


def cns_provisorio(base: str) -> str:
    """Cartão do SUS provisório (7, 8 ou 9) a partir de 14 dígitos fictícios."""
    for troca in range(10):
        inicio = base[:-1] + str(troca)
        if (dv := -_pesos(inicio) % 11) < 10:
            return inicio + str(dv)
    raise ValueError(base)
