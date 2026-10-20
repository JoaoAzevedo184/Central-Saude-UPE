"""Domínio da proposta, das transições do agendamento e da geração de vagas.

UC-003, UC-004, UC-005, UC-006, RN-014, RN-016, ADR-008, ADR-021.
"""

from datetime import UTC, date, datetime, time, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.dominio.agendamento.estados import (
    Agendamento,
    cancelar_pelo_paciente,
    confirmar,
    expirar,
    recusar,
    registrar_presenca,
)
from app.dominio.agendamento.proposta import (
    Candidata,
    VagaLivre,
    propor_vaga,
    turnos_compativeis,
)
from app.dominio.agendamento.vagas import GradeAgenda, horarios_da_agenda, situacao_da_vaga
from app.dominio.erros import PropostaExpirada, ToleranciaNaoEncerrada, TransicaoInvalida
from app.dominio.solicitacao import Solicitacao, expirar_proposta, recusar_proposta

RECIFE = ZoneInfo("America/Recife")
AGORA = datetime(2026, 10, 19, 12, tzinfo=UTC)  # segunda-feira, 9h em Recife
T0 = datetime(2026, 10, 1, 12, tzinfo=UTC)


def sol(risco="AMARELO", nota=0, entrada=T0, status="NA_FILA"):
    return Solicitacao(uuid4(), status, risco, nota, entrada)


def cand(s, turno="QUALQUER", ja_teve=False):
    return Candidata(s, turno, ja_teve)


def vaga(em_horas=24 * 10, hora_local=None):
    inicio = AGORA + timedelta(hours=em_horas)
    if hora_local is not None:
        inicio = datetime.combine(inicio.astimezone(RECIFE).date(), hora_local, RECIFE)
    return VagaLivre(uuid4(), inicio, 48)


def propor(candidatas, v=None):
    return propor_vaga(
        candidatas,
        v or vaga(),
        AGORA,
        antecedencia_minima_horas=24,
        janela_minima_horas=12,
        fuso=RECIFE,
    )


# --- turno ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("hora", "esperado"),
    [
        (time(7), {"MANHA", "QUALQUER"}),
        (time(11, 59), {"MANHA", "QUALQUER"}),
        (time(12), {"TARDE", "QUALQUER"}),
        (time(17), {"TARDE", "QUALQUER"}),
    ],
)
def test_uc003_turno_pela_hora_local_de_recife(hora, esperado):
    inicio = datetime.combine(date(2026, 10, 20), hora, RECIFE)

    assert turnos_compativeis(inicio, RECIFE) == esperado


def test_uc003_turno_usa_hora_local_e_nao_utc():
    # 13h UTC = 10h em Recife: manhã.
    assert "MANHA" in turnos_compativeis(datetime(2026, 10, 20, 13, tzinfo=UTC), RECIFE)


# --- propor_vaga ---------------------------------------------------------------------------


def test_uc003_escolhe_a_primeira_na_ordem_da_fila():
    verde, amarelo_nota_alta, amarelo_antigo = (
        sol("VERDE", 99, T0 - timedelta(days=30)),
        sol("AMARELO", 5),
        sol("AMARELO", 5, T0 - timedelta(hours=1)),
    )

    proposta = propor([cand(verde), cand(amarelo_nota_alta), cand(amarelo_antigo)])

    assert proposta.solicitacao.id == amarelo_antigo.id
    assert proposta.solicitacao.status == "EM_PROPOSTA"
    assert proposta.evento.tipo == "PROPOSTA_ENVIADA" and proposta.evento.visivel_paciente


def test_uc003_respeita_o_turno():
    manha, tarde = sol(entrada=T0 - timedelta(days=1)), sol()
    v = vaga(hora_local=time(14))

    proposta = propor([cand(manha, "MANHA"), cand(tarde, "TARDE")], v)

    assert proposta.solicitacao.id == tarde.id


def test_uc003_nunca_reoferece_a_mesma_vaga_a_mesma_solicitacao():
    primeira, segunda = sol(entrada=T0 - timedelta(days=1)), sol()

    proposta = propor([cand(primeira, ja_teve=True), cand(segunda)])

    assert proposta.solicitacao.id == segunda.id


def test_uc003_so_propoe_para_na_fila():
    assert propor([cand(sol(status="EM_ANALISE")), cand(sol(status="EM_PROPOSTA"))]) is None


