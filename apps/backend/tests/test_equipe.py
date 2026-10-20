"""Área da equipe: escopo, painel ordenado, classificação e critérios.

ADR-024, ADR-025, RN-007, RN-015, RF-031, RF-032, AM-007, AM-016.
"""

import logging
import random
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from sqlalchemy import func, select

from app.dominio.fila.ordenacao import ordenar_fila
from app.dominio.solicitacao import Solicitacao as SolicitacaoDominio
from app.infra.modelos import Auditoria, HistoricoSolicitacao, Outbox, Paciente, Solicitacao
from tests.fila_sintetica import (
    chaves,
    criar_equipe,
    criar_paciente,
    csrf,
    entrar,
    montar_mundo,
    na_fila,
)
from tests.test_auth import novo_cliente

pytestmark = pytest.mark.integracao

T0 = datetime(2026, 10, 1, 12, tzinfo=UTC)
ZERO = "00000000-0000-0000-0000-000000000000"


@pytest.fixture
def mundo(sessao):
    return montar_mundo(sessao)


@pytest.fixture
def atendente(api, sessao, mundo):
    usuario = criar_equipe(sessao, "ATENDENTE", filas=[mundo.fila])
    entrar(api, usuario.email)
    return usuario


def em_analise(api_paciente_sessao, mundo, respostas=()):
    """Cria uma solicitação EM_ANALISE pela API do paciente, num cliente separado."""
    sessao = api_paciente_sessao
    _, p = criar_paciente(sessao)
    cliente = entrar(novo_cliente(), p.cpf)
    resposta = cliente.post(
        "/api/v1/solicitacoes",
        json={
            "fila_id": str(mundo.fila),
            "origem_encaminhamento": "USF Sintética",
            "respostas": [{"criterio_id": str(c), "valor": v} for c, v in respostas],
        },
        headers=csrf(cliente),
    )
    assert resposta.status_code == 201, resposta.text
    return resposta.json()["id"]


def classificar(cliente, sid, risco="AMARELO", motivo=None):
    corpo = {"classificacao_risco": risco} | ({"motivo": motivo} if motivo else {})
    return cliente.post(
        f"/api/v1/equipe/solicitacoes/{sid}/classificar", json=corpo, headers=csrf(cliente)
    )


def responder(cliente, sid, respostas):
    return cliente.put(
        f"/api/v1/equipe/solicitacoes/{sid}/respostas",
        json={"respostas": [{"criterio_id": str(c), "valor": v} for c, v in respostas]},
        headers=csrf(cliente),
    )


def painel(cliente, fila, **params):
    resposta = cliente.get(f"/api/v1/equipe/filas/{fila}/solicitacoes", params=params)
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def contar(sessao, modelo, *filtros):
    return sessao.scalar(select(func.count()).select_from(modelo).where(*filtros))


# --- escopo e papéis ----------------------------------------------------------------------


def test_adr025_atendente_fora_do_escopo_recebe_404(api, sessao, mundo, atendente):
    alheia = na_fila(sessao, mundo.fila_outra_unidade, "VERDE", 0, T0)

    assert (
        api.get(f"/api/v1/equipe/filas/{mundo.fila_outra_unidade}/solicitacoes").status_code == 404
    )
    assert api.get(f"/api/v1/equipe/solicitacoes/{alheia}").status_code == 404
    assert classificar(api, alheia, "VERMELHO", "Tentativa sintética").status_code == 404
    assert responder(api, alheia, [(mundo.r_gestacoes, 3)]).status_code == 404
    assert sessao.get(Solicitacao, alheia).classificacao_risco == "VERDE"
    assert api.get(f"/api/v1/equipe/filas/{ZERO}/solicitacoes").status_code == 404


def test_adr025_atendente_sem_filas_ve_lista_vazia(api, sessao, mundo):
    sem_filas = criar_equipe(sessao, "ATENDENTE")
    entrar(api, sem_filas.email)

    assert api.get("/api/v1/equipe/filas").json() == []
    assert api.get(f"/api/v1/equipe/filas/{mundo.fila}/solicitacoes").status_code == 404


