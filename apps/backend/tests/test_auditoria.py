"""Consulta da auditoria (GET /admin/auditoria): acesso, filtros, paginação e privacidade.

RF-023, RN-010, RNF-004, ADR-008, AM-007.
"""

from datetime import UTC, datetime
from typing import get_args
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.rotas.auditoria import Acao, Entidade
from app.dominio.auditoria import ENTIDADES, PERMITIDAS
from app.infra.modelos import Agendamento, Auditoria
from app.worker import jobs
from tests.conftest import IP_DO_CLIENTE
from tests.fila_sintetica import criar_equipe, criar_paciente, csrf, entrar, montar_mundo
from tests.test_agendamentos import DIA_DISTANTE, as_9h, criar_agenda, criar_vaga
from tests.test_auth import com_csrf, criar_usuario, login, novo_cliente

pytestmark = pytest.mark.integracao

URL = "/api/v1/admin/auditoria"
SENTINELA = "SENTINELA"


@pytest.fixture
def admin(api, sessao):
    usuario = criar_usuario(sessao, "ADMIN", email="admin.auditoria@exemplo.com")
    assert login(api, "admin.auditoria@exemplo.com").status_code == 200
    return usuario


@pytest.fixture
def mundo(sessao):
    return montar_mundo(sessao)


def gravar(
    sessao,
    acao="CLASSIFICAR",
    entidade="fila",
    entidade_id=None,
    antes=None,
    depois=None,
    ator=None,
    em=None,
    id=None,
    ip=None,
) -> Auditoria:
    registro = Auditoria(
        id=id or uuid4(),
        ator_usuario_id=ator,
        acao=acao,
        entidade=entidade,
        entidade_id=entidade_id or uuid4(),
        dados_antes=antes,
        dados_depois=depois,
        ip=ip,
        **({"ocorrido_em": em} if em else {}),
    )
    sessao.add(registro)
    sessao.flush()
    return registro


def consultar(cliente, **params):
    return cliente.get(URL, params=params)


def so_de_leitura(sessao) -> int:
    return sessao.scalar(
        select(func.count()).select_from(Auditoria).where(Auditoria.acao != "CONSULTAR_AUDITORIA")
    )


# --- acesso -------------------------------------------------------------------------------


def test_rf023_sem_login_retorna_401():
    assert consultar(novo_cliente()).status_code == 401


@pytest.mark.parametrize("papel", ["ATENDENTE", "GESTOR"])
def test_rf023_equipe_que_nao_e_admin_retorna_403(api, sessao, papel):
    usuario = criar_equipe(sessao, papel)
    cliente = entrar(novo_cliente(), usuario.email)
    assert consultar(cliente).status_code == 403


def test_rf023_paciente_retorna_403(api, sessao):
    _, paciente = criar_paciente(sessao)
    cliente = entrar(novo_cliente(), paciente.cpf)
    assert consultar(cliente).status_code == 403


# --- listagem, paginação e ordem ------------------------------------------------------------


def test_rf023_lista_com_total_limit_offset_e_ordem(api, sessao, admin):
    alvo = uuid4()
    ids = sorted(uuid4() for _ in range(2))
    gravar(sessao, entidade_id=alvo, em=datetime(2026, 10, 1, 12, tzinfo=UTC))
    gravar(sessao, entidade_id=alvo, em=datetime(2026, 10, 3, 12, tzinfo=UTC))
    gravar(sessao, entidade_id=alvo, em=datetime(2026, 10, 2, 12, tzinfo=UTC), id=ids[0])
    gravar(sessao, entidade_id=alvo, em=datetime(2026, 10, 2, 12, tzinfo=UTC), id=ids[1])

    tudo = consultar(api, entidade="fila", entidade_id=str(alvo)).json()
    assert tudo["total"] == 4
    datas = [i["ocorrido_em"][:10] for i in tudo["itens"]]
    assert datas == ["2026-10-03", "2026-10-02", "2026-10-02", "2026-10-01"]
    # empate de horário: `id DESC`
    assert [i["id"] for i in tudo["itens"][1:3]] == [str(ids[1]), str(ids[0])]

    pagina = consultar(api, entidade="fila", entidade_id=str(alvo), limit=2, offset=2).json()
    assert pagina["total"] == 4
    assert [i["id"] for i in pagina["itens"]] == [i["id"] for i in tudo["itens"][2:]]


