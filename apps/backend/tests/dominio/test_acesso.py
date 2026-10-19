from uuid import UUID

import pytest

from app.dominio.acesso import calcular_escopo, pode_autenticar

CISAM, HUOC = UUID(int=100), UUID(int=200)
F1, F2, F3 = UUID(int=1), UUID(int=2), UUID(int=3)
UNIDADE_DA_FILA = {F1: CISAM, F2: CISAM, F3: HUOC}
NADA: frozenset[UUID] = frozenset()


def escopo(papel, filas=NADA, unidades=NADA, situacao="ATIVO"):
    return calcular_escopo(papel, situacao, filas, unidades, UNIDADE_DA_FILA)


def test_adr025_admin_ve_todas_as_filas():
    assert escopo("ADMIN") == {F1, F2, F3}


def test_adr025_gestor_sem_unidade_ve_a_central_inteira():
    assert escopo("GESTOR") == {F1, F2, F3}


def test_adr025_gestor_de_hospital_ve_as_filas_do_hospital():
    assert escopo("GESTOR", unidades=frozenset({CISAM})) == {F1, F2}


def test_adr025_atendente_ve_so_as_filas_atribuidas():
    assert escopo("ATENDENTE", filas=frozenset({F3})) == {F3}


def test_adr025_atendente_sem_atribuicao_nao_ve_nada():
    assert escopo("ATENDENTE") == NADA


def test_adr025_atendente_ignora_lotacao_por_unidade():
    assert escopo("ATENDENTE", unidades=frozenset({CISAM})) == NADA


def test_adr025_paciente_nao_tem_escopo_de_equipe():
    assert escopo("PACIENTE", filas=frozenset({F1})) == NADA


@pytest.mark.parametrize("papel", ["ADMIN", "GESTOR", "ATENDENTE"])
def test_adr028_suspenso_nao_ve_nada(papel):
    assert escopo(papel, filas=frozenset({F1}), situacao="SUSPENSO") == NADA


def test_adr028_suspenso_nao_autentica():
    assert pode_autenticar("ATIVO")
    assert not pode_autenticar("SUSPENSO")
