import re
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from app.dominio.erros import EntradaInvalida, TransicaoInvalida
from app.dominio.solicitacao import (
    MOTIVOS_CANCELAMENTO,
    MOTIVOS_REENTRADA,
    Solicitacao,
    cancelar,
    classificar,
    recalcular_nota,
    reentrar_no_fim_da_fila,
)
from app.infra.relogio import RelogioFixo

CHEGADA = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)


def sol(status):
    return Solicitacao(UUID(int=1), status, "AMARELO", 25, CHEGADA)


@pytest.mark.parametrize(
    ("motivo", "origem", "trecho"),
    [
        ("PROPOSTA_EXPIRADA", "EM_PROPOSTA", "não confirmou a vaga no prazo"),
        ("FALTOU", "AGENDADA", "não compareceu à consulta"),
    ],
)
def test_adr026_reentra_no_fim_da_fila_com_motivo(motivo, origem, trecho):
    relogio = RelogioFixo(datetime(2026, 10, 19, 9, 0, tzinfo=UTC))

    nova, evento = reentrar_no_fim_da_fila(sol(origem), relogio.agora(), motivo)

    assert nova.status == "NA_FILA"
    assert nova.data_entrada_fila == relogio.agora()  # fim da fila = nova hora de chegada
    assert (nova.classificacao_risco, nova.nota) == ("AMARELO", 25)
    assert evento.tipo == "REENTROU_NA_FILA"
    assert (evento.status_anterior, evento.status_novo) == (origem, "NA_FILA")
    assert evento.visivel_paciente is True
    assert trecho in evento.motivo


def test_adr007_texto_para_o_paciente_nunca_cita_posicao_nem_tamanho():
    for _, texto in MOTIVOS_REENTRADA.values():
        assert not re.search(r"\d|posi|lugar|frente|pessoas", texto, re.IGNORECASE)


@pytest.mark.parametrize(
    ("motivo", "status"),
    [
        ("PROPOSTA_EXPIRADA", "AGENDADA"),
        ("FALTOU", "EM_PROPOSTA"),
        ("FALTOU", "NA_FILA"),
        ("FALTOU", "CANCELADA"),
    ],
)
def test_adr026_estado_de_origem_invalido_levanta_transicao_invalida(motivo, status):
    with pytest.raises(TransicaoInvalida):
        reentrar_no_fim_da_fila(sol(status), CHEGADA + timedelta(days=1), motivo)


def test_adr026_motivo_livre_e_recusado():
    with pytest.raises(ValueError, match="motivo"):
        reentrar_no_fim_da_fila(sol("AGENDADA"), CHEGADA, "você era o 3º da fila")


AGORA = datetime(2026, 10, 19, 12, 0, tzinfo=UTC)


def test_uc007_classificar_em_analise_entra_na_fila_com_dois_eventos():
    nova, eventos = classificar(
        Solicitacao(UUID(int=1), "EM_ANALISE", None, 5, None), "VERMELHO", None, AGORA
    )

    assert (nova.status, nova.classificacao_risco, nova.data_entrada_fila) == (
        "NA_FILA",
        "VERMELHO",
        AGORA,
    )
    assert [(e.tipo, e.visivel_paciente) for e in eventos] == [
        ("CLASSIFICADA", False),
        ("ENTROU_NA_FILA", True),
    ]


def test_uc007_reclassificar_na_fila_exige_motivo_e_mantem_a_chegada():
    with pytest.raises(EntradaInvalida):
        classificar(sol("NA_FILA"), "VERMELHO", None, AGORA)
    nova, (evento,) = classificar(sol("NA_FILA"), "VERMELHO", "Motivo sintético", AGORA)

    assert nova.data_entrada_fila == CHEGADA
    assert (evento.tipo, evento.visivel_paciente) == ("RECLASSIFICADA", False)


@pytest.mark.parametrize("status", ["EM_PROPOSTA", "AGENDADA", "ATENDIDA", "CANCELADA"])
def test_uc007_classificar_e_cancelar_fora_do_estado_levantam_transicao_invalida(status):
    with pytest.raises(TransicaoInvalida):
        classificar(sol(status), "VERDE", "Motivo sintético", AGORA)
    if status in ("ATENDIDA", "CANCELADA"):  # EM_PROPOSTA e AGENDADA cancelam (UC-005 A1)
        with pytest.raises(TransicaoInvalida):
            cancelar(sol(status), "OUTRO", AGORA)
    else:
        with pytest.raises(TransicaoInvalida):  # sem agendamento ativo: inconsistente
            cancelar(sol(status), "OUTRO", AGORA)
        assert cancelar(sol(status), "OUTRO", AGORA, tem_agendamento_ativo=True)[0].status == (
            "CANCELADA"
        )


def test_adr024_recalcular_nota_so_gera_evento_na_fila_e_com_nota_diferente():
    assert recalcular_nota(sol("NA_FILA"), 25, AGORA)[1] is None
    assert recalcular_nota(sol("EM_ANALISE"), 40, AGORA)[1] is None
    nova, evento = recalcular_nota(sol("NA_FILA"), 40, AGORA)
    assert nova.nota == 40 and evento.tipo == "RECLASSIFICADA" and not evento.visivel_paciente
    with pytest.raises(TransicaoInvalida):
        recalcular_nota(sol("CANCELADA"), 40, AGORA)


def test_uc002_cancelar_usa_o_rotulo_do_codigo_e_recusa_codigo_desconhecido():
    nova, evento = cancelar(sol("NA_FILA"), "CONFLITO_DE_HORARIO", AGORA)

    assert nova.status == "CANCELADA"
    assert evento.motivo == MOTIVOS_CANCELAMENTO["CONFLITO_DE_HORARIO"]
    with pytest.raises(EntradaInvalida):
        cancelar(sol("NA_FILA"), "texto livre", AGORA)