# --- filtros ------------------------------------------------------------------------------


def _paciente_com_solicitacao(sessao, mundo):
    _, p = criar_paciente(sessao)
    cliente = entrar(novo_cliente(), p.cpf)
    resposta = cliente.post(
        "/api/v1/solicitacoes",
        json={
            "fila_id": str(mundo.fila),
            "origem_encaminhamento": "USF Sintética",
            "respostas": [{"criterio_id": str(mundo.p_filhos), "valor": True}],
        },
        headers=csrf(cliente),
    )
    assert resposta.status_code == 201, resposta.text
    return cliente, resposta.json()["id"]


@pytest.fixture
def rodar(conexao, sessao, relogio):
    def _rodar(job):
        job(
            fabrica=lambda: Session(bind=conexao, join_transaction_mode="create_savepoint"),
            relogio=relogio,
        )
        sessao.expire_all()

    return _rodar


def test_rf023_trilha_da_solicitacao_inclui_os_agendamentos(api, sessao, admin, mundo, rodar):
    paciente, sid = _paciente_com_solicitacao(sessao, mundo)
    atendente = entrar(novo_cliente(), criar_equipe(sessao, "ATENDENTE", filas=[mundo.fila]).email)
    r = atendente.post(
        f"/api/v1/equipe/solicitacoes/{sid}/classificar",
        json={"classificacao_risco": "AMARELO"},
        headers=csrf(atendente),
    )
    assert r.status_code == 200, r.text
    criar_vaga(sessao, criar_agenda(sessao, mundo.fila), as_9h(DIA_DISTANTE))
    rodar(jobs.propor_vagas)
    proposta = sessao.scalar(select(Agendamento).where(Agendamento.solicitacao_id == UUID(sid)))
    confirmar = paciente.post(
        f"/api/v1/agendamentos/{proposta.id}/confirmar", headers=csrf(paciente)
    )
    assert confirmar.status_code == 200, confirmar.text

    corpo = consultar(api, entidade="solicitacao", entidade_id=sid).json()

    pares = sorted((i["entidade"], i["acao"]) for i in corpo["itens"])
    assert pares == sorted(
        [
            ("solicitacao", "CRIAR_SOLICITACAO"),
            ("solicitacao", "CLASSIFICAR"),
            ("solicitacao", "PROPOR_VAGA"),
            ("agendamento", "PROPOR_VAGA"),
            ("solicitacao", "CONFIRMAR_AGENDAMENTO"),
            ("agendamento", "CONFIRMAR_AGENDAMENTO"),
        ]
    )
    assert corpo["total"] == 6
    # `acao` vale sobre o conjunto expandido
    so_confirmar = consultar(
        api, entidade="solicitacao", entidade_id=sid, acao="CONFIRMAR_AGENDAMENTO"
    )
    assert so_confirmar.json()["total"] == 2
    # a trilha de um agendamento sozinho não expande
    ag = next(i["entidade_id"] for i in corpo["itens"] if i["entidade"] == "agendamento")
    assert consultar(api, entidade="agendamento", entidade_id=ag).json()["total"] == 2


def test_rf023_filtra_por_acao_e_por_ator(api, sessao, admin):
    alvo, outro = uuid4(), uuid4()
    equipe = criar_equipe(sessao, "ATENDENTE")
    gravar(sessao, "CLASSIFICAR", entidade_id=alvo, ator=equipe.id)
    gravar(sessao, "RECLASSIFICAR", entidade_id=alvo, ator=None)
    gravar(sessao, "CLASSIFICAR", entidade_id=outro, ator=None)

    por_acao = consultar(api, entidade="fila", entidade_id=str(alvo), acao="CLASSIFICAR").json()
    assert [i["acao"] for i in por_acao["itens"]] == ["CLASSIFICAR"]
    por_ator = consultar(api, ator_usuario_id=str(equipe.id)).json()
    assert [i["ator"]["id"] for i in por_ator["itens"]] == [str(equipe.id)]