def test_adr025_gestor_sem_unidade_ve_a_central_inteira(api, sessao, mundo):
    gestor = criar_equipe(sessao, "GESTOR")
    entrar(api, gestor.email)

    ids = {f["id"] for f in api.get("/api/v1/equipe/filas").json()}

    assert {str(mundo.fila), str(mundo.fila_outra_unidade)} <= ids
    assert (
        api.get(f"/api/v1/equipe/filas/{mundo.fila_outra_unidade}/solicitacoes").status_code == 200
    )


def test_adr025_gestor_de_um_hospital_nao_ve_outro(api, sessao, mundo):
    gestor = criar_equipe(sessao, "GESTOR", unidades=[mundo.unidade])
    entrar(api, gestor.email)

    ids = {f["id"] for f in api.get("/api/v1/equipe/filas").json()}

    assert str(mundo.fila) in ids and str(mundo.fila_outra_unidade) not in ids
    assert (
        api.get(f"/api/v1/equipe/filas/{mundo.fila_outra_unidade}/solicitacoes").status_code == 404
    )


def test_adr025_filas_trazem_contagem_por_status(api, sessao, mundo, atendente):
    na_fila(sessao, mundo.fila, "VERDE", 0, T0)
    na_fila(sessao, mundo.fila, "AMARELO", 0, T0)

    (fila,) = api.get("/api/v1/equipe/filas").json()

    assert fila["contagem_por_status"]["NA_FILA"] == 2
    assert fila["contagem_por_status"]["EM_ANALISE"] == 0


ROTAS_DA_EQUIPE = [
    ("get", "/api/v1/equipe/filas"),
    ("get", f"/api/v1/equipe/filas/{ZERO}/solicitacoes"),
    ("get", f"/api/v1/equipe/solicitacoes/{ZERO}"),
    ("post", f"/api/v1/equipe/solicitacoes/{ZERO}/classificar"),
    ("put", f"/api/v1/equipe/solicitacoes/{ZERO}/respostas"),
]
ESCRITAS_DA_EQUIPE = [r for r in ROTAS_DA_EQUIPE if r[0] != "get"]


@pytest.mark.parametrize(("metodo", "caminho"), ROTAS_DA_EQUIPE)
def test_rbac_paciente_nas_rotas_da_equipe_retorna_403(api, sessao, metodo, caminho):
    _, p = criar_paciente(sessao)
    entrar(api, p.cpf)

    resposta = getattr(api, metodo)(caminho, headers=csrf(api))

    assert resposta.status_code == 403
    assert resposta.json()["type"] == "/problemas/sem-permissao"


@pytest.mark.parametrize("papel", ["GESTOR", "ADMIN"])
@pytest.mark.parametrize(("metodo", "caminho"), ESCRITAS_DA_EQUIPE)
def test_rbac_so_atendente_escreve(api, sessao, mundo, papel, metodo, caminho):
    usuario = criar_equipe(sessao, papel)
    entrar(api, usuario.email)

    resposta = getattr(api, metodo)(caminho, headers=csrf(api))

    assert resposta.status_code == 403


@pytest.mark.parametrize("papel", ["GESTOR", "ADMIN"])
def test_rbac_gestor_e_admin_leem_o_painel(api, sessao, mundo, papel):
    usuario = criar_equipe(sessao, papel)
    entrar(api, usuario.email)

    assert painel(api, mundo.fila)["total"] == 0


@pytest.mark.parametrize(("metodo", "caminho"), ROTAS_DA_EQUIPE)
def test_adr025_rotas_da_equipe_sem_sessao_retornam_401(api, metodo, caminho):
    api.cookies.set("csrf_token", "x")
    resposta = getattr(api, metodo)(caminho, headers={"X-CSRF-Token": "x"})

    assert resposta.status_code == 401


