import pytest
from pydantic import ValidationError

from app.config import Settings


def test_le_variaveis_do_ambiente(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173, http://localhost:3000")
    monkeypatch.setenv("MATCHING_AUTOMATICO", "false")
    monkeypatch.setenv("ESCOPO_POR_UNIDADE", "true")
    monkeypatch.setenv("WORKER_INTERVALO_OUTBOX_S", "2")

    settings = Settings()

    assert settings.cors_origins_lista == ["http://localhost:5173", "http://localhost:3000"]
    assert settings.matching_automatico is False
    assert settings.escopo_por_unidade is True
    assert settings.worker_intervalo_outbox_s == 2


def test_padroes_seguem_as_decisoes_provisorias(monkeypatch):
    monkeypatch.delenv("MATCHING_AUTOMATICO", raising=False)
    monkeypatch.delenv("ESCOPO_POR_UNIDADE", raising=False)

    settings = Settings()

    assert settings.matching_automatico is True  # ADR-021
    assert settings.escopo_por_unidade is False  # ADR-023


def test_database_url_e_obrigatoria(monkeypatch):
    monkeypatch.delenv("DATABASE_URL")

    with pytest.raises(ValidationError):
        Settings()


def test_valor_invalido_e_rejeitado(monkeypatch):
    monkeypatch.setenv("APP_ENV", "homologacao")

    with pytest.raises(ValidationError):
        Settings()
