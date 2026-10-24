"""Autenticação, sessão e suspensão (ADR-003, ADR-028, UC-001, AM-002, AM-004, AM-005, AM-013)."""

import logging
from datetime import date, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.api.main import app
from app.config import get_settings
from app.infra.autenticacao import hash_identificador, hash_senha, sha256
from app.infra.modelos import (
    Auditoria,
    Consentimento,
    Outbox,
    Paciente,
    SessaoRefresh,
    TentativaLogin,
    Usuario,
)
from tests.conftest import IP_DO_CLIENTE
from tests.sinteticos import cns_definitivo, cpf

pytestmark = pytest.mark.integracao

SENHA = "senha-de-teste-123"
CSRF = get_settings().csrf_header_name
CPF_PACIENTE = cpf("111444777")


# --- apoio --------------------------------------------------------------------------------


def criar_usuario(sessao, papel, email=None, situacao="ATIVO", relogio=None):
    usuario = Usuario(
        email=email or f"{uuid4().hex[:8]}@exemplo.com",
        senha_hash=hash_senha(SENHA),
        papel=papel,
        situacao=situacao,
        suspenso_em=relogio.agora() if situacao == "SUSPENSO" else None,
    )
    sessao.add(usuario)
    sessao.flush()
    return usuario


def criar_paciente(sessao, cpf_=CPF_PACIENTE, email="paciente.teste@exemplo.com"):
    usuario = criar_usuario(sessao, "PACIENTE", email=email)
    sessao.add(
        Paciente(
            usuario_id=usuario.id,
            nome="Paciente Sintética",
            cpf=cpf_,
            data_nascimento=date(1985, 3, 2),
        )
    )
    sessao.flush()
    return usuario


def login(cliente, identificador, senha=SENHA):
    return cliente.post("/api/v1/auth/login", json={"identificador": identificador, "senha": senha})


def com_csrf(cliente):
    return {CSRF: cliente.cookies.get("csrf_token", "")}


def postar_com_cookies(cliente, caminho, **cookies):
    """POST só com os cookies indicados (o jar do cliente é esvaziado)."""
    cliente.cookies.clear()
    cookie = "; ".join(f"{nome}={valor}" for nome, valor in cookies.items())
    return cliente.post(caminho, headers={"Cookie": cookie, CSRF: cookies.get("csrf_token", "")})


def novo_cliente():
    """Segundo cliente (outro navegador), com as mesmas dependências trocadas do `api`."""
    return TestClient(app, client=("198.51.100.20", 50000))


def set_cookies(resposta):
    return {c.split("=", 1)[0]: c for c in resposta.headers.get_list("set-cookie")}


def contar(sessao, modelo, *filtros):
    return sessao.scalar(select(func.count()).select_from(modelo).where(*filtros))


# --- login --------------------------------------------------------------------------------


def test_adr003_login_do_paciente_por_cpf(api, sessao):
    criar_paciente(sessao)

    resposta = login(api, "111.444.777-35")

    assert resposta.status_code == 200, resposta.text
    corpo = resposta.json()
    assert corpo["papel"] == "PACIENTE"
    assert corpo["expira_em"].startswith("2026-10-19T12:15:00")
    assert "token" not in resposta.text  # ADR-003: tokens só em cookie
    assert {"access_token", "refresh_token", "csrf_token"} <= set(resposta.cookies)
    assert api.get("/api/v1/me").json()["nome"] == "Paciente Sintética"


def test_adr003_login_da_equipe_por_email(api, sessao):
    criar_usuario(sessao, "ATENDENTE", email="atendente.x@exemplo.com")

    resposta = login(api, " Atendente.X@Exemplo.com ")

    assert resposta.status_code == 200
    assert resposta.json()["papel"] == "ATENDENTE"


def test_am005_credenciais_invalidas_tem_resposta_identica(api, sessao, relogio):
    criar_paciente(sessao)
    criar_usuario(sessao, "ADMIN", email="admin.x@exemplo.com")
    criar_usuario(
        sessao, "ATENDENTE", email="suspenso.x@exemplo.com", situacao="SUSPENSO", relogio=relogio
    )

    respostas = [
        login(api, "admin.x@exemplo.com", "senha-errada-123"),  # senha errada
        login(api, "ninguem@exemplo.com"),  # e-mail inexistente
        login(api, cpf("999888777")),  # CPF inexistente
        login(api, "suspenso.x@exemplo.com"),  # suspenso com a senha certa
        login(api, "paciente.teste@exemplo.com"),  # paciente não entra pelo e-mail
    ]

    assert {r.status_code for r in respostas} == {401}
    assert len({r.text for r in respostas}) == 1
    assert respostas[0].json()["type"] == "/problemas/credenciais-invalidas"
    assert all(r.headers["cache-control"] == "no-store" for r in respostas)


