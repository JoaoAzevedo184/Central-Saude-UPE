import pytest
from sqlalchemy.exc import OperationalError

from app.api.deps import get_session


@pytest.mark.integracao
def test_health_com_banco_responde_200(client):
    resposta = client.get("/api/v1/health")

    assert resposta.status_code == 200
    assert resposta.json() == {"status": "ok"}


class _SessaoSemBanco:
    def execute(self, *_args, **_kwargs):
        raise OperationalError("SELECT 1", {}, Exception("host=segredo senha=segredo"))


def test_health_sem_banco_responde_503_em_problem_details(client):
    client.app.dependency_overrides[get_session] = lambda: _SessaoSemBanco()

    resposta = client.get("/api/v1/health")

    assert resposta.status_code == 503
    assert resposta.headers["content-type"] == "application/problem+json"
    corpo = resposta.json()
    assert corpo["status"] == 503
    assert {"type", "title", "detail"} <= corpo.keys()
    assert "segredo" not in resposta.text


def test_rota_inexistente_responde_404_em_problem_details(client):
    resposta = client.get("/api/v1/nao-existe")

    assert resposta.status_code == 404
    assert resposta.headers["content-type"] == "application/problem+json"
