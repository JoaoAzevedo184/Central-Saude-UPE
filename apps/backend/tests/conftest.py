import os
from pathlib import Path

from sqlalchemy import create_engine, make_url, text

# Padrões para rodar fora do Compose; dentro do container valem as variáveis do .env.
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://teleagendamento:teleagendamento@localhost:5432/teleagendamento",
)
os.environ["APP_ENV"] = "test"  # vale também dentro do container, cujo .env diz development
os.environ.setdefault("JWT_SECRET_KEY", "segredo-somente-para-testes")
os.environ.setdefault("LOGIN_HASH_KEY", "chave-de-hash-somente-para-testes")

# Os testes nunca tocam o banco de desenvolvimento: usam <POSTGRES_DB>_test, recriado a cada
# execução. Isto roda antes de qualquer import de `app`, que lê DATABASE_URL uma vez só.
URL_ORIGINAL = make_url(os.environ["DATABASE_URL"])
URL_TESTE = URL_ORIGINAL.set(database=f"{URL_ORIGINAL.database}_test")
os.environ["DATABASE_URL"] = URL_TESTE.render_as_string(hide_password=False)

from datetime import UTC, datetime  # noqa: E402

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.deps import get_relogio, get_session  # noqa: E402
from app.api.main import app  # noqa: E402
from app.infra.db import engine  # noqa: E402
from app.infra.relogio import RelogioFixo  # noqa: E402

BACKEND = Path(__file__).resolve().parent.parent


def alembic_config() -> Config:
    config = Config(str(BACKEND / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND / "migrations"))
    return config


def recriar_banco_de_teste() -> None:
    admin = create_engine(URL_ORIGINAL, isolation_level="AUTOCOMMIT")
    with admin.connect() as conexao:
        conexao.execute(text(f'DROP DATABASE IF EXISTS "{URL_TESTE.database}" WITH (FORCE)'))
        conexao.execute(text(f'CREATE DATABASE "{URL_TESTE.database}"'))
    admin.dispose()


@pytest.fixture(scope="session")
def banco():
    """Banco de teste limpo e migrado até a head. Só os testes de integração o pedem."""
    engine.dispose()
    recriar_banco_de_teste()
    command.upgrade(alembic_config(), "head")
    return engine


@pytest.fixture(autouse=True)
def _banco_para_integracao(request):
    """Todo teste marcado `integracao` recebe o banco de teste, mesmo sem pedir `banco`."""
    if request.node.get_closest_marker("integracao"):
        request.getfixturevalue("banco")


@pytest.fixture
def conexao(banco):
    """Conexão numa transação desfeita no fim do teste (o gatilho append-only impede DELETE)."""
    with banco.connect() as c:
        transacao = c.begin()
        yield c
        transacao.rollback()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def sessao(conexao):
    """Sessão do ORM dentro da transação do teste; o commit das rotas vira um SAVEPOINT."""
    with Session(bind=conexao, join_transaction_mode="create_savepoint") as s:
        yield s


@pytest.fixture
def relogio():
    return RelogioFixo(datetime(2026, 10, 19, 12, tzinfo=UTC))


IP_DO_CLIENTE = "203.0.113.5"  # faixa de documentação (RFC 5737)


@pytest.fixture
def api(sessao, relogio):
    """Cliente com a sessão de teste, o relógio fixo e um IP válido (o padrão é "testclient")."""
    app.dependency_overrides[get_session] = lambda: sessao
    app.dependency_overrides[get_relogio] = lambda: relogio
    with TestClient(app, client=(IP_DO_CLIENTE, 50000)) as c:
        yield c
    app.dependency_overrides.clear()
