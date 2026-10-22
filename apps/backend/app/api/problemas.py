"""Problem Details (RFC 9457) no OpenAPI: schema `Problema` e as respostas de erro por rota."""

from http import HTTPStatus
from typing import Any

from pydantic import BaseModel

MEDIA_TYPE = "application/problem+json"
REF_PROBLEMA = {"$ref": "#/components/schemas/Problema"}

# Respostas que quase toda rota autenticada pode dar.
NAO_AUTENTICADO = (401, "nao-autenticado")
SEM_PERMISSAO = (403, "sem-permissao")
CSRF = (403, "csrf-invalido")


class ErroDeCampo(BaseModel):
    loc: list[str | int]
    msg: str
    type: str


class Problema(BaseModel):
    """Corpo de toda resposta de erro (`Content-Type: application/problem+json`)."""

    type: str
    title: str
    status: int
    detail: str | None = None
    instance: str | None = None
    errors: list[ErroDeCampo] | None = None  # só no 422


def erros(*itens: int | tuple[int, *tuple[str, ...]]) -> dict[int | str, dict[str, Any]]:
    """`responses=` de uma rota. Cada item é um status ou `(status, "tipo", ...)`, em que
    `tipo` vem depois de `/problemas/`. Itens do mesmo status se juntam."""
    por_status: dict[int, list[str]] = {}
    for item in itens:
        status, *tipos = (item,) if isinstance(item, int) else item
        por_status.setdefault(status, []).extend(t for t in tipos if t not in por_status[status])
    return {
        status: {
            "description": HTTPStatus(status).phrase
            + (": " + ", ".join(f"`/problemas/{t}`" for t in tipos) if tipos else ""),
            "model": Problema,
        }
        for status, tipos in por_status.items()
    }
