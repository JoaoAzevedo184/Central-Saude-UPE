import re
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from app.dominio.erros import TransicaoInvalida
from app.dominio.solicitacao import MOTIVOS_REENTRADA, Solicitacao, reentrar_no_fim_da_fila
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
