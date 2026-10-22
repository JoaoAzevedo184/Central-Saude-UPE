"""Convenção das listas paginadas: `?limit=&offset=` na entrada, `{total, itens}` na saída."""

from typing import Annotated

from fastapi import Query
from pydantic import BaseModel

Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]


class Pagina[T](BaseModel):
    """`total` conta todos os itens do filtro, antes de `limit` e `offset`."""

    total: int
    itens: list[T]
