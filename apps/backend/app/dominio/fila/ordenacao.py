"""Ordenação da fila (RN-006, ADR-022).

Este é o ÚNICO lugar do sistema que ordena a fila. As regras são simuladas (ADR-011):
os critérios oficiais são da instituição e chegam pela tabela `regra_prioridade`.
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from uuid import UUID

_PESO_RISCO = {"VERMELHO": 0, "AMARELO": 1, "VERDE": 2, "AZUL": 3}


@dataclass(frozen=True)
class SolicitacaoNaFila:
    id: UUID
    classificacao_risco: str
    prioridade_legal: str | None
    data_pedido: date
    criada_em: datetime


@dataclass(frozen=True)
class RegraPrioridade:
    criterio: str
    ordem: int
    ativa: bool = True


def _risco(s: SolicitacaoNaFila) -> int:
    try:
        return _PESO_RISCO[s.classificacao_risco]
    except KeyError:
        raise ValueError(
            f"classificação de risco desconhecida: {s.classificacao_risco!r}"
        ) from None


_CHAVES: dict[str, Callable[[SolicitacaoNaFila], Any]] = {
    "CLASSIFICACAO_RISCO": _risco,
    "PRIORIDADE_LEGAL": lambda s: s.prioridade_legal is None,  # com prioridade primeiro
    "DATA_PEDIDO": lambda s: s.data_pedido,  # mais antigo primeiro
}


def ordenar_fila(
    solicitacoes: Iterable[SolicitacaoNaFila], regras: Iterable[RegraPrioridade]
) -> list[SolicitacaoNaFila]:
    """Devolve as solicitações na ordem da fila.

    Aplica as regras ativas em ordem crescente de `ordem`. Desempate final por `criada_em`
    e depois por `id`, para a ordem ser sempre determinística. Critério desconhecido
    levanta `ValueError`.
    """
    chaves = []
    for regra in sorted((r for r in regras if r.ativa), key=lambda r: r.ordem):
        if regra.criterio not in _CHAVES:
            raise ValueError(f"critério de prioridade desconhecido: {regra.criterio!r}")
        chaves.append(_CHAVES[regra.criterio])
    return sorted(solicitacoes, key=lambda s: (*(c(s) for c in chaves), s.criada_em, s.id))
