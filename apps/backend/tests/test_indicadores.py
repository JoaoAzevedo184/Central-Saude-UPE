"""Indicadores do gestor (GET /equipe/indicadores): fórmulas, escopo, auditoria e custo.

RF-036, RF-037, RN-021, AM-007, AM-020, ADR-025.
"""

from datetime import UTC, date, datetime, time, timedelta
from itertools import count
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import event, select, text

from app.api.main import app
from app.config import get_settings
from app.infra import indicadores as consultas
from app.infra.modelos import (
    Agenda,
    Agendamento,
    Auditoria,
    HistoricoSolicitacao,
    Solicitacao,
    Vaga,
)
from tests.fila_sintetica import chaves, criar_equipe, criar_paciente, entrar, montar_mundo
from tests.test_auth import novo_cliente

pytestmark = pytest.mark.integracao

RECIFE = ZoneInfo("America/Recife")
URL = "/api/v1/equipe/indicadores"
# O relógio dos testes marca segunda, 19/10/2026 12:00 UTC. O período cobre as semanas de 5 e 12/10.
DE, ATE = "2026-10-05", "2026-10-18"
SEMANA_1 = datetime(2026, 10, 7, 15, tzinfo=UTC)
SEMANA_2 = datetime(2026, 10, 14, 15, tzinfo=UTC)
FUTURO = datetime(2026, 10, 25, 15, tzinfo=UTC)
_n = count()


@pytest.fixture
def mundo(sessao):
    return montar_mundo(sessao)


@pytest.fixture
def gestor(api, sessao, mundo):
    usuario = criar_equipe(sessao, "GESTOR")
    entrar(api, usuario.email)
    return usuario


def consultar(cliente, **params):
    return cliente.get(URL, params={"de": DE, "ate": ATE, **params})


class Fabrica:
    """Cria agenda, vaga, solicitação, histórico e agendamento com datas escolhidas."""

    def __init__(self, sessao):
        self.sessao = sessao
        self.agendas: dict = {}

    def vaga(self, fila, inicio, status_admin="ATIVA"):
        if fila not in self.agendas:
            a = Agenda(
                fila_id=fila,
                profissional="Dra. Sintética",
                dias_semana=[1, 2, 3, 4, 5, 6, 7],
                hora_inicio=time(8),
                hora_fim=time(12),
                duracao_min=60,
                vigencia_inicio=date(2026, 1, 1),
            )
            self.sessao.add(a)
            self.sessao.flush()
            self.agendas[fila] = a.id
        v = Vaga(
            agenda_id=self.agendas[fila],
            inicio=inicio + timedelta(minutes=next(_n)),  # evita colidir (agenda, início)
            fim=inicio + timedelta(hours=1, minutes=next(_n)),
            status_admin=status_admin,
        )
        self.sessao.add(v)
        self.sessao.flush()
        return v

    def solicitacao(self, fila, criada_em=SEMANA_1, status="AGENDADA", motivo=None, entrou=None):
        _, paciente = criar_paciente(self.sessao, login=False)
        s = Solicitacao(
            paciente_id=paciente.id,
            fila_id=fila,
            status=status,
            classificacao_risco=None if status == "CANCELADA" else "AMARELO",
            data_pedido=date(2026, 10, 1),
            criada_em=criada_em,
            motivo_cancelamento=motivo,
            data_entrada_fila=entrou if status == "NA_FILA" else None,
        )
        self.sessao.add(s)
        self.sessao.flush()
        if entrou:
            self.sessao.add(
                HistoricoSolicitacao(
                    solicitacao_id=s.id,
                    tipo="ENTROU_NA_FILA",
                    visivel_paciente=True,
                    ocorrido_em=entrou,
                )
            )
            self.sessao.flush()
        return s

    def agendamento(
        self,
        fila,
        status,
        *,
        proposto_em=SEMANA_1,
        inicio=SEMANA_2,
        confirmado_em=None,
        motivo=None,
        vaga=None,
        solicitacao=None,
        entrou=None,
    ):
        vaga = vaga or self.vaga(fila, inicio)
        solicitacao = solicitacao or self.solicitacao(fila, proposto_em, entrou=entrou)
        a = Agendamento(
            solicitacao_id=solicitacao.id,
            vaga_id=vaga.id,
            status=status,
            proposto_em=proposto_em,
            expira_em=proposto_em + timedelta(hours=48),
            respondido_em=None if status == "PROPOSTO" else proposto_em + timedelta(hours=1),
            confirmado_em=confirmado_em,
            motivo_cancelamento=motivo,
        )
        self.sessao.add(a)
        self.sessao.flush()
        return a


