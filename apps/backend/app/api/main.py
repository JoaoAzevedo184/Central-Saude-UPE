import logging
from collections.abc import Awaitable, Callable
from http import HTTPStatus
from typing import Any

from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException

from app.api.rotas import health
from app.config import get_settings
from app.dominio.erros import ErroDeDominio
from app.logging import configurar_logging, resumo_do_erro

settings = get_settings()
configurar_logging(settings.log_level)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Central Inteligente de Teleagendamento",
    docs_url="/api/v1/docs",
    redoc_url=None,
    openapi_url="/api/v1/openapi.json",
)

api_v1 = APIRouter(prefix="/api/v1")
api_v1.include_router(health.router)
app.include_router(api_v1)


def problema(
    status: int,
    detail: str | None = None,
    tipo: str = "about:blank",
    headers: dict[str, str] | None = None,
    **extras: Any,
) -> JSONResponse:
    """Resposta de erro em Problem Details (RFC 9457)."""
    corpo: dict[str, Any] = {"type": tipo, "title": HTTPStatus(status).phrase, "status": status}
    if detail:
        corpo["detail"] = detail
    corpo.update(extras)
    return JSONResponse(
        corpo, status_code=status, media_type="application/problem+json", headers=headers
    )


@app.exception_handler(HTTPException)
def _http(_: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail if isinstance(exc.detail, str) else None
    return problema(exc.status_code, detail, headers=exc.headers)


@app.exception_handler(RequestValidationError)
def _validacao(_: Request, exc: RequestValidationError) -> JSONResponse:
    # Só loc/msg/type: `input` pode ecoar dados pessoais e `ctx` pode não ser serializável.
    erros = [{"loc": e["loc"], "msg": e["msg"], "type": e["type"]} for e in exc.errors()]
    return problema(422, "Dados inválidos.", errors=erros)


@app.exception_handler(ErroDeDominio)
def _dominio(_: Request, exc: ErroDeDominio) -> JSONResponse:
    return problema(409, str(exc) or None, tipo=exc.tipo)


@app.middleware("http")
async def _inesperado(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    # Middleware, não exception_handler(Exception): o handler roda no ServerErrorMiddleware,
    # que relança a exceção e o servidor loga o traceback com a mensagem (pode ter dados).
    try:
        return await call_next(request)
    except Exception as exc:
        logger.error(
            "erro inesperado em %s %s: %s", request.method, request.url.path, resumo_do_erro(exc)
        )
        return problema(500)


# Registrado depois do middleware do 500 para ficar por fora dele: assim a resposta 500
# também leva os cabeçalhos CORS e o navegador recebe o Problem Details.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_lista,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", settings.csrf_header_name],
)
