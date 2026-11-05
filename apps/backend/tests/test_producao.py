"""Pacote de produção: docs da API desligadas e invariantes de rede do compose/nginx."""

import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from tests.raiz import raiz_do_repositorio

RAIZ = raiz_do_repositorio()
BACKEND = Path(__file__).resolve().parent.parent

CODIGO = """
from fastapi.testclient import TestClient
from app.api.main import app
c = TestClient(app)
print(c.get("/api/v1/docs").status_code, c.get("/api/v1/openapi.json").status_code,
      c.get("/api/v1/health").status_code != 404, bool(app.openapi()["paths"]))
"""


def _rotas_de_docs(app_env: str, **extra: str) -> str:
    env = {
        **os.environ,
        "APP_ENV": app_env,
        "JWT_SECRET_KEY": "a" * 40,
        "LOGIN_HASH_KEY": "b" * 40,
        "COOKIE_SECURE": "true",
        "APP_URL_PUBLICA": "https://central.exemplo.org",
        **extra,
    }
    saida = subprocess.run(
        [sys.executable, "-c", CODIGO],
        env=env,
        cwd=BACKEND,
        capture_output=True,
        text=True,
        check=True,
    )
    return saida.stdout.strip()


def test_producao_nao_serve_docs_nem_openapi_mas_mantem_a_api():
    # 404 nas duas rotas; a API segue de pé e app.openapi() continua gerável.
    assert _rotas_de_docs("production") == "404 404 True True"


def test_desenvolvimento_serve_docs_e_openapi():
    assert _rotas_de_docs("development") == "200 200 True True"


pytestmark_infra = pytest.mark.skipif(RAIZ is None, reason="raiz do repositório fora da imagem")


@pytestmark_infra
def test_compose_so_expoe_postgres_e_api_em_loopback():
    servicos = yaml.safe_load((RAIZ / "docker-compose.yml").read_text())["services"]
    for nome in ("postgres", "api", "mailpit"):
        for porta in servicos[nome]["ports"]:
            assert porta.startswith("127.0.0.1:"), f"{nome} expõe {porta} fora do loopback"
    assert "ports" not in servicos["worker"]
    assert servicos["mailpit"]["profiles"] == ["dev"]
    assert servicos["nginx"]["networks"]["borda"]["ipv4_address"] == "172.30.0.10"
    assert "172.30.0.10" in servicos["api"]["command"]


@pytestmark_infra
def test_nginx_substitui_x_forwarded_for_e_nao_o_acrescenta():
    conf = "".join(p.read_text() for p in (RAIZ / "infra/nginx").rglob("*.conf"))
    assert "proxy_set_header X-Forwarded-For $remote_addr;" in conf
    assert "$proxy_add_x_forwarded_for" not in conf
