"""Ordenação da fila (RN-006, ADR-024).

Este é o ÚNICO lugar do sistema que ordena a fila. A ordem é:
1. classificação de risco: VERMELHO, AMARELO, VERDE;
2. nota do protocolo da fila, decrescente (`calcular_nota`);
3. hora de chegada na fila (`data_entrada_fila`), crescente;
4. `id`, só para a ordem ser sempre determinística.

A posição resultante nunca é gravada nem mostrada ao paciente (ADR-007).
"""

from collections.abc import Iterable

from app.dominio.solicitacao import Solicitacao

PESO_RISCO = {"VERMELHO": 0, "AMARELO": 1, "VERDE": 2}


def _chave(s: Solicitacao) -> tuple:
    if s.classificacao_risco not in PESO_RISCO:
        raise ValueError(f"classificação de risco desconhecida: {s.classificacao_risco!r}")
    if s.data_entrada_fila is None:
        raise ValueError(f"solicitação {s.id} sem data de entrada na fila")
    return (PESO_RISCO[s.classificacao_risco], -s.nota, s.data_entrada_fila, s.id)


def ordenar_fila(solicitacoes: Iterable[Solicitacao]) -> list[Solicitacao]:
    """Devolve as solicitações na ordem da fila."""
    return sorted(solicitacoes, key=_chave)