def test_am004_bloqueio_por_identificador_inclusive_inexistente(api, sessao, relogio):
    limite = get_settings().login_max_tentativas
    clientes = [TestClient(app, client=(f"198.51.100.{i}", 1)) for i in range(limite + 1)]

    # Cada tentativa de um IP diferente: o bloqueio vem do identificador.
    for cliente in clientes[:limite]:
        assert login(cliente, "fantasma@exemplo.com", "x").status_code == 401
    bloqueada = login(clientes[limite], "fantasma@exemplo.com", "x")

    assert bloqueada.status_code == 429
    assert bloqueada.json()["type"] == "/problemas/muitas-tentativas"
    assert "fantasma" not in bloqueada.text
    assert bloqueada.headers["retry-after"] == str(get_settings().login_janela_min * 60)

    relogio.avancar(timedelta(minutes=get_settings().login_janela_min, seconds=1))
    assert login(clientes[limite], "fantasma@exemplo.com", "x").status_code == 401


def test_am004_bloqueio_por_ip_vale_ate_com_a_senha_certa(api, sessao):
    criar_usuario(sessao, "GESTOR", email="gestor.x@exemplo.com")
    for i in range(get_settings().login_max_tentativas):
        assert login(api, f"tentativa{i}@exemplo.com", "x").status_code == 401

    assert login(api, "gestor.x@exemplo.com").status_code == 429
    assert login(novo_cliente(), "gestor.x@exemplo.com").status_code == 200


def test_am004_tentativa_guarda_hash_e_nao_o_identificador(api, sessao):
    antes = contar(sessao, Auditoria)

    login(api, "Fulano.Teste@Exemplo.com", "x")

    tentativa = sessao.scalar(select(TentativaLogin))
    assert tentativa.identificador_hash == hash_identificador("fulano.teste@exemplo.com")
    assert tentativa.identificador_hash != sha256("fulano.teste@exemplo.com")  # HMAC com chave
    assert str(tentativa.ip) == IP_DO_CLIENTE
    assert tentativa.sucesso is False
    linhas = sessao.execute(text("SELECT t::text FROM tentativa_login t")).scalars().all()
    assert not any("fulano" in linha.lower() for linha in linhas)
    assert contar(sessao, Auditoria) == antes  # falha não vai para a auditoria


def test_rn010_login_com_sucesso_gera_auditoria(api, sessao):
    usuario = criar_usuario(sessao, "ADMIN", email="admin.y@exemplo.com")

    login(api, "admin.y@exemplo.com")

    registro = sessao.scalar(select(Auditoria).where(Auditoria.acao == "LOGIN"))
    assert registro.ator_usuario_id == usuario.id
    assert str(registro.ip) == IP_DO_CLIENTE


def test_adr003_xff_so_vale_vindo_do_nginx(sessao, api):
    # O mesmo IP de `--forwarded-allow-ips` no docker-compose.yml.
    app_com_proxy = ProxyHeadersMiddleware(app, trusted_hosts="172.30.0.10")
    forjado = {"X-Forwarded-For": "192.0.2.99"}

    for origem, esperado in (("198.51.100.7", "198.51.100.7"), ("172.30.0.10", "192.0.2.99")):
        cliente = TestClient(app_com_proxy, client=(origem, 1))
        cliente.post(
            "/api/v1/auth/login",
            json={"identificador": f"{origem}@exemplo.com", "senha": "x"},
            headers=forjado,
        )
        hash_ = hash_identificador(f"{origem}@exemplo.com")
        tentativa = sessao.scalar(
            select(TentativaLogin).where(TentativaLogin.identificador_hash == hash_)
        )
        assert str(tentativa.ip) == esperado


# --- refresh ------------------------------------------------------------------------------