def test_rn016_janela_curta_nao_propoe():
    # Vaga em 35 h: prazo = 35 - 24 = 11 h < 12 h de janela mínima.
    assert propor([cand(sol())], vaga(em_horas=35)) is None


def test_adr026_vaga_distante_expira_no_prazo_da_fila():
    assert propor([cand(sol())]).expira_em == AGORA + timedelta(hours=48)


def test_uc003_sem_candidatas_nao_propoe():
    assert propor([]) is None


# --- transições do agendamento -------------------------------------------------------------


def proposto(expira_em=AGORA + timedelta(hours=1)):
    return Agendamento(uuid4(), "PROPOSTO", expira_em)


def test_uc004_confirmar_dentro_do_prazo():
    a = confirmar(proposto(), AGORA)

    assert a.status == "CONFIRMADO" and a.respondido_em == AGORA


def test_uc004_confirmar_no_instante_do_prazo_ja_esta_expirado():
    with pytest.raises(PropostaExpirada):
        confirmar(proposto(expira_em=AGORA), AGORA)


def test_uc004_confirmar_proposta_ja_respondida_e_transicao_invalida():
    with pytest.raises(TransicaoInvalida):
        confirmar(confirmar(proposto(), AGORA), AGORA)


def test_uc005_recusar_grava_o_motivo_codigo():
    a = recusar(proposto(), AGORA)

    assert (a.status, a.motivo_cancelamento) == ("CANCELADO", "RECUSADO_PELO_PACIENTE")


def test_uc006_expirar_so_depois_do_prazo():
    with pytest.raises(TransicaoInvalida):
        expirar(proposto(expira_em=AGORA + timedelta(seconds=1)), AGORA)
    assert expirar(proposto(expira_em=AGORA), AGORA).status == "EXPIRADO"


# --- solicitação ---------------------------------------------------------------------------


def test_uc005_primeira_recusa_mantem_a_posicao():
    s = sol(status="EM_PROPOSTA")

    nova, eventos = recusar_proposta(s, 0, 1, AGORA)

    assert nova.status == "NA_FILA" and nova.data_entrada_fila == T0
    assert [e.tipo for e in eventos] == ["RECUSADA"]


def test_uc005_segunda_recusa_volta_para_o_fim_da_fila():
    s = sol(status="EM_PROPOSTA")

    nova, eventos = recusar_proposta(s, 1, 1, AGORA)

    assert nova.status == "NA_FILA" and nova.data_entrada_fila == AGORA
    assert [e.tipo for e in eventos] == ["RECUSADA", "REENTROU_NA_FILA"]
    assert "recusou outras datas" in eventos[-1].motivo


def test_uc006_expirar_proposta_volta_para_o_fim_com_motivo():
    nova, eventos = expirar_proposta(sol(status="EM_PROPOSTA"), AGORA)

    assert nova.data_entrada_fila == AGORA
    assert [e.tipo for e in eventos] == ["PROPOSTA_EXPIRADA", "REENTROU_NA_FILA"]
    assert "não confirmou a vaga no prazo" in eventos[-1].motivo


# --- geração de vagas ----------------------------------------------------------------------


def grade(**kw):
    padrao = dict(
        dias_semana=[2, 4],  # terça e quinta (ISO)
        hora_inicio=time(8),
        hora_fim=time(10),
        duracao_min=45,
        vigencia_inicio=date(2026, 1, 1),
        vigencia_fim=None,
    )
    return GradeAgenda(**(padrao | kw))


def test_gerar_vagas_respeita_dias_horarios_e_duracao():
    horarios = horarios_da_agenda(grade(), AGORA, 7, RECIFE)

    inicios = [i.astimezone(RECIFE) for i, _ in horarios]
    assert {i.isoweekday() for i in inicios} == {2, 4}
    # 8h00 e 8h45 cabem; 9h30 terminaria 10h15, depois de hora_fim.
    assert sorted({i.time() for i in inicios}) == [time(8), time(8, 45)]
    assert all(f - i == timedelta(minutes=45) for i, f in horarios)