@pytest.fixture
def fab(sessao):
    return Fabrica(sessao)


def totais(resposta):
    assert resposta.status_code == 200, resposta.text
    return resposta.json()["totais"]


# --- acesso ---------------------------------------------------------------------------------


def test_rf036_so_gestor_e_admin_leem(api, sessao, mundo):
    assert consultar(api).status_code == 401
    for papel, esperado in (("ATENDENTE", 403), ("GESTOR", 200), ("ADMIN", 200)):
        cliente = novo_cliente()
        entrar(cliente, criar_equipe(sessao, papel, filas=[mundo.fila]).email)
        assert consultar(cliente).status_code == esperado, papel
    paciente = novo_cliente()
    entrar(paciente, criar_paciente(sessao)[1].cpf)
    assert consultar(paciente).status_code == 403


@pytest.mark.parametrize(
    "params",
    [
        {"de": "2026-10-18", "ate": "2026-10-05"},
        {"de": "2025-10-18", "ate": "2026-10-19"},  # 367 dias
        {"de": "2026-10-05"},
        {"de": "ontem", "ate": "2026-10-18"},
    ],
)
def test_rf036_periodo_invalido_responde_422(api, gestor, params):
    assert api.get(URL, params=params).status_code == 422


def test_rf036_periodo_de_366_dias_vale(api, gestor):
    assert api.get(URL, params={"de": "2025-10-19", "ate": "2026-10-19"}).status_code == 200


# --- escopo ----------------------------------------------------------------------------------


def test_adr025_gestor_so_conta_as_unidades_atribuidas(api, sessao, mundo, fab):
    fab.agendamento(mundo.fila, "CONFIRMADO", confirmado_em=SEMANA_1)
    fab.agendamento(mundo.fila_outra_unidade, "CONFIRMADO", confirmado_em=SEMANA_1)
    do_t1 = criar_equipe(sessao, "GESTOR", unidades=[mundo.unidade])
    entrar(api, do_t1.email)
    assert totais(consultar(api))["confirmadas"] == 1
    assert consultar(api, fila_id=str(mundo.fila_outra_unidade)).status_code == 404
    assert consultar(api, unidade_id=str(mundo.outra_unidade)).status_code == 404
    assert consultar(api, unidade_id="00000000-0000-0000-0000-000000000000").status_code == 404
    # fila de outra unidade combinada com a unidade atribuída também não casa
    pedido = {"unidade_id": str(mundo.unidade), "fila_id": str(mundo.fila_outra_unidade)}
    assert consultar(api, **pedido).status_code == 404


def test_adr025_admin_e_gestor_sem_unidade_veem_a_central_e_filtram(api, sessao, mundo, fab):
    fab.agendamento(mundo.fila, "CONFIRMADO", confirmado_em=SEMANA_1)
    fab.agendamento(mundo.fila_outra_unidade, "CONFIRMADO", confirmado_em=SEMANA_1)
    entrar(api, criar_equipe(sessao, "ADMIN").email)
    assert totais(consultar(api))["confirmadas"] == 2
    assert totais(consultar(api, unidade_id=str(mundo.outra_unidade)))["confirmadas"] == 1
    assert totais(consultar(api, fila_id=str(mundo.fila)))["confirmadas"] == 1


# --- propostas -------------------------------------------------------------------------------