def test_adr003_refresh_rotaciona_o_token(api, sessao):
    criar_paciente(sessao)
    antigo = login(api, CPF_PACIENTE).cookies["refresh_token"]

    resposta = api.post("/api/v1/auth/refresh", headers=com_csrf(api))

    assert resposta.status_code == 200
    novo = resposta.cookies["refresh_token"]
    assert novo != antigo
    linha_antiga = sessao.scalar(
        select(SessaoRefresh).where(SessaoRefresh.token_hash == sha256(antigo))
    )
    linha_nova = sessao.scalar(
        select(SessaoRefresh).where(SessaoRefresh.token_hash == sha256(novo))
    )
    assert linha_antiga.revogado_em is not None
    assert linha_antiga.substituido_por_id == linha_nova.id
    assert linha_nova.familia_id == linha_antiga.familia_id
    assert linha_nova.revogado_em is None
    assert contar(sessao, SessaoRefresh, SessaoRefresh.token_hash == antigo) == 0  # só o hash


def test_adr003_reuso_do_refresh_revoga_a_familia(api, sessao, relogio):
    criar_paciente(sessao)
    primeiro = login(api, CPF_PACIENTE)
    antigo, csrf = primeiro.cookies["refresh_token"], primeiro.cookies["csrf_token"]
    renovado = api.post("/api/v1/auth/refresh", headers=com_csrf(api))
    novo, access = renovado.cookies["refresh_token"], renovado.cookies["access_token"]
    relogio.avancar(timedelta(seconds=get_settings().refresh_tolerancia_s))  # fim da tolerância

    reuso = postar_com_cookies(api, "/api/v1/auth/refresh", refresh_token=antigo, csrf_token=csrf)
    depois = postar_com_cookies(api, "/api/v1/auth/refresh", refresh_token=novo, csrf_token=csrf)

    assert reuso.status_code == 401
    assert depois.status_code == 401  # o token legítimo também caiu
    api.cookies.clear()
    api.cookies.set("access_token", access)
    assert api.get("/api/v1/me").status_code == 401  # e o access token da família, na hora
    familia = sessao.scalar(
        select(SessaoRefresh.familia_id).where(SessaoRefresh.token_hash == sha256(novo))
    )
    assert (
        contar(
            sessao,
            SessaoRefresh,
            SessaoRefresh.familia_id == familia,
            SessaoRefresh.revogado_em.is_(None),
        )
        == 0
    )


def test_adr003_refresh_reapresentado_na_tolerancia_nao_revoga_a_familia(api, sessao, relogio):
    criar_paciente(sessao)
    primeiro = login(api, CPF_PACIENTE)
    antigo, csrf = primeiro.cookies["refresh_token"], primeiro.cookies["csrf_token"]
    novo = api.post("/api/v1/auth/refresh", headers=com_csrf(api)).cookies["refresh_token"]
    relogio.avancar(timedelta(seconds=get_settings().refresh_tolerancia_s - 1))

    outra_aba = postar_com_cookies(
        api, "/api/v1/auth/refresh", refresh_token=antigo, csrf_token=csrf
    )

    assert outra_aba.status_code == 200
    terceiro = outra_aba.cookies["refresh_token"]
    familia = sessao.scalar(
        select(SessaoRefresh.familia_id).where(SessaoRefresh.token_hash == sha256(antigo))
    )
    assert (
        sessao.scalar(
            select(SessaoRefresh.familia_id).where(SessaoRefresh.token_hash == sha256(terceiro))
        )
        == familia
    )
    for token in (novo, terceiro):  # nenhum dos dois foi revogado
        resposta = postar_com_cookies(
            api, "/api/v1/auth/refresh", refresh_token=token, csrf_token=csrf
        )
        assert resposta.status_code == 200


def test_am003_segunda_reapresentacao_na_tolerancia_revoga_a_familia(api, sessao, relogio):
    criar_paciente(sessao)
    primeiro = login(api, CPF_PACIENTE)
    antigo, csrf = primeiro.cookies["refresh_token"], primeiro.cookies["csrf_token"]
    novo = api.post("/api/v1/auth/refresh", headers=com_csrf(api)).cookies["refresh_token"]
    relogio.avancar(timedelta(seconds=1))

    outra_aba = postar_com_cookies(
        api, "/api/v1/auth/refresh", refresh_token=antigo, csrf_token=csrf
    )
    segunda = postar_com_cookies(api, "/api/v1/auth/refresh", refresh_token=antigo, csrf_token=csrf)

    assert outra_aba.status_code == 200
    assert segunda.status_code == 401  # ainda dentro dos 10 s, mas a tolerância já foi usada
    for token in (novo, outra_aba.cookies["refresh_token"]):  # a família inteira caiu
        resposta = postar_com_cookies(
            api, "/api/v1/auth/refresh", refresh_token=token, csrf_token=csrf
        )
        assert resposta.status_code == 401


