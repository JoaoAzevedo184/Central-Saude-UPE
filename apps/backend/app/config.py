"""Configuração da aplicação, lida das variáveis de ambiente (nomes do .env.example)."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    # Ambiente
    # Obrigatório: sem padrão, um ambiente esquecido não sobe como development.
    app_env: Literal["development", "test", "production"]
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
    login_max_tentativas: int = 5  # AM-004: falhas por IP ou identificador dentro da janela
    login_janela_min: int = 15
    registro_max_tentativas: int = 20  # AM-004: registros por IP na mesma janela (recepção)
    # HMAC do CPF/e-mail em tentativa_login: sem a chave, o hash não é revertido por força bruta.
    login_hash_key: SecretStr
    refresh_tolerancia_s: int = 10  # ADR-003: duas abas renovando juntas não contam como roubo
    termo_versao_atual: str = Field(
        "1.0", pattern=r"^\d+(\.\d+)*$"
    )  # UC-001: só aceita o aceite da versão vigente

    # Tempo (ADR-008)
    timezone_exibicao: str = "America/Recife"

    # E-mail (Worker)
    smtp_host: str = "mailpit"
    smtp_port: int = 1025
    smtp_user: str = ""
    smtp_password: SecretStr = SecretStr("")
    smtp_starttls: bool = False
    smtp_from: str = "Central de Agendamento <nao-responda@exemplo.com>"
    smtp_timeout_s: float = 10  # conexão e cada operação: SMTP lento não trava o Worker
    # Link dos e-mails (AM-008, AM-015): sempre o endereço oficial da Central.
    app_url_publica: str = "http://localhost:8000"

    # Worker (ADR-005, ADR-006)
    worker_intervalo_expiracao_s: float = 60
    worker_intervalo_outbox_s: float = 10
    outbox_max_tentativas: int = 5
    worker_intervalo_retencao_s: float = 3600
    worker_intervalo_matching_s: float = 60  # ADR-021: varredura das vagas livres
    worker_intervalo_vagas_s: float = 3600  # geração das vagas a partir das agendas
    vagas_horizonte_dias: int = 30  # quantos dias à frente as vagas são geradas
    worker_intervalo_email_s: float = 15  # envio dos e-mails pendentes e novas tentativas
    worker_intervalo_lembrete_s: float = 3600  # RF-024: lembretes antes da consulta
    worker_lote_maximo: int = Field(100, ge=1)  # itens por rodada; o resto fica para a próxima

    # Regras de negócio configuráveis
    proposta_antecedencia_minima_horas: int = 24  # RN-008 / ADR-021
    proposta_janela_minima_horas: int = 12  # ADR-021: menos que isso para responder, não propõe
    matching_automatico: bool = True  # ADR-021
    # UC-005 (proposta): recusas que mantêm a posição; a seguinte volta para o fim da fila.
    recusas_mantendo_posicao: int = 1
    lembrete_antecedencia_horas: int = 24  # RF-024: lembrete para consultas nas próximas N horas

    @model_validator(mode="after")
    def _producao_segura(self) -> "Settings":
        """AM-009: em produção, sem o segredo de exemplo, sem segredo curto e sem cookie em HTTP."""
        if self.app_env == "production":
            for nome in ("jwt_secret_key", "login_hash_key"):
                segredo = getattr(self, nome).get_secret_value()
                # "troque-" é o prefixo dos valores de exemplo do .env.example.
                if len(segredo) < 32 or segredo.startswith("troque-"):
                    raise ValueError(
                        f"{nome.upper()} de produção precisa de 32+ caracteres aleatórios"
                    )
            if self.jwt_secret_key == self.login_hash_key:
                raise ValueError("LOGIN_HASH_KEY precisa ser diferente de JWT_SECRET_KEY")
            if not self.cookie_secure:
                raise ValueError("COOKIE_SECURE precisa ser true em produção")
            # AM-015: o link dos e-mails leva ao endereço oficial, com TLS.
            url = self.app_url_publica
            if not url.startswith("https://") or "localhost" in url:
                raise ValueError("APP_URL_PUBLICA de produção precisa ser https:// e público")
        return self

    @property
    def cors_origins_lista(self) -> list[str]:
        return [origem.strip() for origem in self.cors_origins.split(",") if origem.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