def test_rn021_taxas_de_proposta_usam_as_encerradas_como_denominador(api, gestor, mundo, fab):
    f = mundo.fila
    for _ in range(2):
        fab.agendamento(f, "CONFIRMADO", confirmado_em=SEMANA_1)
    # confirmada e depois cancelada pelo paciente continua confirmada
    fab.agendamento(f, "CANCELADO", confirmado_em=SEMANA_1, motivo="CANCELADO_PELO_PACIENTE")
    fab.agendamento(f, "CANCELADO", motivo="RECUSADO_PELO_PACIENTE")
    fab.agendamento(f, "EXPIRADO")
    fab.agendamento(f, "CANCELADO", motivo="CANCELADO_PELO_PACIENTE")  # sem resposta
    fab.agendamento(f, "PROPOSTO")  # pendente: fora das taxas
    t = totais(consultar(api))
    assert (t["confirmadas"], t["recusadas"], t["expiradas"]) == (3, 1, 1)
    assert t["propostas_encerradas"] == 5
    assert t["propostas_canceladas_sem_resposta"] == 1
    assert (t["taxa_confirmacao"], t["taxa_recusa"], t["taxa_expiracao"]) == (0.6, 0.2, 0.2)


def test_rn021_proposta_fora_do_periodo_nao_conta(api, gestor, mundo, fab):
    fab.agendamento(
        mundo.fila,
        "CONFIRMADO",
        proposto_em=datetime(2026, 9, 30, 15, tzinfo=UTC),
        confirmado_em=SEMANA_1,
    )
    assert totais(consultar(api))["confirmadas"] == 0


# --- presença --------------------------------------------------------------------------------


def test_rn021_faltas_ancoram_na_vaga_e_dividem_pelos_registrados(api, gestor, mundo, fab):
    f = mundo.fila
    for _ in range(3):
        fab.agendamento(f, "REALIZADO", confirmado_em=SEMANA_1)
    fab.agendamento(f, "FALTOU", confirmado_em=SEMANA_1)
    # proposta fora do período, mas a vaga cai dentro: conta
    fab.agendamento(
        f, "FALTOU", proposto_em=datetime(2026, 9, 1, tzinfo=UTC), confirmado_em=SEMANA_1
    )
    # vaga fora do período: não conta
    fab.agendamento(f, "FALTOU", inicio=datetime(2026, 9, 1, 15, tzinfo=UTC))
    t = totais(consultar(api))
    assert (t["realizadas"], t["faltas"], t["taxa_faltas"]) == (3, 2, 0.4)


# --- desistência -----------------------------------------------------------------------------


def test_rn021_desistencia_e_cancelamento_do_paciente_entre_as_criadas(api, gestor, mundo, fab):
    f = mundo.fila
    fab.solicitacao(f)
    fab.solicitacao(f)
    fab.solicitacao(f, status="CANCELADA", motivo="NAO_PRECISO_MAIS")
    fab.solicitacao(f, status="CANCELADA")  # cancelada sem motivo do paciente: não é desistência
    fab.solicitacao(
        f, criada_em=datetime(2026, 9, 1, tzinfo=UTC), status="CANCELADA", motivo="NAO_PRECISO_MAIS"
    )
    t = totais(consultar(api))
    assert (t["solicitacoes_criadas"], t["desistencias"], t["taxa_desistencia"]) == (4, 1, 0.25)


# --- vagas -----------------------------------------------------------------------------------


