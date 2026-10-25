"""Administração da equipe (RF-035, ADR-025, ADR-028), senha temporária e troca de senha.

Matriz de acesso, senha temporária (exposição única, bloqueio até a troca, revogação de
sessões), atribuições respeitando o papel e a confirmação da visão central. AM-020.
"""

import json
import logging
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.config import get_settings
from app.infra.autenticacao import conferir_senha
from app.infra.modelos import (
    Auditoria,
    SessaoRefresh,
    TentativaLogin,
    Usuario,
    usuario_fila,
    usuario_unidade,
)
from tests.fila_sintetica import montar_mundo
from tests.test_auth import (
    CPF_PACIENTE,
    SENHA,
    com_csrf,
    contar,
    criar_paciente,
    criar_usuario,
    login,
    novo_cliente,
)

pytestmark = pytest.mark.integracao

ADMIN = "/api/v1/admin"
TROCA_OBRIGATORIA = "/problemas/troca-de-senha-obrigatoria"


@pytest.fixture
def admin(api, sessao):
    usuario = criar_usuario(sessao, "ADMIN", email="admin.adm@exemplo.com")
    assert login(api, "admin.adm@exemplo.com").status_code == 200
    return usuario


@pytest.fixture
def mundo(sessao):
    return montar_mundo(sessao)


def criar(api, **corpo):
    corpo.setdefault("email", f"{uuid4().hex[:8]}@exemplo.com")
    corpo.setdefault("papel", "ATENDENTE")
    return api.post(f"{ADMIN}/usuarios", json=corpo, headers=com_csrf(api))


def put(api, caminho, **corpo):
    return api.put(f"{ADMIN}/usuarios/{caminho}", json=corpo, headers=com_csrf(api))


def auditorias(sessao, acao):
    return sessao.scalars(select(Auditoria).where(Auditoria.acao == acao)).all()


# --- matriz de acesso ---------------------------------------------------------------------

ROTAS = [
    ("GET", f"{ADMIN}/usuarios", None),
    ("POST", f"{ADMIN}/usuarios", {"email": "x@exemplo.com", "papel": "ATENDENTE"}),
    ("POST", f"{ADMIN}/usuarios/{uuid4()}/redefinir-senha", None),
    ("PUT", f"{ADMIN}/usuarios/{uuid4()}/filas", {"fila_ids": []}),
    (
        "PUT",
        f"{ADMIN}/usuarios/{uuid4()}/unidades",
        {"unidade_ids": [], "confirmar_visao_central": True},
    ),
    ("POST", f"{ADMIN}/usuarios/{uuid4()}/suspender", {"motivo": "teste"}),
    ("POST", f"{ADMIN}/usuarios/{uuid4()}/reativar", None),
    ("GET", f"{ADMIN}/filas", None),
]


@pytest.mark.parametrize("papel", ["PACIENTE", "ATENDENTE", "GESTOR"])
@pytest.mark.parametrize(("metodo", "caminho", "corpo"), ROTAS)
def test_rf035_so_admin_acessa_a_administracao(api, sessao, papel, metodo, caminho, corpo):
    if papel == "PACIENTE":
        criar_paciente(sessao)
        login(api, CPF_PACIENTE)
    else:
        criar_usuario(sessao, papel, email="nao.admin.adm@exemplo.com")
        login(api, "nao.admin.adm@exemplo.com")

    resposta = api.request(metodo, caminho, json=corpo, headers=com_csrf(api))

    assert resposta.status_code == 403
    assert resposta.json()["type"] == "/problemas/sem-permissao"


@pytest.mark.parametrize(("metodo", "caminho", "corpo"), ROTAS)
def test_rf035_sem_sessao_retorna_401(client, metodo, caminho, corpo):
    resposta = client.request(metodo, caminho, json=corpo, headers={"X-CSRF-Token": "a"})
    # Sem cookie CSRF a escrita nem chega à rota; a leitura prova o 401.
    assert resposta.status_code in (401, 403)
    if metodo == "GET":
        assert resposta.status_code == 401


