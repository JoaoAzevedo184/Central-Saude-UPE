from datetime import UTC, date, datetime
from uuid import UUID

import pytest

from app.dominio.fila.ordenacao import RegraPrioridade, SolicitacaoNaFila, ordenar_fila

CRIADA = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
REGRAS_MVP = [
    RegraPrioridade("CLASSIFICACAO_RISCO", 1),
    RegraPrioridade("PRIORIDADE_LEGAL", 2),
    RegraPrioridade("DATA_PEDIDO", 3),
]


def sol(n, risco="VERDE", prioridade=None, pedido=date(2026, 9, 1), criada=CRIADA):
    return SolicitacaoNaFila(UUID(int=n), risco, prioridade, pedido, criada)


def ids(fila):
    return [s.id.int for s in fila]


def test_rn006_classificacao_risco_vermelho_amarelo_verde_azul():
    fila = [sol(1, "AZUL"), sol(2, "VERDE"), sol(3, "VERMELHO"), sol(4, "AMARELO")]

    assert ids(ordenar_fila(fila, [RegraPrioridade("CLASSIFICACAO_RISCO", 1)])) == [3, 4, 2, 1]


def test_rn006_prioridade_legal_antes_de_sem_prioridade():
    fila = [sol(1), sol(2, prioridade="GESTANTE"), sol(3)]

    assert ids(ordenar_fila(fila, [RegraPrioridade("PRIORIDADE_LEGAL", 1)])) == [2, 1, 3]


def test_rn006_data_pedido_mais_antigo_primeiro():
    fila = [sol(1, pedido=date(2026, 9, 3)), sol(2, pedido=date(2026, 9, 1))]

    assert ids(ordenar_fila(fila, [RegraPrioridade("DATA_PEDIDO", 1)])) == [2, 1]


def test_rn006_combina_os_tres_criterios_na_ordem_das_regras():
    fila = [
        sol(1, "VERDE", None, date(2026, 8, 1)),
        sol(2, "VERDE", "IDOSO", date(2026, 9, 1)),
        sol(3, "VERMELHO", None, date(2026, 9, 5)),
        sol(4, "VERDE", "IDOSO", date(2026, 8, 15)),
        sol(5, "AMARELO", None, date(2026, 7, 1)),
    ]

    # Regras fora de ordem na lista: vale o campo `ordem`.
    assert ids(ordenar_fila(fila, list(reversed(REGRAS_MVP)))) == [3, 5, 4, 2, 1]


def test_rn006_desempate_por_criada_em_e_depois_por_id():
    depois = datetime(2026, 10, 2, tzinfo=UTC)
    fila = [sol(3, criada=depois), sol(2), sol(1)]

    assert ids(ordenar_fila(fila, REGRAS_MVP)) == [1, 2, 3]
    assert ids(ordenar_fila(list(reversed(fila)), REGRAS_MVP)) == [1, 2, 3]


def test_rn006_regra_inativa_e_ignorada():
    fila = [sol(1, "AZUL", pedido=date(2026, 8, 1)), sol(2, "VERMELHO", pedido=date(2026, 9, 1))]
    regras = [
        RegraPrioridade("CLASSIFICACAO_RISCO", 1, ativa=False),
        RegraPrioridade("DATA_PEDIDO", 2),
    ]

    assert ids(ordenar_fila(fila, regras)) == [1, 2]


def test_rn006_sem_regras_ativas_ordena_por_criada_em_e_id():
    fila = [sol(2, "VERMELHO"), sol(1, "AZUL")]

    assert ids(ordenar_fila(fila, [])) == [1, 2]


def test_rn006_criterio_desconhecido_levanta_value_error():
    with pytest.raises(ValueError, match="AGING"):
        ordenar_fila([sol(1)], [RegraPrioridade("AGING", 1)])


def test_rn006_classificacao_risco_desconhecida_levanta_value_error():
    with pytest.raises(ValueError, match="ROXO"):
        ordenar_fila([sol(1, "ROXO")], [RegraPrioridade("CLASSIFICACAO_RISCO", 1)])
