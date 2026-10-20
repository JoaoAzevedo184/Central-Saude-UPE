"""Área do paciente: filas e solicitações (UC-002, RN-009, RN-017, RN-018, ADR-007, AM-001)."""

import logging
from datetime import date, timedelta

import pytest
from sqlalchemy import func, select

from app.infra.modelos import (
    Auditoria,
    HistoricoSolicitacao,
    Outbox,
    RespostaCriterio,
    Solicitacao,
)
from tests.fila_sintetica import (
    chaves,
    criar_equipe,
    criar_paciente,
    csrf,
    entrar,
    montar_mundo,
)
from tests.test_auth import novo_cliente

pytestmark = pytest.mark.integracao

# ADR-007: o paciente nunca recebe nenhuma destas chaves.
CHAVES_PROIBIDAS = {
    "posicao",
    "tamanho_fila",
    "total",
    "nota",
    "pontos",
    "peso",
    "parametros",
    "fator",
    "classificacao_risco",
    "data_entrada_fila",
    "contagem_por_status",
    "ocorrido_em",  # a hora de ENTROU_NA_FILA revelaria data_entrada_fila
}


@pytest.fixture
def mundo(sessao):
    return montar_mundo(sessao)


@pytest.fixture
def paciente(api, sessao):
    usuario, p = criar_paciente(sessao)
    entrar(api, p.cpf)
    return p


def pedir(cliente, fila, respostas=(), **extra):
    corpo = {
        "fila_id": str(fila),
        "turno_preferido": "MANHA",
        "origem_encaminhamento": "USF Sintética",
        "respostas": [{"criterio_id": str(c), "valor": v} for c, v in respostas],
        **extra,
    }
    return cliente.post("/api/v1/solicitacoes", json=corpo, headers=csrf(cliente))


def cancelar(cliente, sid, motivo_codigo="NAO_PRECISO_MAIS"):
    return cliente.post(
        f"/api/v1/solicitacoes/{sid}/cancelar",
        json={"motivo_codigo": motivo_codigo},
        headers=csrf(cliente),
    )


def contar(sessao, modelo, *filtros):
    return sessao.scalar(select(func.count()).select_from(modelo).where(*filtros))


def classificar(sessao, mundo, solicitacao_id, risco="AMARELO", motivo=None):
    """Classifica pela equipe, num segundo cliente, e devolve a resposta."""
    atendente = criar_equipe(sessao, "ATENDENTE", filas=[mundo.fila])
    equipe = entrar(novo_cliente(), atendente.email)
    corpo = {"classificacao_risco": risco} | ({"motivo": motivo} if motivo else {})
    return equipe.post(
        f"/api/v1/equipe/solicitacoes/{solicitacao_id}/classificar",
        json=corpo,
        headers=csrf(equipe),
    )


# --- filas --------------------------------------------------------------------------------


def test_rf028_filas_com_elegibilidade_e_sem_contagem(api, sessao, mundo):
    _, homem = criar_paciente(sessao, nome="João Sintético", sexo="MASCULINO")
    entrar(api, homem.cpf)

    resposta = api.get("/api/v1/filas")

    assert resposta.status_code == 200
    filas = {f["id"]: f for f in resposta.json()}
    assert filas[str(mundo.fila)]["elegivel"] is True
    assert filas[str(mundo.fila)]["motivo_inelegivel"] is None
    assert filas[str(mundo.laqueadura)]["elegivel"] is False
    assert filas[str(mundo.laqueadura)]["motivo_inelegivel"]
    assert filas[str(mundo.fila)]["descricao_paciente"].startswith("Fila sintética")
    assert not chaves(resposta.json()) & CHAVES_PROIBIDAS


def test_rf028_detalhe_da_fila_traz_so_perguntas_do_paciente(api, paciente, mundo):
    resposta = api.get(f"/api/v1/filas/{mundo.fila}")

    assert resposta.status_code == 200
    criterios = {c["codigo"]: c for c in resposta.json()["criterios"]}
    assert set(criterios) == {"P_FILHOS", "P_OPCAO"}  # REGULACAO fica de fora
    assert criterios["P_OPCAO"]["opcoes"] == ["A", "B"]
    assert criterios["P_FILHOS"]["opcoes"] is None
    assert not chaves(resposta.json()) & CHAVES_PROIBIDAS