@pytest.mark.parametrize(
    ("metodo", "caminho"),
    [
        ("POST", f"/api/v1/usuarios/{uuid4()}/suspender"),
        ("POST", f"/api/v1/usuarios/{uuid4()}/reativar"),
    ],
)
def test_rf035_rotas_antigas_de_suspensao_respondem_404(api, admin, metodo, caminho):
    resposta = api.request(metodo, caminho, json={"motivo": "teste"}, headers=com_csrf(api))

    assert resposta.status_code == 404


# --- criar conta e senha temporária -------------------------------------------------------


def test_rf036_cria_conta_com_senha_temporaria_devolvida_uma_vez(api, sessao, admin, caplog):
    caplog.set_level(logging.DEBUG)

    resposta = criar(api, email="Nova.Atendente@Exemplo.com", papel="ATENDENTE")

    assert resposta.status_code == 201
    corpo = resposta.json()
    senha = corpo["senha_temporaria"]
    assert len(senha) >= 16
    usuario = sessao.get(Usuario, corpo["id"])
    assert usuario.email == "nova.atendente@exemplo.com"
    assert usuario.papel == "ATENDENTE"
    assert usuario.senha_temporaria is True
    assert conferir_senha(usuario.senha_hash, senha)
    # A senha (e o hash) nunca aparecem em log nem na auditoria.
    assert senha not in caplog.text
    linhas = sessao.scalars(select(Auditoria)).all()
    dump = json.dumps([[a.dados_antes, a.dados_depois, a.acao] for a in linhas], default=str)
    assert senha not in dump
    assert usuario.senha_hash not in dump
    assert api.get(f"{ADMIN}/usuarios").text.count(senha) == 0  # não reaparece em lugar nenhum
    assert auditorias(sessao, "CRIAR_USUARIO")[0].ator_usuario_id == admin.id


def test_rf036_resposta_da_senha_nao_fica_em_cache(api, admin):
    resposta = criar(api)

    assert resposta.headers["cache-control"] == "no-store"


def test_rf036_login_de_senha_temporaria_traz_trocar_senha(api, sessao, admin):
    senha = criar(api, email="temp.login@exemplo.com").json()["senha_temporaria"]

    resposta = login(novo_cliente(), "temp.login@exemplo.com", senha)

    assert resposta.status_code == 200
    assert resposta.json()["trocar_senha"] is True


def test_rf036_login_comum_nao_traz_trocar_senha(api, sessao):
    criar_usuario(sessao, "GESTOR", email="gestor.sem.troca@exemplo.com")

    resposta = login(api, "gestor.sem.troca@exemplo.com")

    assert "trocar_senha" not in resposta.json()


def test_rf036_email_duplicado_retorna_409(api, admin):
    assert criar(api, email="dup@exemplo.com").status_code == 201

    resposta = criar(api, email="DUP@exemplo.com")

    assert resposta.status_code == 409
    assert resposta.json()["type"] == "/problemas/email-ja-cadastrado"


@pytest.mark.parametrize(
    "corpo",
    [
        {"papel": "PACIENTE"},
        {"email": "sem-arroba"},
        {"papel": "SUPER"},
        {"status": "ATIVO"},  # campo fora do schema
        {"papel": "ATENDENTE", "unidade_ids": []},  # unidade só para GESTOR
        {"papel": "ADMIN", "unidade_ids": [str(uuid4())]},
    ],
)
def test_rf036_criacao_invalida_retorna_422(api, admin, corpo):
    assert criar(api, **corpo).status_code == 422


