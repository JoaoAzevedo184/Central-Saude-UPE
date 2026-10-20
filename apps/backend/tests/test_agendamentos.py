"""Vagas, proposta automática, confirmação, recusa e expiração.

UC-003, UC-004, UC-005, UC-006, RN-001, RN-002, RN-014, RN-016, ADR-004, ADR-007, ADR-021.
Os jobs rodam com sessões na transação do teste. O teste de concorrência usa conexões
próprias, com commit de verdade, numa fila só dele, e apaga tudo no fim.
"""

import logging
import threading
from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.dominio.agendamento.estados import confirmar as confirmar_agendamento
from app.dominio.solicitacao import confirmar_proposta
from app.infra import agendamentos
from app.infra.agendamentos import (
    aplicar_agendamento,
    expirar_agendamento,
    para_dominio_agendamento,
    travar_agendamento,
)
from app.infra.db import SessionLocal
from app.infra.modelos import (
    Agenda,
    Agendamento,
    Auditoria,
    Especialidade,
    Fila,
    HistoricoSolicitacao,
    Outbox,
    Paciente,
    Solicitacao,
    Unidade,
    Vaga,
)
from app.infra.relogio import RelogioFixo
from app.infra.solicitacoes import gravar_transicao, para_dominio
from app.worker import jobs
from tests.fila_sintetica import (
    chaves,
    criar_equipe,
    criar_paciente,
    csrf,
    entrar,
    montar_mundo,
)
from tests.test_auth import novo_cliente
from tests.test_solicitacoes import CHAVES_PROIBIDAS

pytestmark = pytest.mark.integracao

RECIFE = ZoneInfo("America/Recife")
T0 = datetime(2026, 10, 1, 12, tzinfo=UTC)
DIA_DISTANTE = date(2026, 10, 29)  # quinta, 10 dias depois do relógio dos testes


@pytest.fixture
def mundo(sessao):
    return montar_mundo(sessao)


@pytest.fixture
def agenda(sessao, mundo):
    return criar_agenda(sessao, mundo.fila)


def criar_agenda(sessao, fila, dias=(1, 2, 3, 4, 5, 6, 7), **kw) -> UUID:
    a = Agenda(
        fila_id=fila,
        profissional="Dra. Sintética Exemplo",
        dias_semana=list(dias),
        hora_inicio=kw.pop("hora_inicio", time(8)),
        hora_fim=kw.pop("hora_fim", time(12)),
        duracao_min=kw.pop("duracao_min", 60),
        vigencia_inicio=kw.pop("vigencia_inicio", date(2026, 1, 1)),
        **kw,
    )
    sessao.add(a)
    sessao.flush()
    return a.id


def criar_vaga(sessao, agenda, inicio: datetime) -> UUID:
    v = Vaga(agenda_id=agenda, inicio=inicio, fim=inicio + timedelta(hours=1))
    sessao.add(v)
    sessao.flush()
    return v.id


def as_9h(dia=DIA_DISTANTE, hora=time(9)) -> datetime:
    return datetime.combine(dia, hora, RECIFE)


def solicitacao_na_fila(
    sessao, paciente, fila, risco="AMARELO", nota=0, entrada=T0, turno="QUALQUER"
) -> UUID:
    s = Solicitacao(
        paciente_id=paciente.id,
        fila_id=fila,
        status="NA_FILA",
        classificacao_risco=risco,
        nota=nota,
        turno_preferido=turno,
        data_entrada_fila=entrada,
        data_pedido=date(2026, 10, 1),
    )
    sessao.add(s)
    sessao.flush()
    return s.id


def na_fila(sessao, fila, **kw) -> UUID:
    _, p = criar_paciente(sessao, nome="Paciente Sintético Fila", login=False)
    return solicitacao_na_fila(sessao, p, fila, **kw)


@pytest.fixture
def rodar(conexao, sessao, relogio):
    """Roda um job com sessões na transação do teste e o relógio fixo."""

    def _rodar(job):
        resultado = job(
            fabrica=lambda: Session(bind=conexao, join_transaction_mode="create_savepoint"),
            relogio=relogio,
        )
        sessao.expire_all()
        return resultado

    return _rodar


@pytest.fixture
def paciente(api, sessao):
    _, p = criar_paciente(sessao)
    entrar(api, p.cpf)
    return p


def agendamentos_de(sessao, solicitacao_id):
    return list(
        sessao.scalars(
            select(Agendamento)
            .where(Agendamento.solicitacao_id == solicitacao_id)
            .order_by(Agendamento.proposto_em, Agendamento.id)
        )
    )


def ativo_de(sessao, solicitacao_id) -> Agendamento | None:
    return sessao.scalar(
        select(Agendamento).where(
            Agendamento.solicitacao_id == solicitacao_id,
            Agendamento.status.in_(("PROPOSTO", "CONFIRMADO")),
        )
    )


def contar(sessao, modelo, *filtros):
    return sessao.scalar(select(func.count()).select_from(modelo).where(*filtros))


def confirmar(cliente, agendamento_id, com_csrf=True):
    return cliente.post(
        f"/api/v1/agendamentos/{agendamento_id}/confirmar",
        headers=csrf(cliente) if com_csrf else {},
    )


def recusar(cliente, agendamento_id):
    return cliente.post(f"/api/v1/agendamentos/{agendamento_id}/recusar", headers=csrf(cliente))


def motivos(detalhe) -> str:
    """Motivos da linha do tempo, na ordem (ocorrido_em, seq)."""
    return " | ".join(e["motivo"] or "" for e in detalhe["linha_do_tempo"])


def tipos(detalhe) -> list[str]:
    return [e["tipo"] for e in detalhe["linha_do_tempo"]]


def posicao_no_painel(sessao, mundo, solicitacao_id):
    atendente = criar_equipe(sessao, "ATENDENTE", filas=[mundo.fila])
    equipe = entrar(novo_cliente(), atendente.email)
    itens = equipe.get(f"/api/v1/equipe/filas/{mundo.fila}/solicitacoes").json()["itens"]
    return next(i["posicao"] for i in itens if i["id"] == str(solicitacao_id))


# --- gerar_vagas ---------------------------------------------------------------------------


def vagas_da(sessao, agenda):
    return list(sessao.scalars(select(Vaga).where(Vaga.agenda_id == agenda).order_by(Vaga.inicio)))