def test_rf028_fila_inexistente_retorna_404(api, paciente, mundo):
    assert api.get("/api/v1/filas/00000000-0000-0000-0000-000000000000").status_code == 404


# --- criar --------------------------------------------------------------------------------


def test_uc002_cria_solicitacao_em_analise_com_nota(api, sessao, paciente, mundo, relogio):
    resposta = pedir(api, mundo.fila, [(mundo.p_filhos, True), (mundo.p_opcao, "B")])

    assert resposta.status_code == 201, resposta.text
    corpo = resposta.json()
    assert corpo["status"] == "EM_ANALISE"
    assert [e["tipo"] for e in corpo["linha_do_tempo"]] == ["CRIADA"]
    assert {r["valor"] for r in corpo["respostas"]} == {True, "B"}
    s = sessao.get(Solicitacao, corpo["id"])
    assert s.nota == 10 + 2 * 3  # RN-006: soma dos pontos
    assert s.paciente_id == paciente.id
    assert s.origem_encaminhamento == "USF Sintética"
    assert s.data_pedido == date(2026, 10, 19)
    pontos = sessao.scalars(
        select(RespostaCriterio.pontos).where(RespostaCriterio.solicitacao_id == s.id)
    ).all()
    assert sorted(pontos) == [6, 10]
    assert contar(sessao, Outbox, Outbox.agregado_id == s.id) == 1
    assert sessao.scalar(select(Outbox.tipo_evento).where(Outbox.agregado_id == s.id)) == (
        "SOLICITACAO_CRIADA"
    )
    auditoria = sessao.scalar(select(Auditoria).where(Auditoria.entidade_id == s.id))
    assert auditoria.acao == "CRIAR_SOLICITACAO"
    assert auditoria.dados_depois["status"] == "EM_ANALISE"
    evento = sessao.scalar(
        select(HistoricoSolicitacao).where(HistoricoSolicitacao.solicitacao_id == s.id)
    )
    assert evento.tipo == "CRIADA" and evento.visivel_paciente
    assert evento.ocorrido_em == relogio.agora()


def test_rn009_sem_consentimento_retorna_403_e_nada_e_criado(api, sessao, mundo):
    _, p = criar_paciente(sessao, consentimento=False)
    entrar(api, p.cpf)

    resposta = pedir(api, mundo.fila)

    assert resposta.status_code == 403
    assert resposta.json()["type"] == "/problemas/sem-consentimento"
    assert contar(sessao, Solicitacao, Solicitacao.paciente_id == p.id) == 0


@pytest.mark.parametrize(
    ("fila", "sexo", "nascimento"),
    [
        ("laqueadura", "MASCULINO", date(1985, 3, 2)),  # sexo
        ("laqueadura", "FEMININO", date(2010, 1, 1)),  # menor de 18
        ("mamografia", "FEMININO", date(1995, 1, 1)),  # menos de 40
        ("laqueadura", None, date(1985, 3, 2)),  # sem sexo: falha fechada
    ],
)
def test_rn017_inelegivel_retorna_409_e_nada_e_criado(api, sessao, mundo, fila, sexo, nascimento):
    _, p = criar_paciente(sessao, sexo=sexo, nascimento=nascimento)
    entrar(api, p.cpf)

    resposta = pedir(api, getattr(mundo, fila))

    assert resposta.status_code == 409
    assert resposta.json()["type"] == "/problemas/nao-elegivel"
    assert resposta.json()["detail"]
    assert contar(sessao, Solicitacao, Solicitacao.paciente_id == p.id) == 0


