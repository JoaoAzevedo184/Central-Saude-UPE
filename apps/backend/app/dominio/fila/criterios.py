"""Protocolo da fila: critérios com peso e nota da solicitação (ADR-024).

Os critérios e pesos são simulados (ADR-011); os oficiais são da instituição.

Formato de `parametros` por tipo (o valor respondido vai em `resposta_criterio.valor`):
- SIM_NAO: sem parâmetros. Valor `bool`; "sim" vale `peso`, "não" vale 0.
- NUMERO: `{"faixas": [{"min": 0, "max": 2, "fator": 0}, {"min": 3, "fator": 1}]}`.
  Valor numérico; vale `peso * fator` da primeira faixa que o contém (`min` e `max`
  inclusivos e opcionais). Fora de todas as faixas vale 0.
- OPCAO: `{"opcoes": {"CODIGO": fator, ...}}`. Valor é um dos códigos; vale `peso * fator`.
  Código desconhecido é erro.

`fator` é sempre inteiro >= 0; parâmetro malformado levanta `ValueError`.
"""

from collections.abc import Hashable, Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from app.dominio.erros import EntradaInvalida

# Quem responde cada origem de critério (ADR-024). O paciente nunca responde pela regulação.
ORIGENS_DO_PACIENTE = frozenset({"PACIENTE"})
ORIGENS_DA_EQUIPE = frozenset({"REGULACAO", "EQUIPE"})


@dataclass(frozen=True)
class Criterio:
    codigo: str
    tipo: str
    peso: int
    parametros: Mapping[str, Any] = field(default_factory=dict)
    origem: str = "PACIENTE"


def _fator(criterio: Criterio, fator: Any) -> int:
    if isinstance(fator, bool) or not isinstance(fator, int) or fator < 0:
        raise ValueError(f"critério {criterio.codigo}: fator deve ser inteiro >= 0")
    return fator


def calcular_pontos(criterio: Criterio, valor: Any) -> int:
    """Pontos de uma resposta. Valor do tipo errado levanta `ValueError`."""
    if criterio.tipo == "SIM_NAO":
        if not isinstance(valor, bool):
            raise ValueError(f"critério {criterio.codigo}: esperado sim/não")
        return criterio.peso if valor else 0

    if criterio.tipo == "NUMERO":
        if isinstance(valor, bool) or not isinstance(valor, int | float):
            raise ValueError(f"critério {criterio.codigo}: esperado número")
        for faixa in criterio.parametros.get("faixas", []):
            if faixa.get("min", valor) <= valor <= faixa.get("max", valor):
                return criterio.peso * _fator(criterio, faixa.get("fator"))
        return 0

    if criterio.tipo == "OPCAO":
        opcoes = criterio.parametros.get("opcoes", {})
        if not isinstance(valor, str) or valor not in opcoes:
            raise ValueError(f"critério {criterio.codigo}: opção desconhecida")
        return criterio.peso * _fator(criterio, opcoes[valor])

    raise ValueError(f"tipo de critério desconhecido: {criterio.tipo!r}")


def calcular_nota(respostas: Iterable[tuple[Criterio, Any]]) -> int:
    """Nota da solicitação: soma dos pontos das respostas `(criterio, valor)`."""
    return sum(calcular_pontos(criterio, valor) for criterio, valor in respostas)


def pontuar_respostas[K: Hashable](
    criterios: Mapping[K, Criterio], respostas: Iterable[tuple[K, Any]], origens: frozenset[str]
) -> dict[K, int]:
    """Pontos de cada resposta `(criterio_id, valor)`, validando quem responde.

    `criterios` são os critérios ativos da fila da solicitação; `origens`, as que este ator
    pode responder. Critério de outra fila ou de outra origem, resposta repetida ou valor
    inválido levantam `EntradaInvalida` (422).
    """
    pontos: dict[K, int] = {}
    for criterio_id, valor in respostas:
        criterio = criterios.get(criterio_id)
        if criterio is None or criterio.origem not in origens:
            raise EntradaInvalida("Critério inexistente nesta fila ou que você não responde.")
        if criterio_id in pontos:
            raise EntradaInvalida("Critério respondido mais de uma vez.")
        try:
            pontos[criterio_id] = calcular_pontos(criterio, valor)
        except ValueError:
            raise EntradaInvalida("Resposta inválida para o critério.") from None
    return pontos