def test_rf023_periodo_usa_o_dia_de_recife(api, sessao, admin):
    alvo = uuid4()
    # 23h30 de 14/10 em Recife (UTC-3) = 02h30 de 15/10 em UTC
    gravar(sessao, entidade_id=alvo, em=datetime(2026, 10, 15, 2, 30, tzinfo=UTC))
    base = {"entidade": "fila", "entidade_id": str(alvo)}

    assert consultar(api, **base, de="2026-10-14", ate="2026-10-14").json()["total"] == 1
    assert consultar(api, **base, de="2026-10-15", ate="2026-10-15").json()["total"] == 0
    assert consultar(api, **base, de="2026-10-15").json()["total"] == 0
    assert consultar(api, **base, ate="2026-10-14").json()["total"] == 1


@pytest.mark.parametrize(
    "params",
    [
        {"entidade_id": str(uuid4())},
        {"de": "2026-10-10", "ate": "2026-10-09"},
        {"acao": "ACAO_INEXISTENTE"},
        {"entidade": "inexistente"},
        {"de": "9999-12-31"},
        {"ate": "9999-12-31"},
        {"de": "0001-01-01"},
        {"ate": "0001-01-01"},
        {"de": "1999-12-31"},
        {"ate": "2101-01-01"},
    ],
)
def test_rf023_filtro_invalido_retorna_422(api, admin, params):
    assert consultar(api, **params).status_code == 422


# --- privacidade ----------------------------------------------------------------------------


def test_rf023_sentinela_nenhuma_marca_sai_na_resposta(api, sessao, admin, mundo):
    marca = f"{SENTINELA}-7f3a"
    _, p = criar_paciente(sessao, nome=f"{marca}-NOME")
    paciente = entrar(novo_cliente(), p.cpf)
    sid = paciente.post(
        "/api/v1/solicitacoes",
        json={
            "fila_id": str(mundo.fila),
            "origem_encaminhamento": f"{marca}-ORIGEM",
            "respostas": [{"criterio_id": str(mundo.p_filhos), "valor": True}],
        },
        headers=csrf(paciente),
    ).json()["id"]
    atendente = entrar(novo_cliente(), criar_equipe(sessao, "ATENDENTE", filas=[mundo.fila]).email)
    alvo = criar_usuario(sessao, "ATENDENTE")
    for rota, corpo in (
        ("classificar", {"classificacao_risco": "VERDE"}),
        ("classificar", {"classificacao_risco": "VERMELHO", "motivo": f"{marca}-MOTIVO"}),
    ):
        r = atendente.post(
            f"/api/v1/equipe/solicitacoes/{sid}/{rota}", json=corpo, headers=csrf(atendente)
        )
        assert r.status_code == 200, r.text
    r = atendente.put(
        f"/api/v1/equipe/solicitacoes/{sid}/respostas",
        json={"respostas": [{"criterio_id": str(mundo.r_gestacoes), "valor": 3}]},
        headers=csrf(atendente),
    )
    assert r.status_code == 200, r.text
    r = api.post(
        f"/api/v1/admin/usuarios/{alvo.id}/suspender",
        json={"motivo": f"{marca}-SUSPENSAO"},
        headers=com_csrf(api),
    )
    assert r.status_code == 204, r.text
    paciente_email = criar_usuario(sessao, "PACIENTE", email=f"{marca}-EMAIL@exemplo.com")
    gravar(sessao, "LOGIN", "usuario", paciente_email.id, ator=paciente_email.id, ip=IP_DO_CLIENTE)

    resposta = consultar(api, limit=100)

    texto = resposta.text
    assert resposta.json()["total"] >= 6
    assert marca.lower() not in texto.lower()
    assert str(mundo.r_gestacoes) not in texto  # chaves de `respostas` não saem
    assert IP_DO_CLIENTE not in texto
    assert '"ip"' not in texto
    responder = [i for i in resposta.json()["itens"] if i["acao"] == "RESPONDER_CRITERIOS"]
    assert responder
    oculto = next(c for c in responder[0]["campos"] if c["campo"] == "respostas")
    assert oculto == {"campo": "respostas", "antes": None, "depois": None, "oculto": True}
    assert responder[0]["detalhes_omitidos"] is False