def test_adr003_logout_corta_o_access_token_na_hora(api, sessao):
    criar_paciente(sessao)
    access = login(api, CPF_PACIENTE).cookies["access_token"]
    assert api.post("/api/v1/auth/logout", headers=com_csrf(api)).status_code == 204

    api.cookies.clear()
    api.cookies.set("access_token", access)

    assert api.get("/api/v1/me").status_code == 401


def test_adr003_refresh_vencido_retorna_401(api, sessao, relogio):
    criar_paciente(sessao)
    login(api, CPF_PACIENTE)

    relogio.avancar(timedelta(days=get_settings().refresh_token_ttl_dias, seconds=1))

    assert api.post("/api/v1/auth/refresh", headers=com_csrf(api)).status_code == 401


def test_adr003_access_token_vencido_retorna_401(api, sessao, relogio):
    criar_paciente(sessao)
    login(api, CPF_PACIENTE)

    relogio.avancar(timedelta(minutes=get_settings().access_token_ttl_minutos, seconds=1))

    assert api.get("/api/v1/me").status_code == 401


def test_adr003_logout_revoga_a_familia_e_apaga_cookies(api, sessao):
    criar_paciente(sessao)
    refresh = login(api, CPF_PACIENTE).cookies["refresh_token"]

    resposta = api.post("/api/v1/auth/logout", headers=com_csrf(api))

    assert resposta.status_code == 204
    apagados = set_cookies(resposta)
    assert {"access_token", "refresh_token", "csrf_token"} <= set(apagados)
    assert "Path=/api/v1/auth" in apagados["refresh_token"]
    linha = sessao.scalar(select(SessaoRefresh).where(SessaoRefresh.token_hash == sha256(refresh)))
    assert linha.revogado_em is not None


def test_adr003_logout_sem_sessao_e_idempotente(api):
    resposta = postar_com_cookies(api, "/api/v1/auth/logout", csrf_token="abc")

    assert resposta.status_code == 204


# --- CSRF ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "caminho",
    ["/api/v1/auth/refresh", "/api/v1/auth/logout", f"/api/v1/usuarios/{uuid4()}/suspender"],
)
def test_am002_escrita_sem_header_csrf_retorna_403(api, sessao, caminho):
    criar_usuario(sessao, "ADMIN", email="admin.csrf@exemplo.com")
    login(api, "admin.csrf@exemplo.com")

    sem_header = api.post(caminho, json={"motivo": "teste"})
    diferente = api.post(caminho, json={"motivo": "teste"}, headers={CSRF: "outro-valor"})

    for resposta in (sem_header, diferente):
        assert resposta.status_code == 403
        assert resposta.json()["type"] == "/problemas/csrf-invalido"


# --- cookies ------------------------------------------------------------------------------


def test_adr003_atributos_dos_cookies_padrao(api, sessao):
    criar_paciente(sessao)

    cookies = set_cookies(login(api, CPF_PACIENTE))

    assert "HttpOnly" in cookies["refresh_token"]
    assert "Path=/api/v1/auth" in cookies["refresh_token"]
    assert "SameSite=lax" in cookies["refresh_token"]
    assert "Secure" not in cookies["refresh_token"]
    assert "HttpOnly" in cookies["access_token"]
    assert "Path=/api/v1;" in cookies["access_token"]
    assert "HttpOnly" not in cookies["csrf_token"]


def test_adr003_cookies_seguem_a_configuracao(api, sessao, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "cookie_secure", True)
    monkeypatch.setattr(settings, "cookie_samesite", "strict")
    monkeypatch.setattr(settings, "cookie_domain", "central.exemplo.com")
    criar_paciente(sessao)

    cookies = set_cookies(login(api, CPF_PACIENTE))

    for nome in ("access_token", "refresh_token", "csrf_token"):
        assert "Secure" in cookies[nome]
        assert "SameSite=strict" in cookies[nome]
        assert "Domain=central.exemplo.com" in cookies[nome]