def test_adr028_suspenso_nao_le_o_painel(api, sessao, mundo, atendente, relogio):
    atendente.situacao, atendente.suspenso_em = "SUSPENSO", relogio.agora()
    sessao.flush()

    assert api.get(f"/api/v1/equipe/filas/{mundo.fila}/solicitacoes").status_code == 401


@pytest.mark.parametrize(("metodo", "caminho"), ESCRITAS_DA_EQUIPE)
def test_am002_escrita_da_equipe_sem_csrf_retorna_403(api, atendente, metodo, caminho):
    resposta = getattr(api, metodo)(caminho, json={})

    assert resposta.status_code == 403
    assert resposta.json()["type"] == "/problemas/csrf-invalido"


# --- classificar --------------------------------------------------------------------------


def test_uc007_classificar_em_analise_entra_na_fila(api, sessao, mundo, atendente, relogio):
    sid = em_analise(sessao, mundo)

    resposta = classificar(api, sid, "AMARELO", "Encaminhamento sintético conferido")

    assert resposta.status_code == 200, resposta.text
    s = sessao.get(Solicitacao, sid)
    assert (s.status, s.classificacao_risco) == ("NA_FILA", "AMARELO")
    assert s.data_entrada_fila == relogio.agora()
    eventos = sessao.execute(
        select(HistoricoSolicitacao.tipo, HistoricoSolicitacao.visivel_paciente)
        .where(HistoricoSolicitacao.solicitacao_id == sid, HistoricoSolicitacao.tipo != "CRIADA")
        .order_by(HistoricoSolicitacao.tipo)
    ).all()
    assert eventos == [("CLASSIFICADA", False), ("ENTROU_NA_FILA", True)]
    assert (
        contar(
            sessao, Outbox, Outbox.agregado_id == sid, Outbox.tipo_evento == "SOLICITACAO_NA_FILA"
        )
        == 1
    )
    auditoria = sessao.scalar(
        select(Auditoria).where(Auditoria.entidade_id == sid, Auditoria.acao == "CLASSIFICAR")
    )
    assert auditoria.ator_usuario_id == atendente.id
    assert auditoria.dados_depois["status"] == "NA_FILA"
    assert auditoria.dados_depois["classificacao_risco"] == "AMARELO"


def test_uc007_reclassificar_exige_motivo_e_nao_avisa_o_paciente(api, sessao, mundo, atendente):
    sid = em_analise(sessao, mundo)
    classificar(api, sid, "VERDE")

    sem_motivo = classificar(api, sid, "VERMELHO")
    com_motivo = classificar(api, sid, "VERMELHO", "Exame sintético alterado")

    assert sem_motivo.status_code == 422
    assert com_motivo.status_code == 200
    evento = sessao.scalar(
        select(HistoricoSolicitacao).where(
            HistoricoSolicitacao.solicitacao_id == sid,
            HistoricoSolicitacao.tipo == "RECLASSIFICADA",
        )
    )
    assert evento.motivo == "Exame sintético alterado" and not evento.visivel_paciente
    assert (
        contar(
            sessao, Outbox, Outbox.agregado_id == sid, Outbox.tipo_evento == "SOLICITACAO_NA_FILA"
        )
        == 1
    )
    assert sessao.scalar(
        select(Auditoria.id).where(Auditoria.entidade_id == sid, Auditoria.acao == "RECLASSIFICAR")
    )


@pytest.mark.parametrize("estado", ["EM_PROPOSTA", "AGENDADA", "ATENDIDA", "CANCELADA"])
def test_uc007_classificar_em_outro_estado_retorna_409(api, sessao, mundo, atendente, estado):
    sid = na_fila(sessao, mundo.fila, "VERDE", 0, T0)
    sessao.get(Solicitacao, sid).status = estado
    sessao.flush()

    resposta = classificar(api, sid, "VERMELHO", "Tentativa sintética")

    assert resposta.status_code == 409
    assert resposta.json()["type"] == "/problemas/transicao-invalida"