def test_rn021_vagas_ofertadas_ocupadas_reaproveitadas_e_perdidas(api, gestor, mundo, fab):
    f = mundo.fila
    passada = datetime(2026, 10, 8, 15, tzinfo=UTC)
    fab.agendamento(f, "REALIZADO", inicio=passada, confirmado_em=SEMANA_1)
    fab.agendamento(f, "FALTOU", inicio=passada, confirmado_em=SEMANA_1)
    # CONFIRMADO de vaga futura (ainda no período) conta como ocupada e não é perdida
    fab.agendamento(
        f, "CONFIRMADO", inicio=datetime(2026, 10, 22, 15, tzinfo=UTC), confirmado_em=SEMANA_2
    )
    fab.vaga(f, datetime(2026, 10, 16, 15, tzinfo=UTC))  # passou livre: perdida
    fab.agendamento(f, "EXPIRADO", inicio=passada)  # proposta que expirou e a vaga passou: perdida
    fab.vaga(
        f, datetime(2026, 10, 9, 15, tzinfo=UTC), status_admin="BLOQUEADA"
    )  # fora das ofertadas
    fab.vaga(f, FUTURO)  # livre e futura: ofertada, ainda não perdida
    fab.vaga(f, datetime(2026, 11, 20, 15, tzinfo=UTC))  # fora do período
    # reaproveitada: expirou para uma solicitação e outra confirmou a mesma vaga
    vaga = fab.vaga(f, passada)
    fab.agendamento(f, "EXPIRADO", vaga=vaga, proposto_em=SEMANA_1)
    fab.agendamento(
        f, "REALIZADO", vaga=vaga, proposto_em=SEMANA_1 + timedelta(days=1), confirmado_em=SEMANA_2
    )
    t = totais(consultar(api, ate="2026-10-26"))
    assert t["vagas_ofertadas"] == 7
    assert t["vagas_ocupadas"] == 4
    assert t["vagas_reaproveitadas"] == 1
    assert t["vagas_perdidas"] == 2


def test_rn021_mesma_solicitacao_confirmando_depois_nao_reaproveita(api, gestor, mundo, fab):
    vaga = fab.vaga(mundo.fila, SEMANA_2)
    solicitacao = fab.solicitacao(mundo.fila)
    fab.agendamento(mundo.fila, "EXPIRADO", vaga=vaga, solicitacao=solicitacao)
    fab.agendamento(
        mundo.fila,
        "CONFIRMADO",
        vaga=vaga,
        solicitacao=solicitacao,
        proposto_em=SEMANA_1 + timedelta(days=1),
        confirmado_em=SEMANA_2,
    )
    assert totais(consultar(api))["vagas_reaproveitadas"] == 0


# --- tempo de espera -------------------------------------------------------------------------


def test_rn021_espera_vai_da_entrada_na_fila_a_primeira_confirmacao(api, gestor, mundo, fab):
    f = mundo.fila
    for dias in (2, 10):
        fab.agendamento(
            f, "CONFIRMADO", confirmado_em=SEMANA_1, entrou=SEMANA_1 - timedelta(days=dias)
        )
    # reconfirmou depois de cancelar: só a primeira confirmação conta
    s = fab.solicitacao(f, entrou=SEMANA_1 - timedelta(days=12))
    fab.agendamento(
        f,
        "CANCELADO",
        solicitacao=s,
        confirmado_em=SEMANA_1 - timedelta(days=5),
        motivo="CANCELADO_PELO_PACIENTE",
        proposto_em=SEMANA_1 - timedelta(days=6),
    )
    fab.agendamento(f, "CONFIRMADO", solicitacao=s, confirmado_em=SEMANA_2)
    resposta = consultar(api).json()["tempo_de_espera"]
    assert resposta == {"confirmacoes": 2, "mediana_dias": 6.0, "p90_dias": 9.2}


def test_rn021_espera_sem_confirmacao_e_nula(api, gestor):
    assert consultar(api).json()["tempo_de_espera"] == {
        "confirmacoes": 0,
        "mediana_dias": None,
        "p90_dias": None,
    }


# --- fila atual e série ----------------------------------------------------------------------


def test_rf037_fila_atual_por_cor_so_do_escopo(api, sessao, mundo, fab):
    for risco, fila in (
        ("VERMELHO", mundo.fila),
        ("VERMELHO", mundo.fila),
        ("VERDE", mundo.fila),
        ("VERMELHO", mundo.fila_outra_unidade),
    ):
        s = fab.solicitacao(fila, status="NA_FILA", entrou=SEMANA_1)
        s.classificacao_risco = risco
    fab.solicitacao(mundo.fila)  # AGENDADA: fora
    entrar(api, criar_equipe(sessao, "GESTOR", unidades=[mundo.unidade]).email)
    assert consultar(api).json()["fila_atual"] == {"VERMELHO": 2, "AMARELO": 0, "VERDE": 1}