def test_gerar_vagas_respeita_a_vigencia_e_o_horizonte():
    inicio_vigencia = date(2026, 10, 22)  # quinta
    horarios = horarios_da_agenda(
        grade(vigencia_inicio=inicio_vigencia, vigencia_fim=date(2026, 10, 27)), AGORA, 30, RECIFE
    )

    dias = sorted({i.astimezone(RECIFE).date() for i, _ in horarios})
    assert dias == [date(2026, 10, 22), date(2026, 10, 27)]
    sem_fim = horarios_da_agenda(grade(), AGORA, 3, RECIFE)  # seg, ter, qua
    assert {i.astimezone(RECIFE).date() for i, _ in sem_fim} == {date(2026, 10, 20)}


def test_gerar_vagas_nao_cria_vaga_que_ja_comecou():
    agora = datetime.combine(date(2026, 10, 20), time(8, 30), RECIFE)  # terça, 8h30

    horarios = horarios_da_agenda(grade(), agora, 1, RECIFE)

    assert [i.astimezone(RECIFE).time() for i, _ in horarios] == [time(8, 45)]


def test_adr008_vagas_em_recife_sao_utc_menos_3_o_ano_todo():
    # Recife não tem horário de verão: janeiro (verão) e julho dão o mesmo deslocamento.
    for dia in (date(2027, 1, 5), date(2027, 7, 6)):  # terças
        agora = datetime.combine(dia, time(0), RECIFE)
        inicio, _ = horarios_da_agenda(grade(), agora, 1, RECIFE)[0]
        assert inicio.utcoffset() == timedelta(hours=-3)
        assert inicio.astimezone(UTC).time() == time(11)


# --- presença, cancelamento e situação da vaga (UC-008, UC-005 A1, RN-016) ----------------


def test_uc008_presenca_so_de_confirmado_e_falta_estrita_apos_tolerancia():
    inicio = AGORA
    ag = Agendamento(uuid4(), "CONFIRMADO", AGORA - timedelta(days=1))

    with pytest.raises(TransicaoInvalida):
        registrar_presenca(ag, True, inicio, 60, inicio - timedelta(seconds=1))
    assert registrar_presenca(ag, True, inicio, 60, inicio).status == "REALIZADO"
    with pytest.raises(ToleranciaNaoEncerrada):
        registrar_presenca(ag, False, inicio, 60, inicio + timedelta(minutes=60))
    falta = registrar_presenca(ag, False, inicio, 60, inicio + timedelta(minutes=60, seconds=1))
    assert falta.status == "FALTOU"
    with pytest.raises(TransicaoInvalida):
        registrar_presenca(
            Agendamento(uuid4(), "PROPOSTO", AGORA), True, inicio, 60, inicio + timedelta(hours=2)
        )


def test_uc005_cancelar_pelo_paciente_so_antes_do_inicio():
    inicio = AGORA + timedelta(hours=1)
    ag = Agendamento(uuid4(), "CONFIRMADO", AGORA - timedelta(days=1), AGORA - timedelta(days=2))

    cancelado = cancelar_pelo_paciente(ag, inicio, AGORA)

    assert cancelado.status == "CANCELADO"
    assert cancelado.motivo_cancelamento == "CANCELADO_PELO_PACIENTE"
    assert cancelado.respondido_em == ag.respondido_em  # a confirmação não é reescrita
    with pytest.raises(TransicaoInvalida):
        cancelar_pelo_paciente(ag, inicio, inicio)
    with pytest.raises(TransicaoInvalida):
        cancelar_pelo_paciente(cancelado, inicio, AGORA)


@pytest.mark.parametrize(
    ("em_horas", "status_admin", "ativo", "esperado"),
    [
        (240, "ATIVA", None, "LIVRE"),
        (30, "ATIVA", None, "LIVRE_SEM_PROPOSTA"),  # 30 - 24 = 6 h < janela de 12 h
        (240, "ATIVA", "PROPOSTO", "PROPOSTA"),
        (-1, "ATIVA", "CONFIRMADO", "CONFIRMADA"),  # presença ainda não registrada
        (240, "BLOQUEADA", None, "BLOQUEADA"),
        (-1, "ATIVA", None, "ENCERRADA"),
    ],
)
def test_rn016_situacao_da_vaga_no_painel(em_horas, status_admin, ativo, esperado):
    inicio = AGORA + timedelta(hours=em_horas)

    situacao = situacao_da_vaga(inicio, status_admin, ativo, AGORA, 48, 24, janela_minima_horas=12)

    assert situacao == esperado