def test_gerar_vagas_respeita_dias_horarios_e_vigencia(sessao, mundo, rodar):
    # Relógio: segunda 19/10, 9h em Recife. Terças e quintas, 8h-10h, 1 h; vigência até 29/10.
    agenda = criar_agenda(
        sessao, mundo.fila, dias=(2, 4), hora_fim=time(10), vigencia_fim=date(2026, 10, 29)
    )
    inativa = criar_agenda(sessao, mundo.fila, ativa=False)

    rodar(jobs.gerar_vagas)

    vagas = vagas_da(sessao, agenda)
    dias = sorted({v.inicio.astimezone(RECIFE).date() for v in vagas})
    assert dias == [date(2026, 10, d) for d in (20, 22, 27, 29)]
    assert {v.inicio.astimezone(RECIFE).time() for v in vagas} == {time(8), time(9)}
    assert vagas_da(sessao, inativa) == []


def test_gerar_vagas_rodar_duas_vezes_nao_duplica(sessao, agenda, rodar):
    rodar(jobs.gerar_vagas)
    primeira = [v.id for v in vagas_da(sessao, agenda)]

    rodar(jobs.gerar_vagas)

    assert primeira and [v.id for v in vagas_da(sessao, agenda)] == primeira


def test_adr008_vagas_gravadas_no_fuso_de_recife(sessao, mundo, rodar, relogio):
    # Janeiro: se Recife tivesse horário de verão, seria UTC-2. O teste fixa UTC-3.
    relogio.instante = datetime(2027, 1, 4, 12, tzinfo=UTC)
    agenda = criar_agenda(sessao, mundo.fila, dias=(2,), hora_inicio=time(8), hora_fim=time(9))

    rodar(jobs.gerar_vagas)

    vaga = vagas_da(sessao, agenda)[0]
    assert vaga.inicio == datetime(2027, 1, 5, 11, tzinfo=UTC)  # 8h em Recife
    assert vaga.inicio.astimezone(RECIFE).hour == 8


# --- propor_vagas --------------------------------------------------------------------------


def test_uc003_propoe_ao_primeiro_na_ordem_da_fila(sessao, mundo, agenda, rodar, relogio):
    vaga = criar_vaga(sessao, agenda, as_9h())
    segunda = na_fila(sessao, mundo.fila, risco="AMARELO", nota=9)
    primeira = na_fila(sessao, mundo.fila, risco="VERMELHO", nota=0, entrada=T0 + timedelta(1))

    rodar(jobs.propor_vagas)

    ag = ativo_de(sessao, primeira)
    assert ag.vaga_id == vaga and ag.status == "PROPOSTO"
    assert ag.proposto_por_usuario_id is None
    assert ag.proposto_em == relogio.agora()
    assert ag.expira_em == relogio.agora() + timedelta(hours=48)
    assert sessao.get(Solicitacao, primeira).status == "EM_PROPOSTA"
    assert ativo_de(sessao, segunda) is None
    evento = sessao.scalar(
        select(HistoricoSolicitacao).where(
            HistoricoSolicitacao.solicitacao_id == primeira,
            HistoricoSolicitacao.tipo == "PROPOSTA_ENVIADA",
        )
    )
    assert evento.visivel_paciente and evento.ator_usuario_id is None
    outbox = sessao.scalar(select(Outbox).where(Outbox.agregado_id == primeira))
    assert outbox.tipo_evento == "PROPOSTA_ENVIADA"
    assert outbox.payload["agendamento_id"] == str(ag.id)
    assert contar(sessao, Auditoria, Auditoria.entidade_id == ag.id) == 1


def test_uc003_respeita_o_turno(sessao, mundo, agenda, rodar):
    criar_vaga(sessao, agenda, as_9h(hora=time(14)))  # tarde
    manha = na_fila(sessao, mundo.fila, turno="MANHA", entrada=T0 - timedelta(days=1))
    tarde = na_fila(sessao, mundo.fila, turno="TARDE")

    rodar(jobs.propor_vagas)

    assert ativo_de(sessao, manha) is None
    assert ativo_de(sessao, tarde) is not None


def test_rn016_janela_curta_nao_propoe(sessao, mundo, agenda, rodar, relogio):
    # 30 h à frente: prazo = 30 - 24 = 6 h, menor que a janela mínima de 12 h.
    vaga = criar_vaga(sessao, agenda, relogio.agora() + timedelta(hours=30))
    s = na_fila(sessao, mundo.fila)

    rodar(jobs.propor_vagas)

    assert ativo_de(sessao, s) is None
    assert contar(sessao, Agendamento, Agendamento.vaga_id == vaga) == 0


def test_uc003_nao_propoe_para_solicitacao_em_analise(sessao, mundo, agenda, rodar):
    criar_vaga(sessao, agenda, as_9h())
    _, p = criar_paciente(sessao, login=False)
    s = Solicitacao(
        paciente_id=p.id, fila_id=mundo.fila, status="EM_ANALISE", data_pedido=date(2026, 10, 1)
    )
    sessao.add(s)
    sessao.flush()

    rodar(jobs.propor_vagas)

    assert agendamentos_de(sessao, s.id) == []


def test_rn002_uma_proposta_por_solicitacao_mesmo_com_varias_vagas(sessao, mundo, agenda, rodar):
    criar_vaga(sessao, agenda, as_9h())
    criar_vaga(sessao, agenda, as_9h(hora=time(10)))
    s = na_fila(sessao, mundo.fila)

    rodar(jobs.propor_vagas)
    rodar(jobs.propor_vagas)

    assert len(agendamentos_de(sessao, s)) == 1


def test_uc003_vaga_vai_para_a_mais_cedo_primeiro(sessao, mundo, agenda, rodar):
    tarde = criar_vaga(sessao, agenda, as_9h(hora=time(11)))
    cedo = criar_vaga(sessao, agenda, as_9h(hora=time(8)))
    s = na_fila(sessao, mundo.fila)

    rodar(jobs.propor_vagas)

    assert ativo_de(sessao, s).vaga_id == cedo
    assert contar(sessao, Agendamento, Agendamento.vaga_id == tarde) == 0


def test_uc003_ignora_vaga_bloqueada_e_vaga_passada(sessao, mundo, agenda, rodar, relogio):
    bloqueada = criar_vaga(sessao, agenda, as_9h())
    sessao.get(Vaga, bloqueada).status_admin = "BLOQUEADA"
    criar_vaga(sessao, agenda, relogio.agora() - timedelta(hours=1))
    s = na_fila(sessao, mundo.fila)

    rodar(jobs.propor_vagas)

    assert agendamentos_de(sessao, s) == []


