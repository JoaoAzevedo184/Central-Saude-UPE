from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import Settings

# Na raiz do repositório. Na imagem (/app/tests) não há parents[3]: o teste é pulado.
_PAIS = Path(__file__).resolve().parents
ENV_EXAMPLE = _PAIS[3] / ".env.example" if len(_PAIS) > 3 else None


def test_le_variaveis_do_ambiente(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173, http://localhost:3000")
    monkeypatch.setenv("MATCHING_AUTOMATICO", "false")
    monkeypatch.setenv("PROPOSTA_JANELA_MINIMA_HORAS", "6")
    monkeypatch.setenv("WORKER_INTERVALO_OUTBOX_S", "2")

    settings = Settings()

    assert settings.cors_origins_lista == ["http://localhost:5173", "http://localhost:3000"]
    assert settings.matching_automatico is False
    assert settings.proposta_janela_minima_horas == 6
    assert settings.worker_intervalo_outbox_s == 2


def test_padroes_seguem_as_decisoes(monkeypatch):
    monkeypatch.delenv("MATCHING_AUTOMATICO", raising=False)
    monkeypatch.delenv("PROPOSTA_JANELA_MINIMA_HORAS", raising=False)

    settings = Settings()

    assert settings.matching_automatico is True  # ADR-021
    assert settings.proposta_janela_minima_horas == 12  # ADR-021


def test_adr025_variavel_antiga_de_escopo_e_ignorada(monkeypatch):
    # .env antigo com ESCOPO_POR_UNIDADE não quebra a inicialização (extra="ignore").
    monkeypatch.setenv("ESCOPO_POR_UNIDADE", "true")

    assert not hasattr(Settings(), "escopo_por_unidade")


@pytest.mark.skipif(
    ENV_EXAMPLE is None or not ENV_EXAMPLE.exists(), reason=".env.example fica fora da imagem"
)
def test_env_example_traz_toda_variavel_obrigatoria():
    # Sem isso, um .env copiado do exemplo derruba o migrate com "Field required".
    chaves = {
        linha.split("=", 1)[0]
        for linha in ENV_EXAMPLE.read_text().splitlines()
        if "=" in linha and not linha.startswith("#")
    }
    obrigatorias = {
        nome.upper() for nome, campo in Settings.model_fields.items() if campo.is_required()
    }
    # DATABASE_URL é montada no docker-compose.yml a partir das POSTGRES_*.
    assert {"APP_ENV", "JWT_SECRET_KEY", "LOGIN_HASH_KEY"} <= obrigatorias
    assert obrigatorias - {"DATABASE_URL"} - chaves == set()


def test_app_env_e_obrigatorio(monkeypatch):
    monkeypatch.delenv("APP_ENV")

    with pytest.raises(ValidationError):
        Settings()


def test_database_url_e_obrigatoria(monkeypatch):
    monkeypatch.delenv("DATABASE_URL")

    with pytest.raises(ValidationError):
        Settings()


def test_valor_invalido_e_rejeitado(monkeypatch):
    monkeypatch.setenv("APP_ENV", "homologacao")

    with pytest.raises(ValidationError):
        Settings()


@pytest.mark.parametrize(
    ("jwt", "hash_login", "secure"),
    [
        ("troque-por-um-segredo-longo-e-aleatorio", "y" * 64, "true"),
        ("curto", "y" * 64, "true"),
        ("x" * 64, "troque-por-outro-segredo-longo-e-aleatorio", "true"),
        ("x" * 64, "curto", "true"),
        ("x" * 64, "y" * 64, "false"),
        ("x" * 64, "x" * 64, "true"),  # a mesma chave nos dois
    ],
)
def test_am009_producao_recusa_configuracao_insegura(monkeypatch, jwt, hash_login, secure):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SECRET_KEY", jwt)
    monkeypatch.setenv("LOGIN_HASH_KEY", hash_login)
    monkeypatch.setenv("COOKIE_SECURE", secure)

    with pytest.raises(ValidationError):
        Settings()


def test_am009_producao_aceita_configuracao_segura(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SECRET_KEY", "x" * 64)
    monkeypatch.setenv("LOGIN_HASH_KEY", "y" * 64)
    monkeypatch.setenv("COOKIE_SECURE", "true")

    assert Settings().cookie_secure is True
