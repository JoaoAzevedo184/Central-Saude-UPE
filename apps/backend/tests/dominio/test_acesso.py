from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from app.dominio.acesso import (
    calcular_escopo,
    normalizar_identificador,
    pode_autenticar,
    refresh_na_tolerancia,
    tentativas_esgotadas,
    verificar_reativacao,
    verificar_suspensao,
)
from app.dominio.erros import OperacaoNaoPermitida, TransicaoInvalida

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


A, B = UUID(int=900), UUID(int=901)


def test_adr028_nao_suspende_a_si_mesmo():
    with pytest.raises(OperacaoNaoPermitida):
        verificar_suspensao(A, A, "ADMIN", "ATIVO", admins_ativos=3)


def test_adr028_nao_suspende_o_ultimo_admin_ativo():
    # Só acontece com dois admins suspendendo um ao outro ao mesmo tempo: a rota trava as
    # linhas e o segundo vê só um admin ativo.
    with pytest.raises(OperacaoNaoPermitida):
        verificar_suspensao(A, B, "ADMIN", "ATIVO", admins_ativos=1)
    verificar_suspensao(A, B, "ADMIN", "ATIVO", admins_ativos=2)


def test_adr028_so_suspende_conta_da_equipe_ativa():
    with pytest.raises(OperacaoNaoPermitida):
        verificar_suspensao(A, B, "PACIENTE", "ATIVO", admins_ativos=1)
    with pytest.raises(TransicaoInvalida):
        verificar_suspensao(A, B, "ATENDENTE", "SUSPENSO", admins_ativos=1)
    verificar_suspensao(A, B, "ATENDENTE", "ATIVO", admins_ativos=1)


def test_adr028_reativar_exige_suspenso():
    with pytest.raises(TransicaoInvalida):
        verificar_reativacao("ATIVO")
    verificar_reativacao("SUSPENSO")


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        ("123.456.789-09", ("CPF", "12345678909")),
        (" 12345678909 ", ("CPF", "12345678909")),
        ("Admin@Exemplo.com ", ("EMAIL", "admin@exemplo.com")),
    ],
)
def test_adr003_identificador_do_login(valor, esperado):
    assert normalizar_identificador(valor) == esperado


def test_am004_tentativas_esgotadas_ao_atingir_o_maximo():
    assert not tentativas_esgotadas(4, 5)
    assert tentativas_esgotadas(5, 5)


def test_adr003_refresh_na_tolerancia():
    revogado = datetime(2026, 10, 19, 12, tzinfo=UTC)
    dez = timedelta(seconds=10)

    assert refresh_na_tolerancia(revogado, True, False, revogado + timedelta(seconds=9), dez)
    assert not refresh_na_tolerancia(revogado, True, False, revogado + dez, dez)
    assert not refresh_na_tolerancia(revogado, False, False, revogado, dez)  # logout
    assert not refresh_na_tolerancia(revogado, True, True, revogado, dez)  # 2ª reapresentação
