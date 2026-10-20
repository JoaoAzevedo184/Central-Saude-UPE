from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.infra.autenticacao import abrir_sessao, apagar_dados_vencidos, registrar_tentativa
from app.infra.modelos import SessaoRefresh, TentativaLogin, Usuario

pytestmark = pytest.mark.integracao


def test_retencao_apaga_tentativas_antigas_e_sessoes_vencidas(sessao, relogio):
    agora = relogio.agora()
    usuario = Usuario(email="retencao@exemplo.com", senha_hash="x", papel="ADMIN")
    sessao.add(usuario)
    sessao.flush()
    # Família rotacionada: a sessão vencida aponta para a nova, que ainda vale.
    familia = uuid4()
    _, vencida = abrir_sessao(
        sessao, usuario.id, agora - timedelta(days=8), timedelta(days=7), None, familia
    )
    _, valida = abrir_sessao(sessao, usuario.id, agora, timedelta(days=7), None, familia)
    vencida.substituido_por_id = valida.id
    # E uma sessão vencida para a qual outra vencida aponta (as duas saem juntas).
    _, a = abrir_sessao(sessao, usuario.id, agora - timedelta(days=9), timedelta(days=7), None)
    _, b = abrir_sessao(
        sessao, usuario.id, agora - timedelta(days=8), timedelta(days=7), None, a.familia_id
    )
    a.substituido_por_id = b.id
    registrar_tentativa(sessao, "LOGIN", agora - timedelta(hours=25), None, False, "h1")
    registrar_tentativa(sessao, "LOGIN", agora - timedelta(hours=23), None, False, "h2")
    sessao.flush()

    assert apagar_dados_vencidos(sessao, agora) == 4
    assert apagar_dados_vencidos(sessao, agora) == 0  # idempotente

    assert sessao.scalars(select(SessaoRefresh.id)).all() == [valida.id]
    assert sessao.scalars(select(TentativaLogin.identificador_hash)).all() == ["h2"]
