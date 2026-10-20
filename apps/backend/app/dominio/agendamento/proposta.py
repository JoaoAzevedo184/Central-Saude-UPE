"""Proposta de vaga (UC-003, ADR-021: automática, na ordem da fila).

`propor_vaga()` é o ÚNICO lugar que escolhe a quem uma vaga é proposta. A garantia final
contra duas propostas na mesma vaga ou na mesma solicitação são os índices únicos parciais
(RN-001, RN-002); quem chama trata a violação descartando a tentativa.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, time
from uuid import UUID
from zoneinfo import ZoneInfo

from app.dominio.agendamento.prazos import calcular_expira_em
from app.dominio.fila.ordenacao import ordenar_fila
from app.dominio.solicitacao import EventoHistorico, Solicitacao, receber_proposta

# Turno da vaga pela hora local de início (regra nova, business-rules.md):
# antes de 12h é MANHA; a partir de 12h, TARDE. QUALQUER aceita os dois.
MEIO_DIA = time(12)


def turnos_compativeis(vaga_inicio: datetime, fuso: ZoneInfo) -> frozenset[str]:
    """Preferências de turno (`solicitacao.turno_preferido`) que aceitam esta vaga."""
    turno = "MANHA" if vaga_inicio.astimezone(fuso).time() < MEIO_DIA else "TARDE"
    return frozenset({turno, "QUALQUER"})


@dataclass(frozen=True)
class VagaLivre:
    id: UUID
    inicio: datetime
    prazo_confirmacao_horas: int  # da fila (ADR-026)


@dataclass(frozen=True)
class Candidata:
    solicitacao: Solicitacao
    turno_preferido: str
    ja_teve_esta_vaga: bool  # já recebeu esta vaga antes (recusou ou deixou expirar)


@dataclass(frozen=True)
class Proposta:
    solicitacao: Solicitacao  # já em EM_PROPOSTA
    evento: EventoHistorico
    expira_em: datetime


def propor_vaga(
    candidatas: Iterable[Candidata],
    vaga: VagaLivre,
    agora: datetime,
    *,
    antecedencia_minima_horas: int,
    janela_minima_horas: int,
    fuso: ZoneInfo,
) -> Proposta | None:
    """Escolhe a primeira candidata, na ordem de `ordenar_fila()`, que pode receber a vaga.

    Pode receber: está `NA_FILA`, o turno preferido aceita a vaga e nunca recebeu esta mesma
    vaga (a vaga não é reoferecida à mesma solicitação, depois de recusa ou expiração).
    Devolve `None` se ninguém pode, ou se `calcular_expira_em()` não deixa a janela mínima
    (RN-016): nesse caso a vaga fica livre e aparece no painel como "vaga sem proposta".
    """
    expira_em = calcular_expira_em(
        agora,
        vaga.inicio,
        vaga.prazo_confirmacao_horas,
        antecedencia_minima_horas,
        janela_minima_horas=janela_minima_horas,
    )
    if expira_em is None:
        return None
    turnos = turnos_compativeis(vaga.inicio, fuso)
    aptas = {
        c.solicitacao.id: c
        for c in candidatas
        if c.solicitacao.status == "NA_FILA"
        and c.turno_preferido in turnos
        and not c.ja_teve_esta_vaga
    }
    if not aptas:
        return None
    primeira = ordenar_fila(c.solicitacao for c in aptas.values())[0]
    nova, evento = receber_proposta(primeira, agora)
    return Proposta(nova, evento, expira_em)