# --- suspensão (ADR-028) ------------------------------------------------------------------


@pytest.fixture
def admin(api, sessao):
    usuario = criar_usuario(sessao, "ADMIN", email="admin.z@exemplo.com")
    assert login(api, "admin.z@exemplo.com").status_code == 200
    return usuario


def suspender(api, usuario_id, motivo="Férias (dado sintético)"):
    return api.post(
        f"/api/v1/usuarios/{usuario_id}/suspender", json={"motivo": motivo}, headers=com_csrf(api)
    )


def test_adr028_suspensao_corta_o_acesso_na_hora(api, sessao, admin):
    atendente = criar_usuario(sessao, "ATENDENTE", email="atendente.z@exemplo.com")
    navegador = novo_cliente()
    assert login(navegador, "atendente.z@exemplo.com").status_code == 200
    assert navegador.get("/api/v1/me").status_code == 200

    assert suspender(api, atendente.id).status_code == 204

    assert navegador.get("/api/v1/me").status_code == 401  # access token ainda não venceu
    assert navegador.post("/api/v1/auth/refresh", headers=com_csrf(navegador)).status_code == 401
    assert (
        contar(
            sessao,
            SessaoRefresh,
            SessaoRefresh.usuario_id == atendente.id,
            SessaoRefresh.revogado_em.is_(None),
        )
        == 0
    )
    sessao.refresh(atendente)
    assert atendente.situacao == "SUSPENSO"
    assert atendente.suspenso_em is not None
    assert atendente.motivo_suspensao == "Férias (dado sintético)"
    assert login(novo_cliente(), "atendente.z@exemplo.com").status_code == 401


def test_adr028_reativar_devolve_o_acesso_e_audita(api, sessao, admin):
    atendente = criar_usuario(sessao, "ATENDENTE", email="atendente.w@exemplo.com")
    suspender(api, atendente.id)

    resposta = api.post(f"/api/v1/usuarios/{atendente.id}/reativar", headers=com_csrf(api))

    assert resposta.status_code == 204
    assert login(novo_cliente(), "atendente.w@exemplo.com").status_code == 200
    acoes = sessao.scalars(
        select(Auditoria.acao)
        .where(Auditoria.entidade_id == atendente.id)
        .order_by(Auditoria.ocorrido_em, Auditoria.acao.desc())
    ).all()
    assert set(acoes) >= {"SUSPENDER", "REATIVAR"}
    auditoria = sessao.scalar(select(Auditoria).where(Auditoria.acao == "SUSPENDER"))
    assert auditoria.ator_usuario_id == admin.id


def test_adr028_nao_suspende_a_si_mesmo(api, admin):
    resposta = suspender(api, admin.id)

    assert resposta.status_code == 409
    assert resposta.json()["type"] == "/problemas/operacao-nao-permitida"


def test_adr028_nao_suspende_paciente(api, sessao, admin):
    paciente = criar_paciente(sessao)

    assert suspender(api, paciente.id).status_code == 409


def test_adr028_usuario_inexistente_retorna_404(api, admin):
    assert suspender(api, uuid4()).status_code == 404
    reativar = api.post(f"/api/v1/usuarios/{uuid4()}/reativar", headers=com_csrf(api))
    assert reativar.status_code == 404


@pytest.mark.parametrize("papel", ["PACIENTE", "ATENDENTE", "GESTOR"])
def test_adr028_so_admin_suspende(api, sessao, papel):
    if papel == "PACIENTE":
        criar_paciente(sessao)
        login(api, CPF_PACIENTE)
    else:
        criar_usuario(sessao, papel, email="nao.admin@exemplo.com")
        login(api, "nao.admin@exemplo.com")
    alvo = criar_usuario(sessao, "ATENDENTE")

    resposta = suspender(api, alvo.id)

    assert resposta.status_code == 403
    assert resposta.json()["type"] == "/problemas/sem-permissao"


def test_adr028_suspender_sem_sessao_retorna_401(api, sessao):
    alvo = criar_usuario(sessao, "ATENDENTE")

    resposta = postar_com_cookies(api, f"/api/v1/usuarios/{alvo.id}/suspender", csrf_token="abc")

    assert resposta.status_code == 401