@pytest.mark.parametrize(
    "respostas",
    [
        lambda m: [(m.criterio_outra_fila, True)],  # critério de outra fila
        lambda m: [(m.r_gestacoes, 3)],  # origem REGULACAO
        lambda m: [(m.p_filhos, True), (m.p_filhos, False)],  # repetido
        lambda m: [(m.p_filhos, "talvez")],  # tipo errado
        lambda m: [(m.p_opcao, "Z")],  # opção inexistente
    ],
)
def test_uc002_resposta_invalida_retorna_422_e_nada_e_criado(
    api, sessao, paciente, mundo, respostas
):
    resposta = pedir(api, mundo.fila, respostas(mundo))

    assert resposta.status_code == 422, resposta.text
    assert contar(sessao, Solicitacao, Solicitacao.paciente_id == paciente.id) == 0


@pytest.mark.parametrize(
    "campo",
    [
        {"status": "NA_FILA"},
        {"nota": 999},
        {"classificacao_risco": "VERMELHO"},
        {"pontos": 50},
        {"papel": "ADMIN"},
        {"paciente_id": "00000000-0000-0000-0000-000000000000"},
    ],
)
def test_am013_criar_recusa_campos_proibidos(api, sessao, paciente, mundo, campo):
    resposta = pedir(api, mundo.fila, **campo)

    assert resposta.status_code == 422
    assert contar(sessao, Solicitacao, Solicitacao.paciente_id == paciente.id) == 0


def test_rn018_solicitacao_duplicada_retorna_409_e_apos_cancelar_e_permitida(
    api, sessao, paciente, mundo
):
    primeira = pedir(api, mundo.fila).json()["id"]

    duplicada = pedir(api, mundo.fila)

    assert duplicada.status_code == 409
    assert duplicada.json()["type"] == "/problemas/solicitacao-duplicada"
    assert duplicada.json()["solicitacao_id"] == primeira  # UC-002 E2
    assert cancelar(api, primeira).status_code == 200
    assert pedir(api, mundo.fila).status_code == 201


# --- ler, listar, cancelar ----------------------------------------------------------------


def test_am001_paciente_b_nao_le_nem_cancela_solicitacao_de_a(api, sessao, paciente, mundo):
    id_a = pedir(api, mundo.fila).json()["id"]
    _, b = criar_paciente(sessao, nome="Beatriz Sintética")
    cliente_b = entrar(novo_cliente(), b.cpf)

    assert cliente_b.get(f"/api/v1/solicitacoes/{id_a}").status_code == 404
    assert cancelar(cliente_b, id_a).status_code == 404
    assert cliente_b.get("/api/v1/solicitacoes").json() == []
    assert sessao.get(Solicitacao, id_a).status == "EM_ANALISE"


def test_rf030_situacao_separa_abertas_e_encerradas(api, sessao, paciente, mundo):
    aberta = pedir(api, mundo.fila).json()["id"]
    encerrada = pedir(api, mundo.mamografia).json()["id"]
    cancelar(api, encerrada)

    def ids(situacao=None):
        params = {"situacao": situacao} if situacao else {}
        return {s["id"] for s in api.get("/api/v1/solicitacoes", params=params).json()}

    assert ids() == {aberta, encerrada}
    assert ids("abertas") == {aberta}
    assert ids("encerradas") == {encerrada}


def test_uc002_cancelar_grava_evento_auditoria_e_outbox(api, sessao, paciente, mundo, relogio):
    sid = pedir(api, mundo.fila).json()["id"]
    relogio.avancar(timedelta(seconds=1))  # a linha do tempo é ordenada por ocorrido_em

    resposta = cancelar(api, sid, "CONSEGUI_EM_OUTRO_LUGAR")

    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["status"] == "CANCELADA"
    evento = resposta.json()["linha_do_tempo"][-1]
    assert evento["tipo"] == "CANCELADA"
    assert evento["motivo"] == "Consegui atendimento em outro lugar."  # rótulo, não o código
    assert sessao.get(Solicitacao, sid).motivo_cancelamento == "CONSEGUI_EM_OUTRO_LUGAR"
    assert sessao.scalar(
        select(Outbox.id).where(
            Outbox.agregado_id == sid, Outbox.tipo_evento == "SOLICITACAO_CANCELADA"
        )
    )
    auditoria = sessao.scalar(
        select(Auditoria).where(
            Auditoria.entidade_id == sid, Auditoria.acao == "CANCELAR_SOLICITACAO"
        )
    )
    assert auditoria.dados_antes == {"status": "EM_ANALISE"}
    assert auditoria.dados_depois == {
        "status": "CANCELADA",
        "motivo_cancelamento": "CONSEGUI_EM_OUTRO_LUGAR",
    }
    assert auditoria.ator_usuario_id == paciente.usuario_id


