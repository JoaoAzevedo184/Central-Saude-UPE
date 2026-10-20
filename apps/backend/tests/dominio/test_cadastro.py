from datetime import date

import pytest

from app.dominio.cadastro import cns_valido, cpf_valido, erro_data_nascimento
from tests.sinteticos import cns_definitivo, cns_provisorio, cpf

HOJE = date(2026, 10, 19)


def test_uc001_cpf_com_digitos_corretos_e_valido():
    assert cpf_valido(cpf("123456789"))


@pytest.mark.parametrize("valor", ["12345678900", "11111111111", "1234567890", "1234567890a"])
def test_uc001_cpf_invalido(valor):
    assert not cpf_valido(valor)


@pytest.mark.parametrize(
    "valor",
    [
        cns_definitivo("10000000001"),
        cns_definitivo("20000000002"),
        cns_definitivo("12345678901"),
        cns_provisorio("70000000000000"),
        cns_provisorio("89999999999999"),
    ],
)
def test_uc001_cns_definitivo_e_provisorio_validos(valor):
    assert cns_valido(valor)


def test_uc001_cns_invalido():
    bom = cns_definitivo("12345678901")
    assert not cns_valido(bom[:-1] + str((int(bom[-1]) + 1) % 10))
    assert not cns_valido("3" + bom[1:])  # 3 a 6 não existem
    assert not cns_valido(bom[:-1])


def test_uc001_data_de_nascimento():
    assert erro_data_nascimento(date(1990, 1, 1), HOJE) is None
    assert erro_data_nascimento(HOJE, HOJE) is None
    assert "futuro" in erro_data_nascimento(date(2026, 10, 20), HOJE)
    assert erro_data_nascimento(date(1896, 10, 19), HOJE) is None  # 130 anos
    assert "130" in erro_data_nascimento(date(1895, 10, 19), HOJE)