def test_rf036_gestor_sem_unidade_exige_confirmar_a_visao_central(api, sessao, admin, mundo):
    sem_nada = criar(api, papel="GESTOR")
    confirmado = criar(api, papel="GESTOR", confirmar_visao_central=True)
    com_unidade = criar(api, papel="GESTOR", unidade_ids=[str(mundo.unidade)])

    assert sem_nada.status_code == 409
    assert sem_nada.json()["type"] == "/problemas/visao-central-nao-confirmada"
    assert confirmado.status_code == 201
    assert com_unidade.status_code == 201
    unidades = sessao.scalars(
        select(usuario_unidade.c.unidade_id).where(
            usuario_unidade.c.usuario_id == com_unidade.json()["id"]
        )
    ).all()
    assert unidades == [mundo.unidade]
    assert contar(sessao, Usuario, Usuario.papel == "GESTOR") == 2  # a 409 não criou nada


def test_rf036_gestor_com_unidade_inexistente_retorna_422(api, admin):
    assert criar(api, papel="GESTOR", unidade_ids=[str(uuid4())]).status_code == 422


# --- troca obrigatória --------------------------------------------------------------------


@pytest.fixture
def temporario(api, sessao, admin):
    """Cliente logado como ADMIN com senha temporária (criado por outro admin)."""
    senha = criar(api, email="admin.temp@exemplo.com", papel="ADMIN")
    senha = senha.json()["senha_temporaria"]
    cliente = novo_cliente()
    assert login(cliente, "admin.temp@exemplo.com", senha).status_code == 200
    return cliente, senha


def test_rf036_senha_temporaria_bloqueia_as_outras_rotas(temporario):
    cliente, _ = temporario
    chamadas = [
        cliente.get(f"{ADMIN}/usuarios"),
        cliente.get(f"{ADMIN}/filas"),
        cliente.post(f"{ADMIN}/usuarios/{uuid4()}/reativar", headers=com_csrf(cliente)),
        cliente.put(
            f"{ADMIN}/usuarios/{uuid4()}/filas", json={"fila_ids": []}, headers=com_csrf(cliente)
        ),
    ]

    for resposta in chamadas:
        assert resposta.status_code == 403
        assert resposta.json()["type"] == TROCA_OBRIGATORIA


def test_rf036_senha_temporaria_ainda_acessa_me_refresh_e_logout(temporario):
    cliente, _ = temporario

    assert cliente.get("/api/v1/me").status_code == 200
    assert cliente.post("/api/v1/auth/refresh", headers=com_csrf(cliente)).status_code == 200
    assert cliente.post("/api/v1/auth/logout", headers=com_csrf(cliente)).status_code == 204


def test_rf036_troca_de_senha_libera_o_acesso_e_revoga_as_outras_sessoes(
    temporario, sessao, caplog
):
    cliente, temp = temporario
    outro = novo_cliente()
    assert login(outro, "admin.temp@exemplo.com", temp).status_code == 200
    caplog.set_level(logging.DEBUG)

    resposta = cliente.post(
        "/api/v1/auth/trocar-senha",
        json={"senha_atual": temp, "senha_nova": "uma-senha-nova-forte"},
        headers=com_csrf(cliente),
    )

    assert resposta.status_code == 204
    assert cliente.get(f"{ADMIN}/usuarios").status_code == 200  # a sessão atual segue
    assert outro.get("/api/v1/me").status_code == 401  # as outras caem
    assert "uma-senha-nova-forte" not in caplog.text
    usuario = sessao.scalar(select(Usuario).where(Usuario.email == "admin.temp@exemplo.com"))
    assert usuario.senha_temporaria is False
    assert (
        login(novo_cliente(), "admin.temp@exemplo.com", "uma-senha-nova-forte").status_code == 200
    )
    auditoria = auditorias(sessao, "TROCAR_SENHA")[0]
    assert auditoria.dados_antes is None and auditoria.dados_depois is None