def test_am013_classificar_recusa_risco_invalido_e_campo_extra(api, sessao, mundo, atendente):
    sid = em_analise(sessao, mundo)
    url = f"/api/v1/equipe/solicitacoes/{sid}/classificar"

    azul = api.post(url, json={"classificacao_risco": "AZUL"}, headers=csrf(api))
    extra = api.post(url, json={"classificacao_risco": "VERDE", "nota": 99}, headers=csrf(api))

    assert azul.status_code == 422 and extra.status_code == 422
    assert sessao.get(Solicitacao, sid).status == "EM_ANALISE"


# --- critérios da regulação ---------------------------------------------------------------


def test_adr024_responder_criterios_recalcula_a_nota(api, sessao, mundo, atendente):
    sid = em_analise(sessao, mundo, [(mundo.p_filhos, True)])

    resposta = responder(api, sid, [(mundo.r_gestacoes, 3)])

    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["nota"] == 10 + 5 * 2
    assert {(r["codigo"], r["pontos"]) for r in resposta.json()["respostas"]} == {
        ("P_FILHOS", 10),
        ("R_GESTACOES", 10),
    }
    # Em análise não há posição: nenhuma RECLASSIFICADA.
    assert contar(sessao, HistoricoSolicitacao, HistoricoSolicitacao.tipo == "RECLASSIFICADA") == 0


def test_adr024_nota_nova_na_fila_grava_reclassificada(api, sessao, mundo, atendente):
    sid = em_analise(sessao, mundo)
    classificar(api, sid, "VERDE")

    responder(api, sid, [(mundo.r_gestacoes, 3)])
    responder(api, sid, [(mundo.r_gestacoes, 4)])  # mesma faixa: nota igual, sem evento

    eventos = sessao.scalars(
        select(HistoricoSolicitacao).where(
            HistoricoSolicitacao.solicitacao_id == sid,
            HistoricoSolicitacao.tipo == "RECLASSIFICADA",
        )
    ).all()
    assert [(e.motivo, e.visivel_paciente) for e in eventos] == [("nota recalculada", False)]
    assert sessao.get(Solicitacao, sid).nota == 10
    assert (
        contar(
            sessao, Auditoria, Auditoria.entidade_id == sid, Auditoria.acao == "RESPONDER_CRITERIOS"
        )
        == 2
    )


@pytest.mark.parametrize(
    "respostas",
    [
        lambda m: [(m.p_filhos, True)],  # origem PACIENTE
        lambda m: [(m.criterio_outra_fila, True)],  # outra fila
        lambda m: [(m.r_gestacoes, "muitas")],  # tipo errado
    ],
)
def test_adr024_equipe_nao_responde_criterio_do_paciente_nem_de_outra_fila(
    api, sessao, mundo, atendente, respostas
):
    sid = em_analise(sessao, mundo)

    resposta = responder(api, sid, respostas(mundo))

    assert resposta.status_code == 422
    assert sessao.get(Solicitacao, sid).nota == 0


def test_adr024_responder_em_solicitacao_cancelada_retorna_409(api, sessao, mundo, atendente):
    sid = na_fila(sessao, mundo.fila, "VERDE", 0, T0)
    sessao.get(Solicitacao, sid).status = "CANCELADA"
    sessao.flush()

    assert responder(api, sid, [(mundo.r_gestacoes, 3)]).status_code == 409
    # Estado de origem vem antes da validação da entrada.
    assert responder(api, sid, [(mundo.p_filhos, True)]).status_code == 409