def test_rf037_serie_semanal_comeca_na_segunda_e_tem_zeros(api, gestor, mundo, fab):
    fab.agendamento(mundo.fila, "CONFIRMADO", confirmado_em=SEMANA_1)
    # domingo 11/10 23:00 em Recife (02:00 UTC de segunda): ainda é a semana de 05/10
    fab.agendamento(mundo.fila, "EXPIRADO", proposto_em=datetime(2026, 10, 12, 2, tzinfo=UTC))
    corpo = api.get(URL, params={"de": "2026-10-07", "ate": "2026-10-27"}).json()
    semanas = {s["semana"]: s for s in corpo["semanas"]}
    assert list(semanas) == ["2026-10-05", "2026-10-12", "2026-10-19", "2026-10-26"]
    assert (semanas["2026-10-05"]["confirmadas"], semanas["2026-10-05"]["expiradas"]) == (1, 1)
    assert semanas["2026-10-12"]["propostas_encerradas"] == 0
    assert semanas["2026-10-12"]["taxa_confirmacao"] is None
    assert corpo["totais"]["propostas_encerradas"] == 2


def test_rf037_sem_dados_as_razoes_sao_nulas_e_as_contagens_zero(api, gestor):
    t = totais(consultar(api))
    razoes = {k: v for k, v in t.items() if k.startswith("taxa_")}
    assert razoes and all(v is None for v in razoes.values())
    assert all(v == 0 for k, v in t.items() if not k.startswith("taxa_"))


# --- auditoria, privacidade e custo ----------------------------------------------------------


def test_am007_leitura_e_auditada_so_com_periodo_e_filtros(api, sessao, mundo, gestor):
    consultar(api)
    consultar(api, unidade_id=str(mundo.unidade))
    consultar(api, fila_id=str(mundo.fila))
    linhas = sessao.scalars(
        select(Auditoria).where(Auditoria.acao == "CONSULTAR_INDICADORES").order_by(Auditoria.id)
    ).all()
    assert len(linhas) == 3
    por_entidade = {a.entidade: a.entidade_id for a in linhas}
    assert por_entidade == {"usuario": gestor.id, "unidade": mundo.unidade, "fila": mundo.fila}
    for a in linhas:
        assert a.ator_usuario_id == gestor.id
        assert set(a.dados_depois) == {"de", "ate", "unidade_id", "fila_id"}


def test_rf036_negada_nao_audita(api, sessao, mundo):
    entrar(api, criar_equipe(sessao, "ATENDENTE", filas=[mundo.fila]).email)
    consultar(api)
    assert sessao.scalar(select(Auditoria).where(Auditoria.acao == "CONSULTAR_INDICADORES")) is None


def test_adr007_resposta_sem_dado_de_paciente(api, gestor, mundo, fab):
    fab.agendamento(mundo.fila, "CONFIRMADO", confirmado_em=SEMANA_1, entrou=SEMANA_1)
    proibidas = {
        "nome",
        "cpf",
        "paciente_nome",
        "paciente_cpf",
        "paciente_id",
        "solicitacao_id",
        "posicao",
        "email",
    }
    assert not proibidas & chaves(consultar(api).json())