@pytest.mark.parametrize(
    "corpo",
    [
        {"senha_atual": "errada", "senha_nova": "uma-senha-nova-forte"},
        {"senha_atual": SENHA, "senha_nova": "curta"},
        {"senha_atual": SENHA, "senha_nova": SENHA},
        {"senha_atual": SENHA, "senha_nova": "uma-senha-nova-forte", "papel": "ADMIN"},
    ],
)
def test_rf036_troca_invalida_retorna_422_e_nao_muda_nada(api, sessao, admin, corpo):
    resposta = api.post("/api/v1/auth/trocar-senha", json=corpo, headers=com_csrf(api))

    assert resposta.status_code == 422
    assert login(novo_cliente(), "admin.adm@exemplo.com").status_code == 200


def test_rf036_trocar_senha_exige_sessao_e_csrf(api, admin):
    corpo = {"senha_atual": SENHA, "senha_nova": "uma-senha-nova-forte"}

    sem_csrf = api.post("/api/v1/auth/trocar-senha", json=corpo)

    assert sem_csrf.status_code == 403
    assert sem_csrf.json()["type"] == "/problemas/csrf-invalido"
    sem_sessao = novo_cliente().post(
        "/api/v1/auth/trocar-senha", json=corpo, headers={"X-CSRF-Token": "a"}
    )
    assert sem_sessao.status_code in (401, 403)


def test_am020_erros_na_troca_de_senha_bloqueiam_sem_revogar_nada(
    api, sessao, relogio, admin, monkeypatch
):
    settings = get_settings()
    monkeypatch.setattr(settings, "access_token_ttl_minutos", 120)  # sobrevive à janela
    api.cookies.clear()
    assert login(api, "admin.adm@exemplo.com").status_code == 200
    errada = {"senha_atual": "errada", "senha_nova": "uma-senha-nova-forte"}
    for _ in range(settings.login_max_tentativas):
        r = api.post("/api/v1/auth/trocar-senha", json=errada, headers=com_csrf(api))
        assert r.status_code == 422

    certa = {"senha_atual": SENHA, "senha_nova": "uma-senha-nova-forte"}
    bloqueada = api.post("/api/v1/auth/trocar-senha", json=certa, headers=com_csrf(api))

    assert bloqueada.status_code == 429
    assert bloqueada.json()["type"] == "/problemas/muitas-tentativas"
    assert contar(sessao, SessaoRefresh, SessaoRefresh.revogado_em.is_(None)) >= 1
    usuario = sessao.get(Usuario, admin.id)
    assert conferir_senha(usuario.senha_hash, SENHA)  # nada mudou
    hashes = sessao.scalars(
        select(TentativaLogin.identificador_hash).where(TentativaLogin.tipo == "TROCA_SENHA")
    ).all()
    assert str(admin.id) not in hashes and len(set(hashes)) == 1  # só o HMAC do usuário

    relogio.avancar(timedelta(minutes=settings.login_janela_min, seconds=1))
    depois = api.post("/api/v1/auth/trocar-senha", json=certa, headers=com_csrf(api))
    assert depois.status_code == 204


# --- redefinir senha ----------------------------------------------------------------------


def test_rf036_redefinir_senha_revoga_sessoes_e_exige_nova_troca(api, sessao, admin, caplog):
    alvo = criar_usuario(sessao, "ATENDENTE", email="redef@exemplo.com")
    navegador = novo_cliente()
    assert login(navegador, "redef@exemplo.com").status_code == 200
    caplog.set_level(logging.DEBUG)

    resposta = api.post(f"{ADMIN}/usuarios/{alvo.id}/redefinir-senha", headers=com_csrf(api))

    assert resposta.status_code == 200
    senha = resposta.json()["senha_temporaria"]
    assert navegador.get("/api/v1/me").status_code == 401
    assert login(novo_cliente(), "redef@exemplo.com", SENHA).status_code == 401
    entrou = login(novo_cliente(), "redef@exemplo.com", senha)
    assert entrou.status_code == 200 and entrou.json()["trocar_senha"] is True
    assert senha not in caplog.text
    sessao.refresh(alvo)
    dump = json.dumps(
        [[a.dados_antes, a.dados_depois] for a in auditorias(sessao, "REDEFINIR_SENHA")]
    )
    assert senha not in dump and alvo.senha_hash not in dump