# --- /me ----------------------------------------------------------------------------------


def test_adr007_me_do_paciente_sem_fila(api, sessao):
    usuario = criar_paciente(sessao)
    login(api, CPF_PACIENTE)

    resposta = api.get("/api/v1/me")

    assert resposta.json() == {
        "id": str(usuario.id),
        "papel": "PACIENTE",
        "nome": "Paciente Sintética",
        "filas": None,
    }
    assert resposta.headers["cache-control"] == "no-store"


def test_adr025_me_da_equipe_traz_o_escopo(api, sessao):
    criar_usuario(sessao, "ATENDENTE", email="atendente.sem.fila@exemplo.com")
    login(api, "atendente.sem.fila@exemplo.com")

    assert api.get("/api/v1/me").json()["filas"] == []


def test_adr007_me_tem_sempre_as_mesmas_chaves(api, sessao):
    """Paciente: `filas` null. Equipe: `nome` null. Nenhuma chave some da resposta."""
    criar_paciente(sessao)
    equipe = criar_usuario(sessao, "ATENDENTE", email="atendente.chaves@exemplo.com")
    login(api, CPF_PACIENTE)
    do_paciente = api.get("/api/v1/me").json()
    login(api, equipe.email)
    da_equipe = api.get("/api/v1/me").json()

    assert set(do_paciente) == set(da_equipe) == {"id", "papel", "nome", "filas"}
    assert do_paciente["filas"] is None and do_paciente["nome"]
    assert da_equipe["nome"] is None and da_equipe["filas"] == []


# --- registro (UC-001) --------------------------------------------------------------------


def dados_registro(**mudancas):
    dados = {
        "nome": "Joana Sintética",
        "cpf": cpf("222333444"),
        "cns": cns_definitivo("12345678901"),
        "data_nascimento": "1990-04-12",
        "sexo": "FEMININO",
        "municipio": "Olinda",
        "telefone": "(81) 99999-0000",
        "email": "joana.sintetica@exemplo.com",
        "senha": "uma-senha-longa",
        "aceite_termo": True,
        "versao_termo": "1.0",
    }
    dados.update(mudancas)
    return {k: v for k, v in dados.items() if v is not None}


def registrar(cliente, **mudancas):
    return cliente.post("/api/v1/auth/registro", json=dados_registro(**mudancas))


def test_uc001_registro_cria_conta_consentimento_e_sessao(api, sessao):
    resposta = registrar(api)

    assert resposta.status_code == 201, resposta.text
    assert resposta.json()["papel"] == "PACIENTE"
    assert resposta.headers["cache-control"] == "no-store"
    assert {"access_token", "refresh_token", "csrf_token"} <= set(resposta.cookies)
    paciente = sessao.scalar(select(Paciente).where(Paciente.cpf == cpf("222333444")))
    usuario = sessao.get(Usuario, paciente.usuario_id)
    assert usuario.papel == "PACIENTE"
    assert usuario.senha_hash.startswith("$argon2id$")
    assert "uma-senha-longa" not in usuario.senha_hash
    consentimentos = sessao.scalars(
        select(Consentimento).where(Consentimento.paciente_id == paciente.id)
    ).all()
    assert [(c.finalidade, c.versao_termo) for c in consentimentos] == [("AGENDAMENTO", "1.0")]
    assert sessao.scalar(select(Auditoria).where(Auditoria.acao == "REGISTRO")).entidade_id == (
        paciente.id
    )
    assert api.get("/api/v1/me").json()["nome"] == "Joana Sintética"  # sessão iniciada
    assert login(novo_cliente(), cpf("222333444"), "uma-senha-longa").status_code == 200


def test_uc001_registro_sem_email_e_com_lembrete(api, sessao):
    assert registrar(api, email=None).status_code == 201
    assert (
        registrar(
            api,
            cpf=cpf("555666777"),
            cns=cns_definitivo("20000000002"),
            email=None,
            aceite_lembrete_email=True,
        ).status_code
        == 422
    )
    assert (
        registrar(
            api,
            cpf=cpf("555666777"),
            cns=cns_definitivo("20000000002"),
            email="com.lembrete@exemplo.com",
            aceite_lembrete_email=True,
        ).status_code
        == 201
    )
    finalidades = sessao.scalars(
        select(Consentimento.finalidade)
        .join(Paciente, Paciente.id == Consentimento.paciente_id)
        .where(Paciente.cpf == cpf("555666777"))
    ).all()
    assert sorted(finalidades) == ["AGENDAMENTO", "LEMBRETE_EMAIL"]


