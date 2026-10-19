from collections.abc import Iterator
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.infra.acesso import carregar_escopo
from app.infra.db import SessionLocal


def get_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session


def usuario_da_sessao() -> UUID:
    """ID do usuário autenticado. A tarefa de autenticação (ADR-003) substitui este corpo.

    Até lá, nenhuma rota que dependa de sessão autentica.
    """
    raise HTTPException(status_code=401, detail="Não autenticado.")


def escopo_da_equipe(
    usuario_id: Annotated[UUID, Depends(usuario_da_sessao)],
    session: Annotated[Session, Depends(get_session)],
) -> frozenset[UUID]:
    """Filas que o usuário da equipe pode ver e operar (ADR-025).

    Toda rota da equipe deve recebê-lo via `Depends(escopo_da_equipe)` e filtrar as consultas
    por `fila_id IN escopo` dentro da query. A regra está em `dominio.acesso.calcular_escopo`.
    """
    return carregar_escopo(session, usuario_id)