def test_rf036_redefinir_senha_so_de_atendente_e_gestor(api, sessao, admin):
    paciente = criar_paciente(sessao)
    outro_admin = criar_usuario(sessao, "ADMIN")
    gestor = criar_usuario(sessao, "GESTOR")

    for alvo in (paciente, outro_admin, admin):  # inclui a própria conta
        resposta = api.post(f"{ADMIN}/usuarios/{alvo.id}/redefinir-senha", headers=com_csrf(api))
        assert resposta.status_code == 409
        assert resposta.json()["type"] == "/problemas/operacao-nao-permitida"
    assert (
        api.post(f"{ADMIN}/usuarios/{gestor.id}/redefinir-senha", headers=com_csrf(api)).status_code
        == 200
    )
    inexistente = api.post(f"{ADMIN}/usuarios/{uuid4()}/redefinir-senha", headers=com_csrf(api))
    assert inexistente.status_code == 404
    sessao.refresh(outro_admin)
    assert outro_admin.senha_temporaria is False


def test_rf036_me_traz_trocar_senha_so_com_senha_temporaria(api, sessao, temporario):
    cliente, _ = temporario
    comum = criar_usuario(sessao, "GESTOR", email="me.comum@exemplo.com")
    login(novo := novo_cliente(), "me.comum@exemplo.com")

    com_flag = cliente.get("/api/v1/me").json()
    sem_flag = novo.get("/api/v1/me").json()

    assert com_flag["trocar_senha"] is True
    assert set(com_flag) == {"id", "papel", "nome", "filas", "trocar_senha"}
    assert set(sem_flag) == {"id", "papel", "nome", "filas"}  # resposta intacta
    assert sem_flag["id"] == str(comum.id)


# --- atribuições --------------------------------------------------------------------------


def test_rf035_atribui_filas_so_ao_atendente_e_substitui(api, sessao, admin, mundo):
    atendente = criar_usuario(sessao, "ATENDENTE")
    gestor = criar_usuario(sessao, "GESTOR")
    ator = criar_usuario(sessao, "ADMIN")

    primeira = put(api, f"{atendente.id}/filas", fila_ids=[str(mundo.fila), str(mundo.laqueadura)])
    segunda = put(api, f"{atendente.id}/filas", fila_ids=[str(mundo.fila)])

    assert primeira.status_code == segunda.status_code == 204
    filas = sessao.scalars(
        select(usuario_fila.c.fila_id).where(usuario_fila.c.usuario_id == atendente.id)
    ).all()
    assert filas == [mundo.fila]
    for outro in (gestor, ator):
        resposta = put(api, f"{outro.id}/filas", fila_ids=[str(mundo.fila)])
        assert resposta.status_code == 409
        assert resposta.json()["type"] == "/problemas/operacao-nao-permitida"
    depois = auditorias(sessao, "ATRIBUIR_FILAS")
    assert len(depois) == 2 and depois[-1].ator_usuario_id == admin.id
    assert put(api, f"{atendente.id}/filas", fila_ids=[str(uuid4())]).status_code == 422
    assert put(api, f"{uuid4()}/filas", fila_ids=[]).status_code == 404
    esvaziada = put(api, f"{atendente.id}/filas", fila_ids=[])
    assert esvaziada.status_code == 204  # atendente sem fila não vê nenhuma: falha fechada


