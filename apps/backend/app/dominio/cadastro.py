"""Validação dos documentos e da data de nascimento no cadastro do paciente (UC-001)."""

from datetime import date

from app.dominio.fila.elegibilidade import idade_em_anos

IDADE_MAXIMA = 130


def cpf_com_digitos(base: str) -> str:
    """CPF completo a partir dos 9 primeiros dígitos (calcula os dois verificadores)."""
    digitos = [int(d) for d in base]
    for tamanho in (9, 10):
        soma = sum(d * (tamanho + 1 - i) for i, d in enumerate(digitos[:tamanho]))
        digitos.append(0 if soma % 11 < 2 else 11 - soma % 11)
    return "".join(map(str, digitos))


def cpf_valido(cpf: str) -> bool:
    """11 dígitos, verificadores corretos e não todos iguais (111.111.111-11 passa no cálculo)."""
    return (
        len(cpf) == 11 and cpf.isdigit() and len(set(cpf)) > 1 and cpf_com_digitos(cpf[:9]) == cpf
    )


def cns_valido(cns: str) -> bool:
    """Cartão do SUS: definitivo (começa com 1 ou 2) ou provisório (7, 8 ou 9)."""
    if len(cns) != 15 or not cns.isdigit():
        return False
    if cns[0] in "789":
        return sum(int(d) * (15 - i) for i, d in enumerate(cns)) % 11 == 0
    if cns[0] not in "12":
        return False
    # Definitivo: os 11 primeiros dígitos (PIS) geram o resto do número.
    pis = cns[:11]
    soma = sum(int(d) * (15 - i) for i, d in enumerate(pis))
    dv = 11 - soma % 11
    if dv == 11:
        dv = 0
    if dv == 10:
        dv = 11 - (soma + 2) % 11
        return cns == f"{pis}001{dv}"
    return cns == f"{pis}000{dv}"


def erro_data_nascimento(data_nascimento: date, hoje: date) -> str | None:
    """Mensagem de erro, ou None se a data é aceitável."""
    if data_nascimento > hoje:
        return "A data de nascimento não pode estar no futuro."
    if idade_em_anos(data_nascimento, hoje) > IDADE_MAXIMA:
        return f"A idade não pode passar de {IDADE_MAXIMA} anos."
    return None