# --- expirar_propostas ---------------------------------------------------------------------


def test_uc006_expira_e_volta_para_o_fim_da_fila(
    api, sessao, paciente, mundo, agenda, rodar, relogio
):
    criar_vaga(sessao, agenda, as_9h())
    sid = solicitacao_na_fila(sessao, paciente, mundo.fila)
    rodar(jobs.propor_vagas)
    ag = ativo_de(sessao, sid)

    relogio.avancar(timedelta(hours=48))
    rodar(jobs.expirar_propostas)
    entrar(api, paciente.cpf)  # o access token venceu com o relógio

    assert sessao.get(Agendamento, ag.id).status == "EXPIRADO"
    s = sessao.get(Solicitacao, sid)
    assert s.status == "NA_FILA" and s.data_entrada_fila == relogio.agora()
    detalhe = api.get(f"/api/v1/solicitacoes/{sid}").json()
    assert detalhe["agendamento_ativo"] is None
    assert "não confirmou a vaga no prazo" in motivos(detalhe)
    assert not chaves(detalhe) & CHAVES_PROIBIDAS
    assert (
        contar(sessao, Outbox, Outbox.agregado_id == sid, Outbox.tipo_evento == "PROPOSTA_EXPIRADA")
        == 1
    )


def test_uc006_rodar_duas_vezes_nao_muda_nada(sessao, mundo, agenda, rodar, relogio):
    criar_vaga(sessao, agenda, as_9h())
    sid = na_fila(sessao, mundo.fila)
    rodar(jobs.propor_vagas)
    relogio.avancar(timedelta(hours=48))
    rodar(jobs.expirar_propostas)
    antes = (
        contar(sessao, HistoricoSolicitacao, HistoricoSolicitacao.solicitacao_id == sid),
        contar(sessao, Outbox, Outbox.agregado_id == sid),
        sessao.get(Solicitacao, sid).data_entrada_fila,
    )

    rodar(jobs.expirar_propostas)

    depois = (
        contar(sessao, HistoricoSolicitacao, HistoricoSolicitacao.solicitacao_id == sid),
        contar(sessao, Outbox, Outbox.agregado_id == sid),
        sessao.get(Solicitacao, sid).data_entrada_fila,
    )
    assert depois == antes


def test_uc006_um_segundo_antes_do_prazo_nao_expira(sessao, mundo, agenda, rodar, relogio):
    criar_vaga(sessao, agenda, as_9h())
    sid = na_fila(sessao, mundo.fila)
    rodar(jobs.propor_vagas)

    relogio.avancar(timedelta(hours=48, seconds=-1))
    rodar(jobs.expirar_propostas)

    assert ativo_de(sessao, sid).status == "PROPOSTO"


def test_uc003_nunca_reoferece_a_mesma_vaga_depois_de_expirar(
    sessao, mundo, agenda, rodar, relogio
):
    vaga = criar_vaga(sessao, agenda, as_9h())
    sid = na_fila(sessao, mundo.fila)
    rodar(jobs.propor_vagas)
    relogio.avancar(timedelta(hours=48))
    rodar(jobs.expirar_propostas)

    rodar(jobs.propor_vagas)

    assert len(agendamentos_de(sessao, sid)) == 1
    assert contar(sessao, Agendamento, Agendamento.vaga_id == vaga) == 1


# --- confirmar -----------------------------------------------------------------------------


@pytest.fixture
def proposta(sessao, paciente, mundo, agenda, rodar):
    """Agendamento PROPOSTO para uma solicitação do `paciente` logado."""
    criar_vaga(sessao, agenda, as_9h())
    sid = solicitacao_na_fila(sessao, paciente, mundo.fila)
    rodar(jobs.propor_vagas)
    return ativo_de(sessao, sid)


def test_uc004_detalhe_mostra_a_proposta(api, proposta):
    detalhe = api.get(f"/api/v1/solicitacoes/{proposta.solicitacao_id}").json()

    ativo = detalhe["agendamento_ativo"]
    assert ativo["id"] == str(proposta.id) and ativo["status"] == "PROPOSTO"
    assert ativo["inicio"] == "2026-10-29T09:00:00-03:00"
    assert ativo["expira_em"] == "2026-10-21T09:00:00-03:00"
    assert ativo["profissional"] == "Dra. Sintética Exemplo"
    assert ativo["unidade"]["sigla"] == "TST1"
    assert "endereco" in ativo
    assert not chaves(detalhe) & CHAVES_PROIBIDAS


def test_uc004_confirmar_dentro_do_prazo(api, sessao, paciente, proposta, relogio):
    relogio.avancar(timedelta(hours=47))
    entrar(api, paciente.cpf)

    resposta = confirmar(api, proposta.id)

    assert resposta.status_code == 200, resposta.text
    corpo = resposta.json()
    assert corpo["status"] == "AGENDADA"
    assert corpo["agendamento_ativo"]["status"] == "CONFIRMADO"
    assert corpo["agendamento_ativo"]["expira_em"] is None
    assert tipos(corpo)[-1] == "CONFIRMADA"
    assert not chaves(corpo) & CHAVES_PROIBIDAS
    ag = sessao.get(Agendamento, proposta.id)
    assert ag.status == "CONFIRMADO" and ag.respondido_em == relogio.agora()
    assert (
        contar(
            sessao,
            Outbox,
            Outbox.agregado_id == proposta.solicitacao_id,
            Outbox.tipo_evento == "AGENDAMENTO_CONFIRMADO",
        )
        == 1
    )
    assert (
        contar(
            sessao,
            Auditoria,
            Auditoria.entidade_id == proposta.id,
            Auditoria.acao == "CONFIRMAR_AGENDAMENTO",
        )
        == 1
    )


def test_uc004_um_segundo_depois_do_prazo_responde_409_sem_o_job(
    api, sessao, paciente, proposta, relogio
):
    relogio.instante = proposta.expira_em + timedelta(seconds=1)
    entrar(api, paciente.cpf)

    resposta = confirmar(api, proposta.id)

    assert resposta.status_code == 409
    assert resposta.json()["type"] == "/problemas/proposta-expirada"
    sessao.expire_all()
    assert sessao.get(Agendamento, proposta.id).status == "PROPOSTO"
    assert sessao.get(Solicitacao, proposta.solicitacao_id).status == "EM_PROPOSTA"