def test_rf035_atribui_unidades_so_ao_gestor(api, sessao, admin, mundo):
    gestor = criar_usuario(sessao, "GESTOR")
    atendente = criar_usuario(sessao, "ATENDENTE")

    ok = put(api, f"{gestor.id}/unidades", unidade_ids=[str(mundo.unidade)])
    outro_papel = put(api, f"{atendente.id}/unidades", unidade_ids=[str(mundo.unidade)])

    assert ok.status_code == 204
    assert outro_papel.status_code == 409
    assert put(api, f"{gestor.id}/unidades", unidade_ids=[str(uuid4())]).status_code == 422


def test_adr025_visao_central_exige_confirmacao_explicita(api, sessao, admin, mundo):
    gestor = criar_usuario(sessao, "GESTOR")
    assert put(api, f"{gestor.id}/unidades", unidade_ids=[str(mundo.unidade)]).status_code == 204

    sem = put(api, f"{gestor.id}/unidades", unidade_ids=[])
    falsa = put(api, f"{gestor.id}/unidades", unidade_ids=[], confirmar_visao_central=False)

    for resposta in (sem, falsa):
        assert resposta.status_code == 409
        assert resposta.json()["type"] == "/problemas/visao-central-nao-confirmada"
    assert sessao.scalars(
        select(usuario_unidade.c.unidade_id).where(usuario_unidade.c.usuario_id == gestor.id)
    ).all() == [mundo.unidade]  # nada mudou

    com = put(api, f"{gestor.id}/unidades", unidade_ids=[], confirmar_visao_central=True)

    assert com.status_code == 204
    assert not sessao.scalars(
        select(usuario_unidade.c.unidade_id).where(usuario_unidade.c.usuario_id == gestor.id)
    ).all()
    assert auditorias(sessao, "ATRIBUIR_UNIDADES")[-1].dados_depois["visao_central"] is True


def test_rf035_papel_no_corpo_da_atribuicao_retorna_422(api, sessao, admin, mundo):
    atendente = criar_usuario(sessao, "ATENDENTE")

    assert put(api, f"{atendente.id}/filas", fila_ids=[], papel="ADMIN").status_code == 422


# --- listagens ----------------------------------------------------------------------------


def test_rf035_lista_so_a_equipe_com_filtros_e_atribuicoes(api, sessao, relogio, admin, mundo):
    criar_paciente(sessao)
    atendente = criar_usuario(sessao, "ATENDENTE", email="lista.atendente@exemplo.com")
    gestor = criar_usuario(sessao, "GESTOR", email="lista.gestor@exemplo.com")
    suspenso = criar_usuario(
        sessao,
        "ATENDENTE",
        email="lista.suspenso@exemplo.com",
        situacao="SUSPENSO",
        relogio=relogio,
    )
    put(api, f"{atendente.id}/filas", fila_ids=[str(mundo.fila)])
    put(api, f"{gestor.id}/unidades", unidade_ids=[str(mundo.unidade)])

    todos = api.get(f"{ADMIN}/usuarios").json()
    atendentes = api.get(f"{ADMIN}/usuarios?papel=ATENDENTE&situacao=ATIVO").json()
    suspensos = api.get(f"{ADMIN}/usuarios?situacao=SUSPENSO").json()
    pagina = api.get(f"{ADMIN}/usuarios?limit=1&offset=1").json()

    assert todos["total"] == 4  # admin, atendente, gestor, suspenso; sem o paciente
    assert {i["papel"] for i in todos["itens"]} == {"ADMIN", "ATENDENTE", "GESTOR"}
    por_id = {i["id"]: i for i in todos["itens"]}
    assert por_id[str(atendente.id)]["filas"] == [str(mundo.fila)]
    assert por_id[str(gestor.id)]["unidades"] == [str(mundo.unidade)]
    assert por_id[str(gestor.id)]["filas"] == []
    assert [i["id"] for i in atendentes["itens"]] == [str(atendente.id)]
    assert [i["id"] for i in suspensos["itens"]] == [str(suspenso.id)]
    assert pagina["total"] == 4 and len(pagina["itens"]) == 1
    assert "senha_hash" not in api.get(f"{ADMIN}/usuarios").text
    assert api.get(f"{ADMIN}/usuarios?papel=PACIENTE").status_code == 422
    assert api.get(f"{ADMIN}/usuarios?limit=0").status_code == 422


