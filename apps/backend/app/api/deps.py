from collections.abc import Iterator
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.infra.db import SessionLocal


def get_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session


@dataclass(frozen=True)
class EscopoEquipe:
    """Unidades que a equipe pode ver. `None` = todas as unidades."""

    unidade_ids: frozenset[UUID] | None


def escopo_da_equipe(settings: Annotated[Settings, Depends(get_settings)]) -> EscopoEquipe:
    """Escopo de unidades da equipe (ADR-023). Ponto único de troca do ABERTO-3.

    Toda rota da equipe deve recebê-lo via `Depends(escopo_da_equipe)` e passá-lo às
    consultas. Ainda não há usuário autenticado: a tarefa de autenticação vai injetar o
    usuário aqui, para buscar a lotação quando `ESCOPO_POR_UNIDADE=true`.
    """
    if settings.escopo_por_unidade:
        raise NotImplementedError("escopo por unidade ainda não implementado (ADR-023)")
    return EscopoEquipe(unidade_ids=None)