def test_uc004_confirmar_duas_vezes_responde_409(api, proposta):
    assert confirmar(api, proposta.id).status_code == 200

    resposta = confirmar(api, proposta.id)

    assert resposta.status_code == 409
    assert resposta.json()["type"] == "/problemas/transicao-invalida"


def test_am001_confirmar_ou_recusar_proposta_de_outro_paciente_responde_404(sessao, proposta):
    _, outro = criar_paciente(sessao)
    cliente = entrar(novo_cliente(), outro.cpf)

    assert confirmar(cliente, proposta.id).status_code == 404
    assert recusar(cliente, proposta.id).status_code == 404
    assert confirmar(cliente, uuid4()).status_code == 404
    sessao.expire_all()
    assert sessao.get(Agendamento, proposta.id).status == "PROPOSTO"


def test_am002_confirmar_ou_recusar_sem_csrf_responde_403(api, proposta):
    resposta = confirmar(api, proposta.id, com_csrf=False)
    assert api.post(f"/api/v1/agendamentos/{proposta.id}/recusar").status_code == 403

    assert resposta.status_code == 403
    assert resposta.json()["type"] == "/problemas/csrf-invalido"


# --- recusar -------------------------------------------------------------------------------


def test_uc005_primeira_recusa_mantem_a_posicao(
    api, sessao, paciente, mundo, agenda, rodar, relogio
):
    criar_vaga(sessao, agenda, as_9h())
    sid = solicitacao_na_fila(sessao, paciente, mundo.fila, risco="VERMELHO")
    na_fila(sessao, mundo.fila, risco="VERDE")
    na_fila(sessao, mundo.fila, risco="VERMELHO", entrada=T0 + timedelta(days=1))
    antes = posicao_no_painel(sessao, mundo, sid)
    rodar(jobs.propor_vagas)
    ag = ativo_de(sessao, sid)
    relogio.avancar(timedelta(minutes=5))

    resposta = recusar(api, ag.id)

    assert resposta.status_code == 200, resposta.text
    corpo = resposta.json()
    assert corpo["status"] == "NA_FILA" and corpo["agendamento_ativo"] is None
    assert tipos(corpo)[-1] == "RECUSADA"
    assert not chaves(corpo) & CHAVES_PROIBIDAS
    sessao.expire_all()
    assert sessao.get(Agendamento, ag.id).motivo_cancelamento == "RECUSADO_PELO_PACIENTE"
    assert sessao.get(Solicitacao, sid).data_entrada_fila == T0
    assert posicao_no_painel(sessao, mundo, sid) == antes == 1


def test_uc005_segunda_recusa_manda_para_o_fim(
    api, sessao, paciente, mundo, agenda, rodar, relogio
):
    criar_vaga(sessao, agenda, as_9h())
    criar_vaga(sessao, agenda, as_9h(hora=time(10)))
    sid = solicitacao_na_fila(sessao, paciente, mundo.fila)
    rodar(jobs.propor_vagas)
    assert recusar(api, ativo_de(sessao, sid).id).status_code == 200
    rodar(jobs.propor_vagas)  # a próxima vaga, nunca a recusada

    resposta = recusar(api, ativo_de(sessao, sid).id)

    assert resposta.status_code == 200, resposta.text
    assert "recusou outras datas" in motivos(resposta.json())
    sessao.expire_all()
    assert sessao.get(Solicitacao, sid).data_entrada_fila == relogio.agora()


def test_uc005_recusa_conta_so_desde_a_ultima_entrada_na_fila(
    api, sessao, paciente, mundo, agenda, rodar, relogio
):
    for hora in (9, 10, 11):
        criar_vaga(sessao, agenda, as_9h(hora=time(hora)))
    sid = solicitacao_na_fila(sessao, paciente, mundo.fila)

    def propor_e_recusar():  # relógio anda 1 min por passo (o access token vale pouco)
        rodar(jobs.propor_vagas)
        relogio.avancar(timedelta(minutes=1))
        resposta = recusar(api, ativo_de(sessao, sid).id)
        assert resposta.status_code == 200, resposta.text
        relogio.avancar(timedelta(minutes=1))
        sessao.expire_all()
        return sessao.get(Solicitacao, sid).data_entrada_fila

    assert propor_e_recusar() == T0  # 1ª: mantém a posição
    fim_da_fila = propor_e_recusar()  # 2ª: vai para o fim
    assert fim_da_fila > T0

    assert propor_e_recusar() == fim_da_fila  # 1ª desde a volta: mantém a posição


def test_uc005_linha_do_tempo_recusada_antes_de_reentrou(
    api, sessao, paciente, mundo, agenda, rodar
):
    # Relógio parado: RECUSADA e REENTROU_NA_FILA têm o mesmo ocorrido_em; desempata o seq.
    criar_vaga(sessao, agenda, as_9h())
    criar_vaga(sessao, agenda, as_9h(hora=time(10)))
    sid = solicitacao_na_fila(sessao, paciente, mundo.fila)
    for _ in range(2):
        rodar(jobs.propor_vagas)
        assert recusar(api, ativo_de(sessao, sid).id).status_code == 200
    atendente = criar_equipe(sessao, "ATENDENTE", filas=[mundo.fila])
    equipe = entrar(novo_cliente(), atendente.email)

    do_paciente = tipos(api.get(f"/api/v1/solicitacoes/{sid}").json())
    da_equipe = [
        e["tipo"] for e in equipe.get(f"/api/v1/equipe/solicitacoes/{sid}").json()["historico"]
    ]

    for lista in (do_paciente, da_equipe):
        assert lista[-2:] == ["RECUSADA", "REENTROU_NA_FILA"], lista


def test_uc003_teto_de_candidatas_registra_aviso_sem_dado_pessoal(
    sessao, mundo, agenda, rodar, relogio, monkeypatch, caplog
):
    vaga = criar_vaga(sessao, agenda, as_9h())
    sids = [na_fila(sessao, mundo.fila, entrada=T0 + timedelta(minutes=i)) for i in range(2)]
    for sid in sids:  # as duas já receberam esta vaga e deixaram expirar
        sessao.add(
            Agendamento(
                solicitacao_id=sid,
                vaga_id=vaga,
                status="EXPIRADO",
                proposto_em=T0,
                expira_em=T0 + timedelta(hours=1),
            )
        )
    sessao.flush()
    tarde = na_fila(sessao, mundo.fila, entrada=T0 + timedelta(days=1))
    monkeypatch.setattr(agendamentos, "CANDIDATAS_POR_VAGA", 2)
    monkeypatch.setattr(agendamentos, "_TETO_AVISADO", set())
    caplog.set_level(logging.WARNING)

    rodar(jobs.propor_vagas)
    rodar(jobs.propor_vagas)  # segunda rodada: não repete o aviso

    assert ativo_de(sessao, tarde) is None  # teto: a terceira fica de fora nesta rodada
    avisos = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(avisos) == 1 and str(vaga) in avisos[0].getMessage()
    nomes = {sessao.get(Paciente, sessao.get(Solicitacao, x).paciente_id) for x in sids}
    for p in nomes:
        assert p.nome not in caplog.text and p.cpf not in caplog.text


