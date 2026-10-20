def test_adr025_sem_autenticacao_o_escopo_falha_fechado(client):
    # A regra do escopo está em dominio/acesso.py (tests/dominio/test_acesso.py). Sem sessão,
    # `usuario_da_sessao` responde 401 antes de qualquer escopo ser calculado.
    resposta = client.get("/api/v1/me")

    assert resposta.status_code == 401
    assert resposta.json()["type"] == "/problemas/nao-autenticado"
