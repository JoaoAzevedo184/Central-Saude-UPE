from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from app.dominio.fila.elegibilidade import (
    MOTIVO_DADO_AUSENTE,
    MOTIVO_IDADE,
    MOTIVO_SEXO,
    DadosPaciente,
    RestricoesFila,
    idade_em_anos,
    motivo_inelegivel,
    verificar_elegibilidade,
)
from app.infra.relogio import RelogioFixo

RECIFE = ZoneInfo("America/Recife")
HOJE = date(2026, 10, 19)
LAQUEADURA = RestricoesFila(sexo_elegivel="FEMININO", idade_minima=18)
FAIXA_40_69 = RestricoesFila(idade_minima=40, idade_maxima=69)


def paciente(sexo="FEMININO", nascimento=date(1990, 1, 1)):
    return DadosPaciente(sexo, nascimento)


def test_adr027_fila_sem_restricao_aceita_qualquer_paciente():
    assert verificar_elegibilidade(paciente(None, None), RestricoesFila(), HOJE)
    assert verificar_elegibilidade(paciente("MASCULINO"), RestricoesFila(), HOJE)


def test_adr027_sexo_diferente_do_elegivel_e_recusado():
    assert verificar_elegibilidade(paciente("FEMININO"), LAQUEADURA, HOJE)
    assert not verificar_elegibilidade(paciente("MASCULINO"), LAQUEADURA, HOJE)


def test_adr027_sem_sexo_e_inelegivel_se_a_fila_restringe_sexo():
    assert not verificar_elegibilidade(paciente(sexo=None), LAQUEADURA, HOJE)


def test_adr027_sem_nascimento_e_inelegivel_se_a_fila_restringe_idade():
    assert not verificar_elegibilidade(paciente(nascimento=None), LAQUEADURA, HOJE)
    assert not verificar_elegibilidade(paciente(nascimento=None), FAIXA_40_69, HOJE)


@pytest.mark.parametrize(
    ("nascimento", "elegivel"),
    [
        (date(1986, 10, 19), True),  # faz 40 hoje: limite mínimo inclusivo
        (date(1986, 10, 20), False),  # faz 40 amanhã: ainda tem 39
        (date(1956, 10, 20), True),  # 69 anos completos: limite máximo inclusivo
        (date(1956, 10, 19), False),  # faz 70 hoje
    ],
)
def test_adr027_idade_em_anos_completos_com_limites_inclusivos(nascimento, elegivel):
    assert verificar_elegibilidade(paciente(nascimento=nascimento), FAIXA_40_69, HOJE) is elegivel


def test_adr027_nascido_em_29_de_fevereiro():
    assert idade_em_anos(date(2008, 2, 29), date(2026, 2, 28)) == 17
    assert idade_em_anos(date(2008, 2, 29), date(2026, 3, 1)) == 18


def test_adr027_hoje_vem_do_relogio_no_fuso_de_recife():
    # 01:30 UTC de 20/10 ainda é 19/10 em Recife: a paciente ainda não fez 18 anos.
    relogio = RelogioFixo(datetime.fromisoformat("2026-10-20T01:30:00+00:00"))
    hoje = relogio.agora().astimezone(RECIFE).date()

    assert not verificar_elegibilidade(paciente(nascimento=date(2008, 10, 20)), LAQUEADURA, hoje)


def test_adr027_nascimento_no_futuro_e_inelegivel():
    so_maxima = RestricoesFila(idade_maxima=12)

    assert not verificar_elegibilidade(paciente(nascimento=date(2027, 1, 1)), so_maxima, HOJE)


def test_rn017_motivo_inelegivel_diz_o_porque():
    assert motivo_inelegivel(paciente("MASCULINO"), LAQUEADURA, HOJE) == MOTIVO_SEXO
    assert motivo_inelegivel(paciente(sexo=None), LAQUEADURA, HOJE) == MOTIVO_DADO_AUSENTE
    # Sem data de nascimento: o banco exige a data (0002); a regra falha fechada mesmo assim.
    assert motivo_inelegivel(paciente(nascimento=None), FAIXA_40_69, HOJE) == MOTIVO_DADO_AUSENTE
    assert (
        motivo_inelegivel(paciente(nascimento=date(2000, 1, 1)), FAIXA_40_69, HOJE) == MOTIVO_IDADE
    )
    assert (
        motivo_inelegivel(paciente(nascimento=date(1950, 1, 1)), FAIXA_40_69, HOJE) == MOTIVO_IDADE
    )
    assert motivo_inelegivel(paciente(), LAQUEADURA, HOJE) is None