def test_rf035_lista_filas_com_unidade_e_especialidade(api, admin, mundo):
    corpo = api.get(f"{ADMIN}/filas").json()

    assert corpo["total"] == 4
    geral = next(i for i in corpo["itens"] if i["nome"] == "Geral")
    assert geral["unidade"] == {"id": str(mundo.unidade), "sigla": "TST1"}
    assert geral["especialidade"]["nome"] == "Especialidade Sintética"
    assert geral["ativa"] is True


# --- suspensão segue valendo sob /admin ---------------------------------------------------


def test_adr028_suspender_sob_admin_revoga_sessoes(api, sessao, admin):
    alvo = criar_usuario(sessao, "ATENDENTE", email="susp.admin@exemplo.com")
    navegador = novo_cliente()
    login(navegador, "susp.admin@exemplo.com")

    resposta = api.post(
        f"{ADMIN}/usuarios/{alvo.id}/suspender", json={"motivo": "Férias"}, headers=com_csrf(api)
    )

    assert resposta.status_code == 204
    assert navegador.get("/api/v1/me").status_code == 401


# --- achados da revisão -------------------------------------------------------------------


def test_am020_troca_de_senha_bloqueada_nao_bloqueia_o_login(
    api, sessao, relogio, admin, monkeypatch
):
    settings = get_settings()
    errada = {"senha_atual": "errada", "senha_nova": "uma-senha-nova-forte"}
    for _ in range(settings.login_max_tentativas):
        api.post("/api/v1/auth/trocar-senha", json=errada, headers=com_csrf(api))

    assert login(novo_cliente(), "admin.adm@exemplo.com").status_code == 200  # LOGIN é outro tipo


def test_am020_trocar_senha_de_conta_suspensa_durante_a_sessao_retorna_401(api, sessao, admin):
    alvo = criar_usuario(sessao, "ATENDENTE", email="susp.troca@exemplo.com")
    navegador = novo_cliente()
    login(navegador, "susp.troca@exemplo.com")
    api.post(
        f"{ADMIN}/usuarios/{alvo.id}/suspender", json={"motivo": "Férias"}, headers=com_csrf(api)
    )

    resposta = navegador.post(
        "/api/v1/auth/trocar-senha",
        json={"senha_atual": SENHA, "senha_nova": "uma-senha-nova-forte"},
        headers=com_csrf(navegador),
    )

    assert resposta.status_code == 401


def test_rf036_auditoria_nunca_guarda_senha_nem_hash(api, sessao, admin):
    alvo = criar_usuario(sessao, "ATENDENTE", email="aud.senha@exemplo.com")
    criada = criar(api).json()["senha_temporaria"]
    redefinida = api.post(
        f"{ADMIN}/usuarios/{alvo.id}/redefinir-senha", headers=com_csrf(api)
    ).json()["senha_temporaria"]
    sessao.expire_all()

    segredos = [criada, redefinida, SENHA, *(u.senha_hash for u in sessao.scalars(select(Usuario)))]
    dump = json.dumps(
        [[a.acao, a.dados_antes, a.dados_depois] for a in sessao.scalars(select(Auditoria))],
        default=str,
    )
    assert not any(segredo in dump for segredo in segredos)


def test_rf035_atribuicoes_a_paciente_retornam_409(api, sessao, admin, mundo):
    paciente = criar_paciente(sessao)

    filas = put(api, f"{paciente.id}/filas", fila_ids=[str(mundo.fila)])
    unidades = put(api, f"{paciente.id}/unidades", unidade_ids=[str(mundo.unidade)])

    assert filas.status_code == unidades.status_code == 409
