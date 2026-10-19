from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from app.dominio.fila.ordenacao import ordenar_fila
from app.dominio.solicitacao import Solicitacao

CHEGADA = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)


def sol(n, risco="VERDE", nota=0, chegada=CHEGADA):
    return Solicitacao(UUID(int=n), "NA_FILA", risco, nota, chegada)


def ids(fila):
    return [s.id.int for s in fila]


def test_adr024_risco_vermelho_amarelo_verde():
    fila = [sol(1, "VERDE"), sol(2, "VERMELHO"), sol(3, "AMARELO")]

    assert ids(ordenar_fila(fila)) == [2, 3, 1]


def test_adr024_risco_vem_antes_da_nota():
    fila = [sol(1, "AMARELO", nota=100), sol(2, "VERMELHO", nota=0)]

    assert ids(ordenar_fila(fila)) == [2, 1]


def test_adr024_mesmo_risco_maior_nota_primeiro():
    fila = [sol(1, nota=10), sol(2, nota=30), sol(3, nota=20)]

    assert ids(ordenar_fila(fila)) == [2, 3, 1]


def test_adr024_empate_resolvido_pela_hora_de_chegada():
    fila = [sol(1, chegada=CHEGADA + timedelta(minutes=5)), sol(2), sol(3, nota=5)]

    assert ids(ordenar_fila(fila)) == [3, 2, 1]


def test_adr024_empate_total_ordena_por_id_de_forma_deterministica():
    fila = [sol(3), sol(1), sol(2)]

    assert ids(ordenar_fila(fila)) == ids(ordenar_fila(reversed(fila))) == [1, 2, 3]


def test_adr026_reentrada_vai_para_o_fim_entre_iguais():
    antiga = sol(1, chegada=CHEGADA)
    reentrou = sol(2, chegada=CHEGADA + timedelta(days=3))

    assert ids(ordenar_fila([reentrou, antiga])) == [1, 2]


@pytest.mark.parametrize("risco", ["AZUL", None])
def test_adr024_risco_invalido_levanta_value_error(risco):
    with pytest.raises(ValueError, match="risco"):
        ordenar_fila([sol(1, risco)])


def test_adr024_sem_hora_de_chegada_levanta_value_error():
    with pytest.raises(ValueError, match="entrada na fila"):
        ordenar_fila([sol(1, chegada=None)])