@pytest.mark.parametrize("estado", ["ATENDIDA", "CANCELADA"])
def test_uc002_cancelar_solicitacao_encerrada_retorna_409(
    api, sessao, paciente, mundo, relogio, estado
):
    # EM_PROPOSTA e AGENDADA cancelam junto o agendamento: test_agendamentos.py.
    sid = pedir(api, mundo.fila).json()["id"]
    s = sessao.get(Solicitacao, sid)
    s.status, s.classificacao_risco, s.data_entrada_fila = estado, "VERDE", relogio.agora()
    sessao.flush()

    resposta = cancelar(api, sid)

    assert resposta.status_code == 409
    assert resposta.json()["type"] == "/problemas/transicao-invalida"
    assert contar(sessao, Outbox, Outbox.tipo_evento == "SOLICITACAO_CANCELADA") == 0


@pytest.mark.parametrize(
    "corpo",
    [
        None,  # motivo obrigatório
        {"motivo_codigo": "QUALQUER_COISA"},  # fora da lista
        {"motivo_codigo": "OUTRO", "motivo": "texto livre"},  # sem campo de texto
        {"motivo_codigo": "OUTRO", "status": "ATENDIDA"},
    ],
)
def test_am013_cancelar_so_aceita_motivo_codigo_da_lista(api, sessao, paciente, mundo, corpo):
    sid = pedir(api, mundo.fila).json()["id"]

    resposta = api.post(f"/api/v1/solicitacoes/{sid}/cancelar", json=corpo, headers=csrf(api))

    assert resposta.status_code == 422
    assert sessao.get(Solicitacao, sid).status == "EM_ANALISE"


@pytest.mark.parametrize(
    "codigo",
    [
        "NAO_PRECISO_MAIS",
        "CONSEGUI_EM_OUTRO_LUGAR",
        "DIFICULDADE_DE_DESLOCAMENTO",
        "CONFLITO_DE_HORARIO",
        "OUTRO",
    ],
)
def test_uc002_cada_motivo_de_cancelamento_tem_rotulo(api, sessao, paciente, mundo, codigo):
    sid = pedir(api, mundo.fila).json()["id"]

    evento = cancelar(api, sid, codigo).json()["linha_do_tempo"][-1]

    assert evento["motivo"] and evento["motivo"] != codigo


# --- ADR-007 ------------------------------------------------------------------------------


def test_adr007_respostas_do_paciente_sem_chaves_proibidas(api, sessao, paciente, mundo):
    sid = pedir(api, mundo.fila, [(mundo.p_filhos, True)]).json()["id"]
    assert classificar(sessao, mundo, sid).status_code == 200
    assert (
        classificar(sessao, mundo, sid, "VERMELHO", "Exame sintético alterado").status_code == 200
    )
    outra = pedir(api, mundo.mamografia)

    respostas = [
        api.get("/api/v1/filas"),
        api.get(f"/api/v1/filas/{mundo.fila}"),
        outra,
        api.get("/api/v1/solicitacoes"),
        api.get(f"/api/v1/solicitacoes/{sid}"),
        cancelar(api, sid),
    ]

    for resposta in respostas:
        assert resposta.status_code in (200, 201), resposta.text
        assert not chaves(resposta.json()) & CHAVES_PROIBIDAS, resposta.request.url
    detalhe = respostas[4].json()
    assert detalhe["respostas"] == [{"descricao": "Pergunta sintética P_FILHOS", "valor": True}]