def test_uc003_nunca_reoferece_a_mesma_vaga_depois_de_recusa(
    api, sessao, paciente, mundo, agenda, rodar
):
    vaga = criar_vaga(sessao, agenda, as_9h())
    sid = solicitacao_na_fila(sessao, paciente, mundo.fila)
    outra = na_fila(sessao, mundo.fila, entrada=T0 + timedelta(days=1))
    rodar(jobs.propor_vagas)
    assert recusar(api, ativo_de(sessao, sid).id).status_code == 200

    rodar(jobs.propor_vagas)

    assert ativo_de(sessao, sid) is None  # continua primeira na fila, mas não recebe a mesma
    assert ativo_de(sessao, outra).vaga_id == vaga


def test_uc005_recusar_depois_do_prazo_responde_409(api, paciente, proposta, relogio):
    relogio.instante = proposta.expira_em
    entrar(api, paciente.cpf)

    resposta = recusar(api, proposta.id)

    assert resposta.status_code == 409
    assert resposta.json()["type"] == "/problemas/proposta-expirada"


# --- ciclo completo ------------------------------------------------------------------------


def test_uc003_uc006_uc004_ciclo_completo(api, sessao, mundo, rodar, relogio):
    # Uma única vaga, 10 dias à frente: sobra janela para a segunda proposta.
    criar_agenda(
        sessao,
        mundo.fila,
        dias=(4,),
        hora_inicio=time(9),
        hora_fim=time(10),
        vigencia_inicio=DIA_DISTANTE,
        vigencia_fim=DIA_DISTANTE,
    )
    pacientes = []
    for _ in range(2):
        _, p = criar_paciente(sessao)
        cliente = entrar(novo_cliente(), p.cpf)
        criada = cliente.post(
            "/api/v1/solicitacoes",
            json={"fila_id": str(mundo.fila), "origem_encaminhamento": "USF Sintética"},
            headers=csrf(cliente),
        )
        assert criada.status_code == 201, criada.text
        pacientes.append((cliente, UUID(criada.json()["id"])))
        relogio.avancar(timedelta(minutes=1))
    atendente = criar_equipe(sessao, "ATENDENTE", filas=[mundo.fila])
    equipe = entrar(novo_cliente(), atendente.email)
    for _, sid in pacientes:
        r = equipe.post(
            f"/api/v1/equipe/solicitacoes/{sid}/classificar",
            json={"classificacao_risco": "AMARELO"},
            headers=csrf(equipe),
        )
        assert r.status_code == 200, r.text
        relogio.avancar(timedelta(minutes=1))
    (cliente_a, a), (cliente_b, b) = pacientes
    cpfs = [
        sessao.get(Paciente, sessao.get(Solicitacao, sid).paciente_id).cpf for _, sid in pacientes
    ]

    # 1. gera a vaga e propõe ao primeiro da fila
    rodar(jobs.gerar_vagas)
    rodar(jobs.propor_vagas)
    vaga = ativo_de(sessao, a).vaga_id
    assert ativo_de(sessao, b) is None

    # 2. A deixa expirar: volta para o fim e a vaga vai para B
    relogio.avancar(timedelta(hours=48))
    rodar(jobs.expirar_propostas)
    rodar(jobs.propor_vagas)
    assert sessao.get(Solicitacao, a).status == "NA_FILA"
    proposta_b = ativo_de(sessao, b)
    assert proposta_b.vaga_id == vaga

    # 3. B confirma (novo login: o access token venceu com o relógio)
    entrar(cliente_a, cpfs[0])
    entrar(cliente_b, cpfs[1])
    resposta = confirmar(cliente_b, proposta_b.id)
    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["status"] == "AGENDADA"
    assert confirmar(cliente_a, proposta_b.id).status_code == 404


# --- concorrência --------------------------------------------------------------------------


LIMPEZA = """
ALTER TABLE historico_solicitacao DISABLE TRIGGER historico_solicitacao_append_only;
ALTER TABLE auditoria DISABLE TRIGGER auditoria_append_only;
DELETE FROM outbox WHERE agregado_id IN (SELECT id FROM solicitacao WHERE fila_id = :fila);
DELETE FROM auditoria WHERE entidade_id IN (
    SELECT id FROM solicitacao WHERE fila_id = :fila
    UNION SELECT a.id FROM agendamento a JOIN solicitacao s ON s.id = a.solicitacao_id
    WHERE s.fila_id = :fila);
DELETE FROM historico_solicitacao
    WHERE solicitacao_id IN (SELECT id FROM solicitacao WHERE fila_id = :fila);
DELETE FROM agendamento
    WHERE solicitacao_id IN (SELECT id FROM solicitacao WHERE fila_id = :fila);
CREATE TEMP TABLE pacientes_limpeza ON COMMIT DROP AS
    SELECT p.id, p.usuario_id FROM paciente p JOIN solicitacao s ON s.paciente_id = p.id
    WHERE s.fila_id = :fila;
DELETE FROM solicitacao WHERE fila_id = :fila;
DELETE FROM consentimento WHERE paciente_id IN (SELECT id FROM pacientes_limpeza);
DELETE FROM paciente WHERE id IN (SELECT id FROM pacientes_limpeza);
DELETE FROM usuario WHERE id IN (SELECT usuario_id FROM pacientes_limpeza);
DELETE FROM vaga WHERE agenda_id IN (SELECT id FROM agenda WHERE fila_id = :fila);
DELETE FROM agenda WHERE fila_id = :fila;
DELETE FROM fila WHERE id = :fila;
DELETE FROM unidade WHERE id = :unidade;
DELETE FROM especialidade WHERE id = :especialidade;
ALTER TABLE auditoria ENABLE TRIGGER auditoria_append_only;
ALTER TABLE historico_solicitacao ENABLE TRIGGER historico_solicitacao_append_only;
"""


