from datetime import UTC, datetime, timedelta

from app.dominio.agendamento.prazos import calcular_expira_em, pode_marcar_falta
from app.infra.relogio import RelogioFixo

AGORA = datetime(2026, 10, 19, 9, 0, tzinfo=UTC)


def expira(vaga_em_horas, prazo=48, antecedencia=24, janela=12):
    return calcular_expira_em(
        AGORA,
        AGORA + timedelta(hours=vaga_em_horas),
        prazo,
        antecedencia,
        janela_minima_horas=janela,
    )


def test_adr026_vaga_distante_usa_o_prazo_da_fila():
    assert expira(vaga_em_horas=24 * 10) == AGORA + timedelta(hours=48)


def test_rn008_vaga_proxima_usa_a_antecedencia():
    assert expira(vaga_em_horas=60) == AGORA + timedelta(hours=36)


def test_adr021_janela_exatamente_minima_ainda_propoe():
    assert expira(vaga_em_horas=36) == AGORA + timedelta(hours=12)


def test_adr021_janela_menor_que_a_minima_nao_propoe():
    assert expira(vaga_em_horas=35) is None
    assert expira(vaga_em_horas=10) is None


def test_adr026_falta_so_apos_tolerancia():
    relogio = RelogioFixo(AGORA)
    inicio = AGORA

    assert not pode_marcar_falta(inicio, relogio.agora(), 60)
    relogio.avancar(timedelta(minutes=60))
    assert not pode_marcar_falta(inicio, relogio.agora(), 60)  # no limite ainda tolera
    relogio.avancar(timedelta(seconds=1))
    assert pode_marcar_falta(inicio, relogio.agora(), 60)


def test_adr026_tolerancia_zero():
    assert pode_marcar_falta(AGORA, AGORA + timedelta(seconds=1), 0)


def test_adr021_sem_janela_e_sem_prazo_nao_propoe():
    # Vaga exatamente na antecedência mínima: expira_em == proposto_em, nunca é proposta.
    assert expira(vaga_em_horas=24, janela=0) is None
