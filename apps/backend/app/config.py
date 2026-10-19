"""Configuração da aplicação, lida das variáveis de ambiente (nomes do .env.example)."""

from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    # Ambiente
    app_env: Literal["development", "test", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # Banco. A aplicação usa só DATABASE_URL; POSTGRES_* servem ao container do Postgres.
    database_url: str
    postgres_db: str = "teleagendamento"
    postgres_user: str = "teleagendamento"
    postgres_password: SecretStr = SecretStr("")
    postgres_port_host: int = 5432

    # API
    api_port_host: int = 8000
    cors_origins: str = ""

    # Autenticação (ADR-003)
    jwt_secret_key: SecretStr
    access_token_ttl_minutos: int = 15
    refresh_token_ttl_dias: int = 7
    cookie_secure: bool = False
    cookie_samesite: Literal["lax", "strict"] = "lax"
    cookie_domain: str = ""
    csrf_header_name: str = "X-CSRF-Token"

    # Tempo (ADR-008)
    timezone_exibicao: str = "America/Recife"

    # E-mail (Worker)
    smtp_host: str = "mailpit"
    smtp_port: int = 1025
    smtp_user: str = ""
    smtp_password: SecretStr = SecretStr("")
    smtp_starttls: bool = False
    smtp_from: str = "Central de Agendamento <nao-responda@exemplo.com>"

    # Worker (ADR-005, ADR-006)
    worker_intervalo_expiracao_s: float = 60
    worker_intervalo_outbox_s: float = 10
    outbox_max_tentativas: int = 5

    # Regras de negócio configuráveis
    proposta_antecedencia_minima_horas: int = 24  # RN-008 / ADR-021
    proposta_janela_minima_horas: int = 12  # ADR-021: menos que isso para responder, não propõe
    matching_automatico: bool = True  # ADR-021

    @property
    def cors_origins_lista(self) -> list[str]:
        return [origem.strip() for origem in self.cors_origins.split(",") if origem.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
