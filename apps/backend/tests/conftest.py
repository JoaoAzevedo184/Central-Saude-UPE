import os

# Padrões para rodar fora do Compose; dentro do container valem as variáveis do .env.
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://teleagendamento:teleagendamento@localhost:5432/teleagendamento",
)
os.environ.setdefault("JWT_SECRET_KEY", "segredo-somente-para-testes")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.api.main import app  # noqa: E402


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