@pytest.mark.parametrize(
    "mudanca",
    [
        {"cpf": "22233344400"},  # dígito verificador errado
        {"cpf": "11111111111"},
        {"cns": "123456789019999"},
        {"cns": None},  # obrigatório (RF-001)
        {"senha": "curta"},
        {"aceite_termo": False},  # consentimento obrigatório
        {"data_nascimento": "2026-10-20"},  # futuro
        {"data_nascimento": "1890-01-01"},  # mais de 130 anos
        {"email": "sem-arroba"},
        {"sexo": "OUTRO"},
        {"versao_termo": "0.9"},  # só a versão vigente (TERMO_VERSAO_ATUAL)
    ],
)
def test_uc001_dados_invalidos_retornam_422_e_nada_e_criado(api, sessao, mudanca):
    antes = contar(sessao, Usuario)

    resposta = registrar(api, **mudanca)

    assert resposta.status_code == 422
    assert resposta.headers["cache-control"] == "no-store"
    assert contar(sessao, Usuario) == antes


@pytest.mark.parametrize(
    "campo",
    [
        {"papel": "ADMIN"},
        {"situacao": "ATIVO"},
        {"classificacao_risco": "VERMELHO"},
        {"id": str(uuid4())},
        {"usuario_id": str(uuid4())},
    ],
)
def test_am013_registro_recusa_campos_proibidos(api, sessao, campo):
    resposta = registrar(api, **campo)

    assert resposta.status_code == 422
    assert contar(sessao, Usuario) == 0


@pytest.mark.parametrize(
    "repetido",
    [
        {"email": "outra.pessoa@exemplo.com"},  # mesmo CPF
        {"cpf": cpf("888777666"), "email": "outra.pessoa@exemplo.com"},  # mesmo CNS
        {"cpf": cpf("888777666"), "cns": cns_definitivo("10000000001")},  # mesmo e-mail
    ],
)
def test_am005_registro_duplicado_tem_resposta_generica(api, sessao, repetido):
    assert registrar(api).status_code == 201
    usuarios = contar(sessao, Usuario)

    resposta = registrar(novo_cliente(), **repetido)

    assert resposta.status_code == 409
    assert resposta.json() == {
        "type": "/problemas/cadastro-nao-concluido",
        "title": "Conflict",
        "status": 409,
        "detail": "Não foi possível concluir o cadastro. Se você já tem conta, entre com seu CPF.",
    }
    assert contar(sessao, Usuario) == usuarios
    assert contar(sessao, Outbox) == 0
    assert "access_token" not in resposta.cookies


def test_am004_registro_limitado_por_ip(api, sessao, monkeypatch):
    limite = 3  # o padrão é REGISTRO_MAX_TENTATIVAS=20; menor para o teste ser rápido
    monkeypatch.setattr(get_settings(), "registro_max_tentativas", limite)
    for i in range(limite):
        resposta = registrar(
            api,
            cpf=cpf(f"30000000{i}"),
            cns=cns_definitivo(f"1000000000{i}"),
            email=f"lote{i}@exemplo.com",
        )
        assert resposta.status_code == 201

    excedente = registrar(api, cpf=cpf("400000000"), cns=cns_definitivo("20000000009"), email=None)

    assert excedente.status_code == 429
    assert contar(sessao, TentativaLogin, TentativaLogin.tipo == "REGISTRO") == limite


# --- logs ---------------------------------------------------------------------------------


def test_am008_logs_de_registro_e_login_sem_dados_pessoais(api, sessao, caplog):
    caplog.set_level(logging.DEBUG)

    registro = registrar(api)
    falha = login(novo_cliente(), cpf("222333444"), "senha-errada-999")
    sucesso = login(novo_cliente(), cpf("222333444"), "uma-senha-longa")

    assert falha.status_code == 401 and sucesso.status_code == 200
    proibidos = [
        cpf("222333444"),
        "joana.sintetica@exemplo.com",
        "Joana Sintética",
        "uma-senha-longa",
        "senha-errada-999",
        *registro.cookies.values(),
        *sucesso.cookies.values(),
    ]
    assert "login: usuario=" in caplog.text  # há log, mas só com IDs
    for valor in proibidos:
        assert valor not in caplog.text