def test_adr007_linha_do_tempo_sem_eventos_internos(api, sessao, paciente, mundo, relogio):
    sid = pedir(api, mundo.fila).json()["id"]
    relogio.avancar(timedelta(seconds=1))  # a linha do tempo é ordenada por ocorrido_em
    classificar(sessao, mundo, sid)
    classificar(sessao, mundo, sid, "VERMELHO", "Motivo interno sintético")

    resposta = api.get(f"/api/v1/solicitacoes/{sid}")

    linha = resposta.json()["linha_do_tempo"]
    assert [e["tipo"] for e in linha] == ["CRIADA", "ENTROU_NA_FILA"]
    assert linha[1]["motivo"] == "Seu pedido entrou na fila."
    assert "Motivo interno sintético" not in resposta.text
    assert resposta.json()["status"] == "NA_FILA"


def test_adr007_linha_do_tempo_so_com_a_data_no_fuso_de_recife(
    api, sessao, paciente, mundo, relogio
):
    # 01:30 UTC de 20/10 ainda é 19/10 em Recife (UTC-3).
    relogio.instante = relogio.agora().replace(day=20, hour=1, minute=30)
    entrar(api, paciente.cpf)  # o access token anterior venceu com o salto do relógio
    sid = pedir(api, mundo.fila).json()["id"]
    classificar(sessao, mundo, sid)

    linha = api.get(f"/api/v1/solicitacoes/{sid}").json()["linha_do_tempo"]

    assert [e["data"] for e in linha] == ["2026-10-19", "2026-10-19"]
    assert all(set(e) == {"tipo", "data", "motivo"} for e in linha)  # sem hora


# --- autenticação, papel e CSRF -----------------------------------------------------------

ROTAS_DO_PACIENTE = [
    ("get", "/api/v1/filas"),
    ("get", "/api/v1/filas/00000000-0000-0000-0000-000000000000"),
    ("get", "/api/v1/solicitacoes"),
    ("get", "/api/v1/solicitacoes/00000000-0000-0000-0000-000000000000"),
    ("post", "/api/v1/solicitacoes"),
    ("post", "/api/v1/solicitacoes/00000000-0000-0000-0000-000000000000/cancelar"),
]


@pytest.mark.parametrize(("metodo", "caminho"), ROTAS_DO_PACIENTE)
def test_am001_rotas_do_paciente_sem_sessao_retornam_401(api, metodo, caminho):
    api.cookies.set("csrf_token", "x")
    resposta = getattr(api, metodo)(caminho, headers={"X-CSRF-Token": "x"})

    assert resposta.status_code == 401


@pytest.mark.parametrize(("metodo", "caminho"), ROTAS_DO_PACIENTE)
def test_rbac_equipe_nas_rotas_do_paciente_retorna_403(api, sessao, mundo, metodo, caminho):
    atendente = criar_equipe(sessao, "ATENDENTE", filas=[mundo.fila])
    entrar(api, atendente.email)

    resposta = getattr(api, metodo)(caminho, headers=csrf(api))

    assert resposta.status_code == 403
    assert resposta.json()["type"] == "/problemas/sem-permissao"


@pytest.mark.parametrize(
    "caminho",
    [
        "/api/v1/solicitacoes",
        "/api/v1/solicitacoes/00000000-0000-0000-0000-000000000000/cancelar",
    ],
)
def test_am002_escrita_do_paciente_sem_csrf_retorna_403(api, paciente, caminho):
    resposta = api.post(caminho, json={})

    assert resposta.status_code == 403
    assert resposta.json()["type"] == "/problemas/csrf-invalido"


def test_am008_logs_do_paciente_sem_nome_nem_cpf(api, paciente, mundo, caplog):
    caplog.set_level(logging.DEBUG)

    sid = pedir(api, mundo.fila, [(mundo.p_filhos, True)]).json()["id"]
    api.get(f"/api/v1/solicitacoes/{sid}")
    cancelar(api, sid)

    assert sid in caplog.text  # os logs usam IDs
    for dado in (paciente.nome, paciente.cpf, paciente.nome.split()[0]):
        assert dado not in caplog.text
