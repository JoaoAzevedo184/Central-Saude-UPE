"""Evento da outbox → avisos ao paciente (ADR-006). Ponto único do mapeamento e das esperas."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.dominio.notificacoes.textos import (
    ASSUNTO_EMAIL,
    CORPO_EMAIL,
    EFEITO_AGUARDANDO_NOVA_VAGA,
    SEM_DATA,
    TEXTOS,
)

# Todo tipo que o código grava em `outbox.tipo_evento`. Um teste confere o código contra
# esta lista, e esta lista contra `TEXTOS`: tipo novo sem aviso definido falha na CI.
TIPOS_EVENTO_OUTBOX = frozenset(
    {
        "SOLICITACAO_CRIADA",
        "SOLICITACAO_NA_FILA",
        "PROPOSTA_ENVIADA",
        "AGENDAMENTO_CONFIRMADO",
        "PROPOSTA_RECUSADA",
        "PROPOSTA_EXPIRADA",
        "AGENDAMENTO_CANCELADO",
        "SOLICITACAO_CANCELADA",
        "FALTA_REGISTRADA",
        "ATENDIMENTO_REGISTRADO",
    }
)
# O lembrete não vem da outbox: é criado pelo job `enviar_lembretes`.
TIPO_LEMBRETE = "LEMBRETE"
# Valores de `notificacao.tipo`, em ordem estável para o contrato da API.
TIPOS_AVISO = (*sorted(TIPOS_EVENTO_OUTBOX), TIPO_LEMBRETE)

# Espera antes da tentativa seguinte: 1, 5, 15 e depois 60 minutos.
ESPERAS = (timedelta(minutes=1), timedelta(minutes=5), timedelta(minutes=15), timedelta(hours=1))


class TipoDeAvisoDesconhecido(ValueError):
    pass


@dataclass(frozen=True)
class Contexto:
    """O que o aviso pode citar. Datas com fuso; unidade e profissional só vão para o site."""

    inicio: datetime | None = None  # início da vaga
    expira_em: datetime | None = None  # prazo da proposta
    unidade: str | None = None
    profissional: str | None = None


@dataclass(frozen=True)
class Aviso:
    canal: str  # IN_APP ou EMAIL
    titulo: str
    corpo: str


def montar_avisos(
    tipo: str, contexto: Contexto, *, com_email: bool, link: str, fuso: ZoneInfo
) -> list[Aviso]:
    """Aviso no site sempre; e-mail se o tipo prevê e `com_email` (quem chama decide pelo
    cadastro e, no lembrete, pelo consentimento `LEMBRETE_EMAIL`)."""
    if tipo not in TEXTOS:
        raise TipoDeAvisoDesconhecido(tipo)
    titulo, corpo, frase_email = TEXTOS[tipo]

    def quando(d: datetime | None, formato: str) -> str:
        return d.astimezone(fuso).strftime(formato) if d else SEM_DATA

    campos = {
        "inicio": quando(contexto.inicio, "%d/%m às %H:%M"),
        "prazo": quando(contexto.expira_em, "%d/%m às %H:%M"),
        "dia": quando(contexto.inicio, "%d/%m"),
        "efeito": EFEITO_AGUARDANDO_NOVA_VAGA,
        "local": "".join(
            f", {rotulo} {valor}"
            for rotulo, valor in (("na unidade", contexto.unidade), ("com", contexto.profissional))
            if valor
        ),
    }
    avisos = [Aviso("IN_APP", titulo.format(**campos), corpo.format(**campos))]
    if com_email and frase_email:
        corpo_email = CORPO_EMAIL.format(mensagem=frase_email.format(**campos), link=link)
        avisos.append(Aviso("EMAIL", ASSUNTO_EMAIL, corpo_email))
    return avisos


def proxima_tentativa(tentativas: int, maximo: int, agora: datetime) -> datetime | None:
    """Depois da falha número `tentativas` (a partir de 1): quando tentar de novo.
    `None` = chegou ao máximo, o item vai para `FALHOU`."""
    if tentativas >= maximo:
        return None
    return agora + ESPERAS[min(tentativas, len(ESPERAS)) - 1]