def test_adr003_tolerancia_nao_revive_familia_encerrada_no_logout(api, sessao):
    criar_paciente(sessao)
    primeiro = login(api, CPF_PACIENTE)
    antigo, csrf = primeiro.cookies["refresh_token"], primeiro.cookies["csrf_token"]
    api.post("/api/v1/auth/refresh", headers=com_csrf(api))
    api.post("/api/v1/auth/logout", headers=com_csrf(api))

    resposta = postar_com_cookies(
        api, "/api/v1/auth/refresh", refresh_token=antigo, csrf_token=csrf
    )

    assert resposta.status_code == 401  # ainda dentro dos 10 s, mas a família foi encerrada


# --- termo vigente (item 5) ---------------------------------------------------------------


def test_uc001_termo_vigente_e_publico_com_cache_curto(api):
    resposta = api.get("/api/v1/termos/vigente")

    assert resposta.status_code == 200
    assert resposta.headers["cache-control"] == "public, max-age=3600"
    assert resposta.json()["versao"] == get_settings().termo_versao_atual
    assert "provisório" in resposta.json()["texto"].lower()


def test_uc001_registro_aceita_a_versao_que_o_termo_devolve(api, sessao):
    versao = api.get("/api/v1/termos/vigente").json()["versao"]

    resposta = registrar(api, versao_termo=versao)

    assert resposta.status_code == 201, resposta.text
    assert registrar(api, versao_termo=versao + "-velha").status_code == 422


def test_uc001_termo_configurado_tem_arquivo_de_texto():
    from app.api.rotas.termos import PASTA_TERMOS

    assert (PASTA_TERMOS / f"{get_settings().termo_versao_atual}.md").is_file()


PALAVRAS_DE_EXISTENCIA = ("já cadastrad", "já existe", "já está", "já tem", "já possui", "duplicad", "em uso")


@pytest.mark.parametrize(
    "mudanca",
    [{"email": "sem-arroba"}, {"senha": "curta"}, {"cns": "123456789019999"}, {"aceite_termo": False}],
)
def test_am005_422_do_registro_nao_revela_existencia_de_cpf_cns_ou_email(api, sessao, mudanca):
    assert registrar(api).status_code == 201  # CPF, CNS e e-mail de dados_registro() já existem
    # mesmo CPF/CNS/e-mail do cadastro existente, só com o campo inválido
    existente = registrar(novo_cliente(), **mudanca)
    # CPF/CNS/e-mail inéditos, mesmo campo inválido
    inedito = registrar(
        novo_cliente(),
        **{
            "cpf": cpf("888777666"),
            "cns": cns_definitivo("10000000001"),
            "email": "outra.pessoa@exemplo.com",
            **mudanca,
        },
    )

    assert existente.status_code == inedito.status_code == 422
    for resposta in (existente, inedito):
        texto = resposta.text.lower()
        assert not any(palavra in texto for palavra in PALAVRAS_DE_EXISTENCIA)
    # a validação não depende do que existe no banco: mesmos campos acusados, mesmas mensagens
    def erros(resposta):
        return sorted((tuple(e["loc"]), e["msg"]) for e in resposta.json()["errors"])

    assert erros(existente) == erros(inedito)


def test_am005_422_do_login_nao_revela_existencia_de_cpf_ou_email(api, sessao):
    criar_paciente(sessao)
    criar_usuario(sessao, "ATENDENTE", email="equipe.teste@exemplo.com")

    # identificador existente (CPF e e-mail) e inexistente, sem a senha
    respostas = [
        api.post("/api/v1/auth/login", json={"identificador": i})
        for i in (CPF_PACIENTE, "equipe.teste@exemplo.com", cpf("888777666"))
    ]

    assert {r.status_code for r in respostas} == {422}
    for resposta in respostas:
        assert not any(p in resposta.text.lower() for p in PALAVRAS_DE_EXISTENCIA)
    assert len({tuple((tuple(e["loc"]), e["msg"]) for e in r.json()["errors"]) for r in respostas}) == 1
