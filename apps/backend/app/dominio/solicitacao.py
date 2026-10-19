"""Solicitação e sua linha do tempo (ADR-026, ADR-007)."""

from dataclasses import dataclass, replace
from datetime import datetime
from uuid import UUID

from app.dominio.erros import TransicaoInvalida


@dataclass(frozen=True)
class Solicitacao:
    id: UUID
    status: str
    classificacao_risco: str | None
    nota: int
    data_entrada_fila: datetime | None


@dataclass(frozen=True)
class EventoHistorico:
    """Linha de `historico_solicitacao`. Nunca carrega posição nem tamanho da fila."""

    tipo: str
    status_anterior: str | None
    status_novo: str | None
    motivo: str | None
    visivel_paciente: bool
    ocorrido_em: datetime


# Motivo da volta para a fila → (status de origem exigido, texto para o paciente).
# Texto fixo: o paciente recebe o motivo, nunca a posição (ADR-007, ADR-026).
MOTIVOS_REENTRADA = {
    "PROPOSTA_EXPIRADA": (
        "EM_PROPOSTA",
        "Você não confirmou a vaga no prazo. Sua solicitação voltou para a fila.",
    ),
    "FALTOU": (
        "AGENDADA",
        "Você não compareceu à consulta. Sua solicitação voltou para a fila.",
    ),
}


def reentrar_no_fim_da_fila(
    solicitacao: Solicitacao, agora: datetime, motivo: str
) -> tuple[Solicitacao, EventoHistorico]:
    """Devolve a solicitação ao fim da fila (ADR-026): `data_entrada_fila = agora`.

    `motivo` é uma chave de `MOTIVOS_REENTRADA`. Estado de origem diferente do exigido
    pelo motivo levanta `TransicaoInvalida`.
    """
    if motivo not in MOTIVOS_REENTRADA:
        raise ValueError(f"motivo de reentrada desconhecido: {motivo!r}")
    origem, texto = MOTIVOS_REENTRADA[motivo]
    if solicitacao.status != origem:
        raise TransicaoInvalida("A solicitação não está em um estado que permita voltar à fila.")

    nova = replace(solicitacao, status="NA_FILA", data_entrada_fila=agora)
    evento = EventoHistorico(
        tipo="REENTROU_NA_FILA",
        status_anterior=solicitacao.status,
        status_novo="NA_FILA",
        motivo=texto,
        visivel_paciente=True,
        ocorrido_em=agora,
    )
    return nova, evento
