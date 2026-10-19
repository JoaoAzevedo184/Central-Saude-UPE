"""Leitura das atribuições da equipe para o escopo por fila (ADR-025)."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dominio.acesso import calcular_escopo
from app.infra.modelos import Fila, Usuario, usuario_fila, usuario_unidade


def carregar_escopo(session: Session, usuario_id: UUID) -> frozenset[UUID]:
    """Filas permitidas ao usuário. Usuário inexistente não vê nada."""
    usuario = session.get(Usuario, usuario_id)
    if usuario is None:
        return frozenset()
    filas = session.scalars(
        select(usuario_fila.c.fila_id).where(usuario_fila.c.usuario_id == usuario_id)
    )
    unidades = session.scalars(
        select(usuario_unidade.c.unidade_id).where(usuario_unidade.c.usuario_id == usuario_id)
    )
    unidade_da_fila = dict(session.execute(select(Fila.id, Fila.unidade_id)).all())
    return calcular_escopo(
        usuario.papel, usuario.situacao, frozenset(filas), frozenset(unidades), unidade_da_fila
    )