def test_rn010_responder_criterios_audita_as_respostas_mesmo_sem_mudar_a_nota(
    api, sessao, mundo, atendente
):
    sid = em_analise(sessao, mundo)
    responder(api, sid, [(mundo.r_gestacoes, 3)])

    responder(api, sid, [(mundo.r_gestacoes, 4)])  # mesma faixa, mesma nota

    ultima = sessao.scalars(
        select(Auditoria)
        .where(Auditoria.entidade_id == sid, Auditoria.acao == "RESPONDER_CRITERIOS")
        .order_by(Auditoria.ocorrido_em, Auditoria.id)
    ).all()
    chave = str(mundo.r_gestacoes)
    assert {a.dados_antes["respostas"][chave] for a in ultima} == {None, 3}
    assert {a.dados_depois["respostas"][chave] for a in ultima} == {3, 4}


# --- painel: ordem e posição --------------------------------------------------------------


def test_rn015_empate_resolvido_pela_chegada(api, sessao, mundo, atendente):
    depois = na_fila(sessao, mundo.fila, "AMARELO", 5, T0 + timedelta(hours=1))
    antes = na_fila(sessao, mundo.fila, "AMARELO", 5, T0)

    itens = painel(api, mundo.fila)["itens"]

    assert [(i["id"], i["posicao"]) for i in itens] == [(str(antes), 1), (str(depois), 2)]


def test_rn015_reclassificar_para_vermelho_muda_a_posicao(api, sessao, mundo, atendente, relogio):
    primeiro = na_fila(sessao, mundo.fila, "AMARELO", 50, T0)
    sid = em_analise(sessao, mundo)
    classificar(api, sid, "VERDE")
    assert [i["id"] for i in painel(api, mundo.fila)["itens"]] == [str(primeiro), sid]
    relogio.avancar(timedelta(minutes=1))  # o access token vale 15 min

    classificar(api, sid, "VERMELHO", "Piora sintética")

    itens = painel(api, mundo.fila)["itens"]
    assert [(i["id"], i["posicao"]) for i in itens] == [(sid, 1), (str(primeiro), 2)]
    assert itens[0]["ultima_mudanca"]["tipo"] == "RECLASSIFICADA"
    assert set(itens[0]["ultima_mudanca"]) == {"tipo", "ocorrido_em"}  # motivo só no detalhe
    assert "Piora sintética" not in str(itens)
    detalhe = api.get(f"/api/v1/equipe/solicitacoes/{sid}").json()
    assert detalhe["historico"][-1]["motivo"] == "Piora sintética"
    assert itens[1]["ultima_mudanca"] is None  # gravada direto, sem histórico


def test_rf031_posicao_real_na_segunda_pagina(api, sessao, mundo, atendente):
    ids = [na_fila(sessao, mundo.fila, "VERDE", 0, T0 + timedelta(minutes=i)) for i in range(5)]
    em_analise(sessao, mundo)  # fora da fila: não conta na posição

    pagina = painel(api, mundo.fila, status="NA_FILA", limit=2, offset=2)

    assert pagina["total"] == 5
    assert [(i["id"], i["posicao"]) for i in pagina["itens"]] == [
        (str(ids[2]), 3),
        (str(ids[3]), 4),
    ]


def test_rf031_posicao_so_para_na_fila_e_ordenacao_por_chegada(api, sessao, mundo, atendente):
    tarde = na_fila(sessao, mundo.fila, "VERMELHO", 0, T0 + timedelta(days=1))
    cedo = na_fila(sessao, mundo.fila, "VERDE", 0, T0)
    analise = em_analise(sessao, mundo)

    todos = painel(api, mundo.fila)["itens"]
    chegada = painel(api, mundo.fila, ordenacao="chegada")["itens"]

    posicoes = {i["id"]: i["posicao"] for i in todos}
    assert posicoes == {str(tarde): 1, str(cedo): 2, analise: None}
    assert [i["id"] for i in chegada] == [str(cedo), str(tarde), analise]