def test_rf023_ator_paciente_sem_id_e_sem_email_e_sistema_quando_nulo(api, sessao, admin):
    alvo = uuid4()
    usuario, _ = criar_paciente(sessao, login=False)
    equipe = criar_equipe(sessao, "GESTOR")
    gravar(sessao, "LOGIN", "fila", alvo, ator=usuario.id)
    gravar(sessao, "LOGIN", "fila", alvo, ator=None)
    gravar(sessao, "LOGIN", "fila", alvo, ator=equipe.id)

    itens = consultar(api, entidade="fila", entidade_id=str(alvo)).json()["itens"]

    por_tipo = {i["ator"]["tipo"]: i["ator"] for i in itens}
    assert por_tipo["PACIENTE"] == {
        "tipo": "PACIENTE",
        "id": None,
        "papel": "PACIENTE",
        "email": None,
    }
    assert por_tipo["SISTEMA"] == {"tipo": "SISTEMA", "id": None, "papel": None, "email": None}
    assert por_tipo["EQUIPE"] == {
        "tipo": "EQUIPE",
        "id": str(equipe.id),
        "papel": "GESTOR",
        "email": equipe.email,
    }


def test_rf023_acao_fora_da_lista_permitida_nao_expoe_nada(api, sessao, admin):
    alvo = uuid4()
    gravar(sessao, "ACAO_NOVA", "fila", alvo, depois={"nome": f"{SENTINELA}-X"})
    gravar(sessao, "CLASSIFICAR", "fila", alvo, depois={"status": "NA_FILA", "cpf": "00000000000"})
    gravar(sessao, "CLASSIFICAR", "fila", alvo, depois={"status": f"{SENTINELA}-livre"})

    corpo = consultar(api, entidade="fila", entidade_id=str(alvo))

    assert SENTINELA not in corpo.text and "00000000000" not in corpo.text
    por_acao = {}
    for i in corpo.json()["itens"]:
        por_acao.setdefault(i["acao"], []).append(i)
    assert por_acao["ACAO_NOVA"][0]["campos"] == []
    assert all(i["detalhes_omitidos"] for itens in por_acao.values() for i in itens)
    assert sorted(len(i["campos"]) for i in por_acao["CLASSIFICAR"]) == [0, 1]


def test_rf023_a_leitura_so_grava_a_propria_auditoria(api, sessao, admin):
    alvo = uuid4()
    gravar(sessao, entidade_id=alvo, depois={"status": "NA_FILA"})
    antes = so_de_leitura(sessao)

    primeira = consultar(api, entidade="fila", entidade_id=str(alvo), acao="CLASSIFICAR")

    assert primeira.status_code == 200
    assert so_de_leitura(sessao) == antes
    gravadas = sessao.scalars(
        select(Auditoria).where(Auditoria.acao == "CONSULTAR_AUDITORIA")
    ).all()
    assert len(gravadas) == 1
    leitura = gravadas[0]
    assert (leitura.ator_usuario_id, leitura.entidade, leitura.entidade_id) == (
        admin.id,
        "usuario",
        admin.id,
    )
    assert leitura.dados_depois == {
        "entidade": "fila",
        "entidade_id": str(alvo),
        "acao": "CLASSIFICAR",
        "ator_usuario_id": None,
        "de": None,
        "ate": None,
    }
    # a leitura não aparece na própria resposta, e sim na seguinte
    assert all(i["acao"] != "CONSULTAR_AUDITORIA" for i in primeira.json()["itens"])
    seguinte = consultar(api, acao="CONSULTAR_AUDITORIA").json()
    assert seguinte["total"] == 1
    assert seguinte["itens"][0]["detalhes_omitidos"] is False
    assert {c["campo"] for c in seguinte["itens"][0]["campos"]} == {
        "entidade",
        "entidade_id",
        "acao",
        "ator_usuario_id",
        "de",
        "ate",
    }


def test_rf023_literais_da_rota_batem_com_a_lista_permitida():
    assert set(get_args(Acao)) == set(PERMITIDAS)
    assert set(get_args(Entidade)) == set(ENTIDADES)
    assert len(get_args(Acao)) == len(PERMITIDAS)


def test_rf023_resposta_nao_tem_o_ip_no_contrato(api):
    from app.api.main import app

    schemas = app.openapi()["components"]["schemas"]
    for nome in ("ItemAuditoria", "AtorAuditoria", "CampoAuditoria"):
        assert "ip" not in schemas[nome]["properties"]
    assert UUID  # import usado só para tipagem dos ids acima
