import pytest
from fastapi import HTTPException

from app.api.deps import usuario_da_sessao


def test_adr025_sem_autenticacao_o_escopo_falha_fechado():
    # A regra do escopo está em dominio/acesso.py (tests/dominio/test_acesso.py). Até existir
    # autenticação, a dependência não identifica usuário e nenhuma rota da equipe responde.
    with pytest.raises(HTTPException) as erro:
        usuario_da_sessao()

    assert erro.value.status_code == 401