def test_rn021_numero_de_consultas_nao_depende_do_volume(api, sessao, mundo, gestor, fab):
    def consultas() -> int:
        usadas = []

        def contar(_c, _cur, statement, *_):
            if not statement.startswith(("SAVEPOINT", "RELEASE")):
                usadas.append(statement[:70])

        event.listen(sessao.get_bind(), "before_cursor_execute", contar)
        try:
            assert consultar(api).status_code == 200
        finally:
            event.remove(sessao.get_bind(), "before_cursor_execute", contar)
        return usadas

    consultas()  # aquece: o commit da auditoria expira o usuário da sessão compartilhada do teste
    vazio = consultas()
    for _ in range(12):
        fab.agendamento(mundo.fila, "CONFIRMADO", confirmado_em=SEMANA_1, entrou=SEMANA_1)
        fab.solicitacao(mundo.fila, status="NA_FILA", entrou=SEMANA_1)
    com_dados = consultas()
    assert len(com_dados) == len(vazio), (vazio, com_dados)


def test_rn021_ocupadas_diz_que_inclui_confirmado_de_vaga_futura():
    descricao = app.openapi()["components"]["schemas"]["Resumo"]["properties"]["vagas_ocupadas"][
        "description"
    ]
    assert "CONFIRMADO de vaga futura" in descricao


def test_rn021_confirmada_que_depois_cancelou_nao_reaproveita(api, gestor, mundo, fab):
    vaga = fab.vaga(mundo.fila, SEMANA_2)
    fab.agendamento(mundo.fila, "EXPIRADO", vaga=vaga)
    fab.agendamento(
        mundo.fila,
        "CANCELADO",
        vaga=vaga,
        proposto_em=SEMANA_1 + timedelta(days=1),
        confirmado_em=SEMANA_2,
        motivo="CANCELADO_PELA_EQUIPE",
    )
    t = totais(consultar(api))
    assert (t["vagas_reaproveitadas"], t["vagas_ocupadas"]) == (0, 0)


def test_rn021_periodo_fecha_a_meia_noite_de_recife(api, gestor, mundo, fab):
    # 05/10 00:00 em Recife = 03:00 UTC (entra); 04/10 23:59 (fica fora); 19/10 00:00 (fica fora)
    for instante in (
        datetime(2026, 10, 5, 3, tzinfo=UTC),
        datetime(2026, 10, 5, 2, 59, tzinfo=UTC),
        datetime(2026, 10, 19, 3, tzinfo=UTC),
        datetime(2026, 10, 19, 2, 59, tzinfo=UTC),
    ):
        fab.agendamento(mundo.fila, "EXPIRADO", proposto_em=instante)
    assert totais(consultar(api))["expiradas"] == 2


def test_rn021_consultas_rodam_com_jit_desligado(api, sessao, gestor):
    vistos = []

    def ver(_c, _cur, statement, *_):
        vistos.append(statement)

    event.listen(sessao.get_bind(), "before_cursor_execute", ver)
    try:
        consultar(api)
    finally:
        event.remove(sessao.get_bind(), "before_cursor_execute", ver)
    primeira = next(i for i, c in enumerate(vistos) if "date_trunc" in c)
    assert any(c == "SET LOCAL jit = off" for c in vistos[:primeira])


def test_rn021_consulta_que_passa_do_limite_responde_503_neutro(api, sessao, gestor, monkeypatch):
    monkeypatch.setenv("INDICADORES_TIMEOUT_S", "0.05")
    get_settings.cache_clear()
    try:
        original = consultas.propostas

        def lenta(*args, **kwargs):
            sessao.execute(text("SELECT pg_sleep(0.5)"))
            return original(*args, **kwargs)

        monkeypatch.setattr(consultas, "propostas", lenta)
        resposta = consultar(api)
    finally:
        get_settings.cache_clear()
    assert resposta.status_code == 503
    assert resposta.headers["content-type"].startswith("application/problem+json")
    assert resposta.headers["retry-after"] == "30"
    corpo = resposta.json()
    assert corpo["type"] == "/problemas/consulta-demorada"
    assert "pg_sleep" not in resposta.text and "statement" not in resposta.text.lower()
    # a transação foi desfeita: nada auditado e a sessão continua utilizável
    assert sessao.scalar(select(Auditoria).where(Auditoria.acao == "CONSULTAR_INDICADORES")) is None
    assert sessao.scalar(text("SELECT 1")) == 1
