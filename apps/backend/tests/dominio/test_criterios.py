import pytest

from app.dominio.fila.criterios import Criterio, calcular_nota, calcular_pontos

FILHOS = Criterio(
    "NUM_FILHOS",
    "NUMERO",
    10,
    {
        "faixas": [
            {"min": 0, "max": 1, "fator": 0},
            {"min": 2, "max": 3, "fator": 1},
            {"min": 4, "fator": 2},
        ]
    },
)
NEURO = Criterio("FILHO_NEURODEGENERATIVA", "SIM_NAO", 20)
GRAVIDADE = Criterio("GRAVIDADE", "OPCAO", 5, {"opcoes": {"LEVE": 0, "GRAVE": 3}})


def test_adr024_sim_vale_o_peso_nao_vale_zero():
    assert calcular_pontos(NEURO, True) == 20
    assert calcular_pontos(NEURO, False) == 0


@pytest.mark.parametrize(("valor", "pontos"), [(0, 0), (1, 0), (2, 10), (3, 10), (4, 20), (9, 20)])
def test_adr024_numero_vale_peso_vezes_fator_da_faixa(valor, pontos):
    assert calcular_pontos(FILHOS, valor) == pontos


def test_adr024_numero_fora_de_todas_as_faixas_vale_zero():
    assert calcular_pontos(FILHOS, -1) == 0


def test_adr024_opcao_vale_peso_vezes_fator():
    assert calcular_pontos(GRAVIDADE, "GRAVE") == 15
    assert calcular_pontos(GRAVIDADE, "LEVE") == 0


@pytest.mark.parametrize(
    ("criterio", "valor"),
    [
        (NEURO, "sim"),
        (NEURO, 1),
        (FILHOS, True),
        (FILHOS, "3"),
        (GRAVIDADE, "MEDIA"),
        (GRAVIDADE, 1),
    ],
)
def test_adr024_valor_do_tipo_errado_levanta_value_error(criterio, valor):
    with pytest.raises(ValueError, match=criterio.codigo):
        calcular_pontos(criterio, valor)


def test_adr024_tipo_desconhecido_levanta_value_error():
    with pytest.raises(ValueError, match="tipo"):
        calcular_pontos(Criterio("X", "DATA", 1), "2026-01-01")


def test_adr024_nota_e_a_soma_dos_pontos():
    assert calcular_nota([(FILHOS, 4), (NEURO, True), (GRAVIDADE, "LEVE")]) == 40
    assert calcular_nota([]) == 0


@pytest.mark.parametrize("fator", [None, 1.5, -1, True])
def test_adr024_fator_invalido_levanta_value_error(fator):
    faixa = {"min": 0} if fator is None else {"min": 0, "fator": fator}
    criterio = Criterio("X", "NUMERO", 10, {"faixas": [faixa]})

    with pytest.raises(ValueError, match="fator"):
        calcular_pontos(criterio, 5)