def test_rn015_ordem_da_sql_igual_a_ordenar_fila(api, sessao, mundo, atendente):
    sorteio = random.Random(15)
    criadas = []
    for _ in range(40):
        # Poucos valores distintos, para forçar empates em risco, nota e chegada.
        risco = sorteio.choice(["VERMELHO", "AMARELO", "VERDE"])
        nota = sorteio.choice([0, 5, 10])
        entrada = T0 + timedelta(minutes=sorteio.choice([0, 1, 2]))
        sid = na_fila(sessao, mundo.fila, risco, nota, entrada)
        criadas.append(SolicitacaoDominio(sid, "NA_FILA", risco, nota, entrada))

    itens = painel(api, mundo.fila, limit=100)["itens"]

    assert [UUID(i["id"]) for i in itens] == [s.id for s in ordenar_fila(criadas)]
    assert [i["posicao"] for i in itens] == list(range(1, 41))


def test_rn007_ultima_mudanca_entrou_na_fila(api, sessao, mundo, atendente):
    sid = em_analise(sessao, mundo)
    classificar(api, sid, "VERDE")

    (item,) = painel(api, mundo.fila)["itens"]

    assert item["ultima_mudanca"]["tipo"] == "ENTROU_NA_FILA"


# --- dados do paciente na tela da equipe --------------------------------------------------


def test_lgpd_painel_com_nome_abreviado_e_cpf_mascarado(api, sessao, mundo, atendente):
    sid = em_analise(sessao, mundo)
    p = sessao.get(Paciente, sessao.get(Solicitacao, sid).paciente_id)

    (item,) = painel(api, mundo.fila)["itens"]
    detalhe = api.get(f"/api/v1/equipe/solicitacoes/{sid}").json()

    assert item["paciente_nome"] == "Maria S."
    assert item["paciente_cpf"] == f"***.{p.cpf[3:6]}.***-{p.cpf[9:]}"
    assert p.cpf not in str(item)
    assert detalhe["paciente_nome"] == p.nome  # completo só no detalhe
    assert detalhe["paciente_cpf"] == item["paciente_cpf"]


# --- AM-007: leituras auditadas -----------------------------------------------------------


def test_am007_leituras_da_equipe_sao_auditadas(api, sessao, mundo, atendente):
    sid = em_analise(sessao, mundo, [(mundo.p_filhos, True)])

    painel(api, mundo.fila, status="EM_ANALISE", ordenacao="chegada", limit=10)
    api.get(f"/api/v1/equipe/solicitacoes/{sid}")

    do_painel = sessao.scalar(
        select(Auditoria).where(
            Auditoria.acao == "CONSULTAR_PAINEL", Auditoria.ator_usuario_id == atendente.id
        )
    )
    assert (do_painel.entidade, do_painel.entidade_id) == ("fila", mundo.fila)
    assert do_painel.dados_depois == {
        "status": "EM_ANALISE",
        "ordenacao": "chegada",
        "limit": 10,
        "offset": 0,
    }
    do_detalhe = sessao.scalar(
        select(Auditoria).where(
            Auditoria.acao == "CONSULTAR_SOLICITACAO", Auditoria.ator_usuario_id == atendente.id
        )
    )
    assert (do_detalhe.entidade, str(do_detalhe.entidade_id)) == ("solicitacao", sid)
    assert do_detalhe.dados_depois is None  # sem nome, CPF nem respostas
    assert not chaves(do_painel.dados_depois) & {"nome", "cpf", "respostas"}


def test_am008_logs_da_equipe_sem_nome_nem_cpf(api, sessao, mundo, atendente, caplog):
    caplog.set_level(logging.DEBUG)
    sid = em_analise(sessao, mundo)
    p = sessao.get(Paciente, sessao.get(Solicitacao, sid).paciente_id)

    classificar(api, sid, "VERDE")
    responder(api, sid, [(mundo.r_gestacoes, 3)])
    painel(api, mundo.fila)
    api.get(f"/api/v1/equipe/solicitacoes/{sid}")

    assert sid in caplog.text
    for dado in (p.nome, p.cpf, "Maria"):
        assert dado not in caplog.text