@pytest.fixture
def fila_real(banco):
    """Fila, agenda e sessões com commit de verdade, para testes com duas conexões.

    Tudo fica numa fila só do teste, em 2030, e é apagado no fim (os gatilhos append-only são
    desligados só durante a limpeza, no banco de teste), para não vazar para os outros.
    """
    with SessionLocal() as s:
        sufixo = uuid4().hex[:8]
        unidade = Unidade(sigla=f"C{sufixo}", nome="Unidade Sintética Concorrência")
        especialidade = Especialidade(nome=f"Especialidade Concorrência {sufixo}")
        s.add_all([unidade, especialidade])
        s.flush()
        fila = Fila(
            unidade_id=unidade.id,
            especialidade_id=especialidade.id,
            nome="Concorrência",
            descricao_paciente="Fila sintética de concorrência.",
        )
        s.add(fila)
        s.flush()
        agenda = criar_agenda(
            s, fila.id, vigencia_inicio=date(2030, 1, 1), vigencia_fim=date(2030, 1, 31)
        )
        s.commit()
        ids = {"fila": fila.id, "unidade": unidade.id, "especialidade": especialidade.id}
    yield fila.id, agenda
    with banco.begin() as c:
        for comando in filter(str.strip, LIMPEZA.split(";")):
            c.execute(text(comando), ids)


