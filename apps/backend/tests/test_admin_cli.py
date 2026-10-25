"""Comando de terminal `python -m app.infra.admin redefinir-senha` (recuperação de ADMIN)."""

import json

import pytest
from sqlalchemy import select

from app.config import get_settings
from app.infra import admin as cli
from app.infra.autenticacao import conferir_senha
from app.infra.modelos import Auditoria, SessaoRefresh, Usuario
from tests.test_auth import contar, criar_paciente, criar_usuario, login, novo_cliente

pytestmark = pytest.mark.integracao


def test_redefinir_senha_do_admin_pelo_terminal(api, sessao, relogio, monkeypatch, capsys, caplog):
    monkeypatch.setattr(get_settings(), "app_env", "production")  # funciona em qualquer APP_ENV
    admin = criar_usuario(sessao, "ADMIN", email="recupera@exemplo.com")
    navegador = novo_cliente()
    assert login(navegador, "recupera@exemplo.com").status_code == 200
    caplog.set_level("DEBUG")

    senha = cli.redefinir_senha(sessao, " Recupera@Exemplo.com ", relogio)

    sessao.refresh(admin)
    assert admin.senha_temporaria is True
    assert conferir_senha(admin.senha_hash, senha)
    assert (
        contar(
            sessao,
            SessaoRefresh,
            SessaoRefresh.usuario_id == admin.id,
            SessaoRefresh.revogado_em.is_(None),
        )
        == 0
    )
    assert navegador.get("/api/v1/me").status_code == 401
    entrou = login(novo_cliente(), "recupera@exemplo.com", senha)
    assert entrou.json()["trocar_senha"] is True
    auditoria = sessao.scalar(select(Auditoria).where(Auditoria.acao == "REDEFINIR_SENHA"))
    assert auditoria.ator_usuario_id is None  # sistema
    assert auditoria.dados_depois == {"origem": "terminal"}
    assert senha not in json.dumps([auditoria.dados_antes, auditoria.dados_depois])
    assert senha not in caplog.text


def test_terminal_so_redefine_conta_da_equipe_existente(sessao, relogio):
    criar_paciente(sessao, email="paciente.cli@exemplo.com")

    for email in ("paciente.cli@exemplo.com", "ninguem@exemplo.com"):
        with pytest.raises(cli.ContaNaoEncontrada):
            cli.redefinir_senha(sessao, email, relogio)
    assert (
        sessao.scalar(
            select(Usuario).where(Usuario.email == "paciente.cli@exemplo.com")
        ).senha_temporaria
        is False
    )


def test_main_imprime_a_senha_uma_vez_e_falha_sem_conta(sessao, monkeypatch, capsys):
    monkeypatch.setattr(cli, "SessionLocal", lambda: _Sessao(sessao))
    criar_usuario(sessao, "ADMIN", email="main.cli@exemplo.com")

    assert cli.main(["redefinir-senha", "--email", "main.cli@exemplo.com"]) == 0
    saida = capsys.readouterr().out
    assert saida.count("senha temporária") == 1
    senha = saida.rsplit(": ", 1)[1].strip()
    usuario = sessao.scalar(select(Usuario).where(Usuario.email == "main.cli@exemplo.com"))
    assert conferir_senha(usuario.senha_hash, senha)

    assert cli.main(["redefinir-senha", "--email", "ninguem@exemplo.com"]) == 1
    assert "não encontrada" in capsys.readouterr().err


class _Sessao:
    """Entrega a sessão do teste sem fechá-la (o `with` do comando chamaria `close`)."""

    def __init__(self, sessao):
        self.sessao = sessao

    def __enter__(self):
        return self.sessao

    def __exit__(self, *_):
        return False
