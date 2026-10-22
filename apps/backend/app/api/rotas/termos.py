"""Termo de uso e consentimento vigente, para a tela de cadastro (UC-001)."""

from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, Response
from pydantic import BaseModel

from app.config import get_settings

router = APIRouter(prefix="/termos", tags=["termos"])

PASTA_TERMOS = Path(__file__).resolve().parent.parent.parent / "termos"
CACHE_PUBLICO = "public, max-age=3600"


class TermoSaida(BaseModel):
    versao: str
    texto: str


@lru_cache
def _texto(versao: str) -> str:
    return (PASTA_TERMOS / f"{versao}.md").read_text(encoding="utf-8")


@router.get("/vigente")
def vigente(response: Response) -> TermoSaida:
    """Versão em `TERMO_VERSAO_ATUAL` e o texto de `app/termos/<versao>.md`. Público: o
    cadastro mostra o termo antes de haver sessão. É a versão que `POST /auth/registro` aceita."""
    versao = get_settings().termo_versao_atual
    response.headers["Cache-Control"] = CACHE_PUBLICO
    return TermoSaida(versao=versao, texto=_texto(versao))
