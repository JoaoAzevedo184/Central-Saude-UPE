"""Acesso da equipe: escopo por fila (ADR-025) e usuário suspenso (ADR-028)."""

from collections.abc import Mapping
from uuid import UUID


def pode_autenticar(situacao: str) -> bool:
    """Usuário SUSPENSO não faz login nem renova o refresh token (ADR-028).

    O login deve responder com a mesma mensagem genérica de credenciais inválidas.
    """
    return situacao == "ATIVO"


def calcular_escopo(
    papel: str,
    situacao: str,
    filas_atribuidas: frozenset[UUID],
    unidades_atribuidas: frozenset[UUID],
    unidade_da_fila: Mapping[UUID, UUID],
) -> frozenset[UUID]:
    """Filas que o usuário da equipe pode ver e operar. Ponto único de troca do escopo.

    - ATENDENTE: só as filas em `usuario_fila`; sem atribuição, nenhuma.
    - GESTOR: as filas das unidades em `usuario_unidade`; sem unidade, a central inteira.
    - ADMIN: todas.
    Suspenso ou outro papel: nenhuma (falha fechada).

    `unidade_da_fila` mapeia cada fila existente para a sua unidade.
    """
    if not pode_autenticar(situacao):
        return frozenset()
    if papel == "ADMIN" or (papel == "GESTOR" and not unidades_atribuidas):
        return frozenset(unidade_da_fila)
    if papel == "GESTOR":
        return frozenset(f for f, u in unidade_da_fila.items() if u in unidades_atribuidas)
    if papel == "ATENDENTE":
        return filas_atribuidas & frozenset(unidade_da_fila)
    return frozenset()