def test_adr004_rn002_propor_vagas_concorrente_nao_duplica(fila_real):
    """Dois Workers ao mesmo tempo, em conexões próprias e com commit de verdade."""
    fila, agenda = fila_real
    relogio = RelogioFixo(datetime(2030, 1, 7, 12, tzinfo=UTC))
    n = 8
    with SessionLocal() as s:
        vagas = [
            criar_vaga(s, agenda, datetime(2030, 1, 20 + i // 4, 11 + i % 4, tzinfo=UTC))
            for i in range(n + 2)
        ]
        solicitacoes = [na_fila(s, fila, entrada=T0 + timedelta(minutes=i)) for i in range(n)]
        s.commit()
    _disputar_e_conferir(relogio, n, vagas, solicitacoes)


def test_uc004_uc006_confirmacao_e_expiracao_simultaneas_so_uma_vence(fila_real):
    """A confirmação trava a proposta; o Worker, no mesmo instante, pula e não altera nada."""
    fila, agenda = fila_real
    relogio = RelogioFixo(datetime(2030, 1, 7, 12, tzinfo=UTC))
    with SessionLocal() as s:
        criar_vaga(s, agenda, datetime(2030, 1, 20, 12, tzinfo=UTC))
        sid = na_fila(s, fila)
        s.commit()
    jobs.propor_vagas(relogio=relogio)
    with SessionLocal() as s:
        agendamento_id = ativo_de(s, sid).id
        expira_em = ativo_de(s, sid).expira_em

    with SessionLocal() as paciente:  # a rota de confirmar, com a trava aberta
        s, a = travar_agendamento(paciente, agendamento_id)
        antes = expira_em - timedelta(seconds=1)
        aplicar_agendamento(
            paciente,
            a,
            confirmar_agendamento(para_dominio_agendamento(a), antes),
            ator_id=None,
            acao="CONFIRMAR_AGENDAMENTO",
            ip=None,
        )
        nova, evento = confirmar_proposta(para_dominio(s), antes)
        gravar_transicao(paciente, s, nova, [evento], ator_id=None, acao="CONFIRMAR", ip=None)
        paciente.flush()

        with SessionLocal() as worker:  # Worker atrasado, já depois do prazo
            assert expirar_agendamento(worker, agendamento_id, expira_em) is False
            worker.commit()
        paciente.commit()

    with SessionLocal() as worker:  # depois do commit, encontra CONFIRMADO e não faz nada
        assert expirar_agendamento(worker, agendamento_id, expira_em) is False
        worker.commit()
    with SessionLocal() as s:
        assert s.get(Agendamento, agendamento_id).status == "CONFIRMADO"
        assert s.get(Solicitacao, sid).status == "AGENDADA"


def _disputar_e_conferir(relogio, n, vagas, solicitacoes):
    largada = threading.Barrier(2)
    erros: list[BaseException] = []
    feitos: list[int] = []

    def worker():
        try:
            largada.wait()
            feitos.append(jobs.propor_vagas(relogio=relogio))
        except BaseException as exc:  # noqa: BLE001
            erros.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)

    assert not erros
    assert sum(feitos) == n  # cada proposta contada por um único Worker
    with SessionLocal() as s:
        ativos = s.execute(
            select(Agendamento.vaga_id, Agendamento.solicitacao_id).where(
                Agendamento.vaga_id.in_(vagas), Agendamento.status == "PROPOSTO"
            )
        ).all()
        status = set(s.scalars(select(Solicitacao.status).where(Solicitacao.id.in_(solicitacoes))))
    assert len(ativos) == n
    assert len({v for v, _ in ativos}) == n  # nenhuma vaga com duas propostas
    assert {sid for _, sid in ativos} == set(solicitacoes)  # uma proposta por solicitação
    assert status == {"EM_PROPOSTA"}


# --- logs ----------------------------------------------------------------------------------


def test_am008_logs_dos_jobs_e_rotas_sem_nome_nem_cpf(
    api, sessao, paciente, mundo, agenda, rodar, relogio, caplog
):
    caplog.set_level(logging.DEBUG)
    criar_vaga(sessao, agenda, as_9h())
    sid = solicitacao_na_fila(sessao, paciente, mundo.fila)
    rodar(jobs.gerar_vagas)
    rodar(jobs.propor_vagas)
    confirmar(api, ativo_de(sessao, sid).id)
    relogio.avancar(timedelta(hours=48))
    rodar(jobs.expirar_propostas)

    p = sessao.get(Paciente, paciente.id)
    assert "propor_vagas" in caplog.text
    for dado in (p.nome, p.cpf, "Maria"):
        assert dado not in caplog.text


# --- Parte 2: presença, agenda do dia, cancelamento e painel de vagas ----------------------

INICIO = as_9h()  # vaga da `proposta`: quinta 29/10, 9h em Recife; tolerância da fila 60 min


@pytest.fixture
def confirmada(api, proposta):
    assert confirmar(api, proposta.id).status_code == 200
    return proposta


def atendente_de(sessao, *filas, papel="ATENDENTE"):
    usuario = criar_equipe(sessao, papel, filas=filas)
    return usuario, entrar(novo_cliente(), usuario.email)


def presenca(cliente, agendamento_id, compareceu, com_csrf=True):
    return cliente.post(
        f"/api/v1/equipe/agendamentos/{agendamento_id}/presenca",
        json={"compareceu": compareceu},
        headers=csrf(cliente) if com_csrf else {},
    )


def no_instante(relogio, instante, sessao, *usuarios):
    """Muda o relógio e refaz os logins (o access token vence com ele)."""
    relogio.instante = instante
    return [entrar(novo_cliente(), u.email) for u in usuarios]


def cancelar_solicitacao(cliente, sid, motivo_codigo="NAO_PRECISO_MAIS"):
    return cliente.post(
        f"/api/v1/solicitacoes/{sid}/cancelar",
        json={"motivo_codigo": motivo_codigo},
        headers=csrf(cliente),
    )


def test_uc008_compareceu_antes_do_inicio_responde_409(sessao, mundo, confirmada, relogio):
    usuario, _ = atendente_de(sessao, mundo.fila)
    (equipe,) = no_instante(relogio, INICIO - timedelta(seconds=1), sessao, usuario)

    resposta = presenca(equipe, confirmada.id, True)

    assert resposta.status_code == 409
    assert resposta.json()["type"] == "/problemas/transicao-invalida"
    sessao.expire_all()
    assert sessao.get(Agendamento, confirmada.id).status == "CONFIRMADO"


def test_uc008_compareceu_a_partir_do_inicio_encerra_como_atendida(
    sessao, mundo, confirmada, relogio
):
    usuario, _ = atendente_de(sessao, mundo.fila)
    (equipe,) = no_instante(relogio, INICIO, sessao, usuario)

    resposta = presenca(equipe, confirmada.id, True)

    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["status"] == "ATENDIDA"
    assert resposta.json()["historico"][-1]["tipo"] == "ATENDIDA"
    sessao.expire_all()
    assert sessao.get(Agendamento, confirmada.id).status == "REALIZADO"
    sid = confirmada.solicitacao_id
    assert (
        contar(
            sessao,
            Outbox,
            Outbox.agregado_id == sid,
            Outbox.tipo_evento == "ATENDIMENTO_REGISTRADO",
        )
        == 1
    )
    assert (
        contar(
            sessao,
            Auditoria,
            Auditoria.entidade_id == confirmada.id,
            Auditoria.acao == "REGISTRAR_COMPARECIMENTO",
            Auditoria.ator_usuario_id == usuario.id,
        )
        == 1
    )


@pytest.mark.parametrize("depois_do_inicio", [timedelta(minutes=30), timedelta(minutes=60)])
def test_uc008_falta_antes_do_fim_da_tolerancia_responde_409(
    sessao, mundo, confirmada, relogio, depois_do_inicio
):
    usuario, _ = atendente_de(sessao, mundo.fila)
    (equipe,) = no_instante(relogio, INICIO + depois_do_inicio, sessao, usuario)

    resposta = presenca(equipe, confirmada.id, False)

    assert resposta.status_code == 409
    assert resposta.json()["type"] == "/problemas/tolerancia-nao-encerrada"
    sessao.expire_all()
    assert sessao.get(Agendamento, confirmada.id).status == "CONFIRMADO"


def test_uc008_falta_depois_da_tolerancia_volta_para_o_fim_da_fila(
    api, sessao, paciente, mundo, confirmada, relogio
):
    usuario, _ = atendente_de(sessao, mundo.fila)
    agora = INICIO + timedelta(minutes=60, seconds=1)
    (equipe,) = no_instante(relogio, agora, sessao, usuario)

    resposta = presenca(equipe, confirmada.id, False)

    assert resposta.status_code == 200, resposta.text
    sessao.expire_all()
    assert sessao.get(Agendamento, confirmada.id).status == "FALTOU"
    s = sessao.get(Solicitacao, confirmada.solicitacao_id)
    assert s.status == "NA_FILA" and s.data_entrada_fila == agora
    entrar(api, paciente.cpf)
    detalhe = api.get(f"/api/v1/solicitacoes/{s.id}").json()
    assert tipos(detalhe)[-2:] == ["FALTOU", "REENTROU_NA_FILA"]
    assert "não compareceu à consulta" in motivos(detalhe)
    assert not chaves(detalhe) & CHAVES_PROIBIDAS
    assert (
        contar(sessao, Outbox, Outbox.agregado_id == s.id, Outbox.tipo_evento == "FALTA_REGISTRADA")
        == 1
    )


def test_uc008_presenca_de_proposta_nao_confirmada_responde_409(sessao, mundo, proposta, relogio):
    usuario, _ = atendente_de(sessao, mundo.fila)
    (equipe,) = no_instante(relogio, INICIO + timedelta(hours=2), sessao, usuario)

    assert presenca(equipe, proposta.id, True).status_code == 409
    assert presenca(equipe, proposta.id, False).status_code == 409


def test_uc008_presenca_fora_do_escopo_404_gestor_403_sem_csrf_403(
    sessao, mundo, confirmada, relogio
):
    outra, _ = atendente_de(sessao, mundo.fila_outra_unidade)
    gestor, _ = atendente_de(sessao, mundo.fila, papel="GESTOR")
    dono, _ = atendente_de(sessao, mundo.fila)
    de_outra, do_gestor, equipe = no_instante(relogio, INICIO, sessao, outra, gestor, dono)

    assert presenca(de_outra, confirmada.id, True).status_code == 404
    assert presenca(equipe, uuid4(), True).status_code == 404
    assert presenca(do_gestor, confirmada.id, True).status_code == 403
    assert presenca(equipe, confirmada.id, True, com_csrf=False).status_code == 403
    sessao.expire_all()
    assert sessao.get(Agendamento, confirmada.id).status == "CONFIRMADO"


def test_uc008_agenda_do_dia(sessao, mundo, confirmada, relogio):
    usuario, equipe = atendente_de(sessao, mundo.fila)
    _, de_outra = atendente_de(sessao, mundo.fila_outra_unidade)
    url = f"/api/v1/equipe/filas/{mundo.fila}/agendamentos"

    itens = equipe.get(url, params={"data": "2026-10-29"}).json()

    assert len(itens) == 1
    item = itens[0]
    assert item["id"] == str(confirmada.id) and item["status"] == "CONFIRMADO"
    assert item["inicio"] == "2026-10-29T09:00:00-03:00"
    assert item["paciente_nome"] == "Maria S."
    assert item["presenca_registrada"] is False
    assert equipe.get(url, params={"data": "2026-10-28"}).json() == []
    assert equipe.get(url, params={"data": "9999-12-31"}).status_code == 422
    assert de_outra.get(url, params={"data": "2026-10-29"}).status_code == 404
    assert (
        contar(
            sessao,
            Auditoria,
            Auditoria.acao == "CONSULTAR_AGENDAMENTOS",
            Auditoria.ator_usuario_id == usuario.id,
        )
        == 2
    )


# --- cancelamento com proposta ou consulta (UC-005 A1) e reaproveitamento -----------------


def test_uc005_rn005_reaproveitamento_cancelada_vai_para_o_proximo(
    api, sessao, paciente, mundo, confirmada, rodar
):
    b = na_fila(sessao, mundo.fila, entrada=T0 + timedelta(days=1))
    sid = confirmada.solicitacao_id

    resposta = cancelar_solicitacao(api, sid)

    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["status"] == "CANCELADA"
    assert resposta.json()["agendamento_ativo"] is None
    sessao.expire_all()
    a = sessao.get(Agendamento, confirmada.id)
    assert (a.status, a.motivo_cancelamento) == ("CANCELADO", "CANCELADO_PELO_PACIENTE")
    outbox = sessao.scalar(
        select(Outbox).where(
            Outbox.agregado_id == sid, Outbox.tipo_evento == "AGENDAMENTO_CANCELADO"
        )
    )
    assert outbox.payload["agendamento_id"] == str(a.id)
    assert (
        contar(
            sessao,
            Auditoria,
            Auditoria.entidade_id == a.id,
            Auditoria.acao == "CANCELAR_AGENDAMENTO",
        )
        == 1
    )

    rodar(jobs.propor_vagas)

    assert ativo_de(sessao, b).vaga_id == confirmada.vaga_id


def test_uc005_cancelar_com_proposta_pendente(api, sessao, proposta):
    resposta = cancelar_solicitacao(api, proposta.solicitacao_id)

    assert resposta.status_code == 200, resposta.text
    sessao.expire_all()
    assert sessao.get(Agendamento, proposta.id).status == "CANCELADO"
    assert sessao.get(Solicitacao, proposta.solicitacao_id).status == "CANCELADA"


def test_uc005_cancelar_depois_do_inicio_da_vaga_responde_409(
    api, sessao, paciente, confirmada, relogio
):
    relogio.instante = INICIO
    entrar(api, paciente.cpf)

    resposta = cancelar_solicitacao(api, confirmada.solicitacao_id)

    assert resposta.status_code == 409
    assert resposta.json()["type"] == "/problemas/transicao-invalida"
    sessao.expire_all()
    assert sessao.get(Agendamento, confirmada.id).status == "CONFIRMADO"
    assert sessao.get(Solicitacao, confirmada.solicitacao_id).status == "AGENDADA"


# --- painel de vagas -----------------------------------------------------------------------


def test_rn016_painel_de_vagas_destaca_livre_sem_proposta(
    api, sessao, mundo, agenda, rodar, relogio
):
    curta = criar_vaga(sessao, agenda, relogio.agora() + timedelta(hours=30))
    proposta = criar_vaga(sessao, agenda, as_9h())
    livre = criar_vaga(sessao, agenda, as_9h(hora=time(10)))
    bloqueada = criar_vaga(sessao, agenda, as_9h(hora=time(11)))
    sessao.get(Vaga, bloqueada).status_admin = "BLOQUEADA"
    na_fila(sessao, mundo.fila)
    rodar(jobs.propor_vagas)
    usuario, equipe = atendente_de(sessao, mundo.fila)
    _, de_outra = atendente_de(sessao, mundo.fila_outra_unidade)
    url = f"/api/v1/equipe/filas/{mundo.fila}/vagas"
    periodo = {"de": "2026-10-19", "ate": "2026-10-29"}

    corpo = equipe.get(url, params=periodo).json()

    situacoes = {i["id"]: i["situacao"] for i in corpo["itens"]}
    assert situacoes == {
        str(curta): "LIVRE_SEM_PROPOSTA",
        str(proposta): "PROPOSTA",
        str(livre): "LIVRE",
        str(bloqueada): "BLOQUEADA",
    }
    assert (corpo["total"], corpo["sem_proposta"]) == (4, 1)
    assert de_outra.get(url, params=periodo).status_code == 404
    assert equipe.get(url, params={"de": "2026-10-29", "ate": "2026-10-19"}).status_code == 422
    assert equipe.get(url, params={"de": "2026-10-01", "ate": "2026-12-01"}).status_code == 422
    assert (
        contar(
            sessao,
            Auditoria,
            Auditoria.acao == "CONSULTAR_VAGAS",
            Auditoria.ator_usuario_id == usuario.id,
        )
        == 1
    )


def test_am008_logs_da_parte_2_sem_nome_nem_cpf(
    api, sessao, paciente, mundo, confirmada, rodar, relogio, caplog
):
    caplog.set_level(logging.DEBUG)
    usuario, equipe = atendente_de(sessao, mundo.fila)
    equipe.get(f"/api/v1/equipe/filas/{mundo.fila}/agendamentos", params={"data": "2026-10-29"})
    equipe.get(
        f"/api/v1/equipe/filas/{mundo.fila}/vagas", params={"de": "2026-10-19", "ate": "2026-10-29"}
    )
    (equipe,) = no_instante(relogio, INICIO + timedelta(hours=2), sessao, usuario)
    assert presenca(equipe, confirmada.id, False).status_code == 200
    rodar(jobs.propor_vagas)

    p = sessao.get(Paciente, paciente.id)
    assert "presenca registrada" in caplog.text
    for dado in (p.nome, p.cpf, "Maria"):
        assert dado not in caplog.text


def test_am007_agenda_e_vagas_leitura_de_gestor_e_admin_e_negada_ao_paciente(
    api, sessao, paciente, mundo
):
    rotas = [
        (f"/api/v1/equipe/filas/{mundo.fila}/agendamentos", {"data": "2026-10-29"}),
        (f"/api/v1/equipe/filas/{mundo.fila}/vagas", {"de": "2026-10-19", "ate": "2026-10-29"}),
    ]
    _, gestor = atendente_de(sessao, mundo.fila, papel="GESTOR")
    _, admin = atendente_de(sessao, papel="ADMIN")

    for url, params in rotas:
        assert gestor.get(url, params=params).status_code == 200
        assert admin.get(url, params=params).status_code == 200
        assert api.get(url, params=params).status_code == 403  # `api` é o paciente logado
