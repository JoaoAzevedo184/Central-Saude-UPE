import logging
from collections.abc import Awaitable, Callable
from http import HTTPStatus
from typing import Any

from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException

from app.api.deps import csrf_valido
from app.api.problemas import MEDIA_TYPE, REF_PROBLEMA, Problema
from app.api.rotas import auth, avisos, equipe, health, solicitacoes, termos, usuarios
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
api_v1.include_router(auth.router)
api_v1.include_router(usuarios.router)
api_v1.include_router(solicitacoes.router)
api_v1.include_router(equipe.router)
api_v1.include_router(avisos.router)
api_v1.include_router(termos.router)
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
    tipo = getattr(exc, "tipo", "about:blank")
    return problema(exc.status_code, detail, tipo=tipo, headers=exc.headers)


@app.exception_handler(RequestValidationError)
def _validacao(_: Request, exc: RequestValidationError) -> JSONResponse:
    # Só loc/msg/type: `input` pode ecoar dados pessoais e `ctx` pode não ser serializável.
    erros = [{"loc": e["loc"], "msg": e["msg"], "type": e["type"]} for e in exc.errors()]
    return problema(422, "Dados inválidos.", errors=erros)


@app.exception_handler(ErroDeDominio)
def _dominio(_: Request, exc: ErroDeDominio) -> JSONResponse:
    return problema(exc.status, str(exc) or None, tipo=exc.tipo, **exc.extras)


METODOS_DE_ESCRITA = frozenset({"POST", "PUT", "PATCH", "DELETE"})
# Só registro e login dispensam CSRF: ainda não há sessão (ADR-003). Negar por padrão.
ROTAS_SEM_CSRF = frozenset({"/api/v1/auth/registro", "/api/v1/auth/login"})
# Respostas com sessão ou dados da conta não ficam em cache.
PREFIXOS_SEM_CACHE = (
    "/api/v1/auth/",
    "/api/v1/me",
    "/api/v1/filas",
    "/api/v1/solicitacoes",
    "/api/v1/equipe/",
    "/api/v1/avisos",
)


@app.middleware("http")
async def _csrf_e_cache(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    path = request.url.path
    if (
        request.method in METODOS_DE_ESCRITA
        and path not in ROTAS_SEM_CSRF
        and not csrf_valido(request)
    ):
        resposta: Response = problema(
            403, "Token CSRF ausente ou inválido.", tipo="/problemas/csrf-invalido"
        )
    else:
        resposta = await call_next(request)
    if path.startswith(PREFIXOS_SEM_CACHE):
        resposta.headers["Cache-Control"] = "no-store"
    return resposta


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


ESQUEMA_CSRF = "csrfToken"


def _openapi() -> dict[str, Any]:
    """OpenAPI com o contrato real de erro e de segurança.

    - Erros (>= 400) são `application/problem+json` com o schema `Problema`; o
      `HTTPValidationError` do FastAPI sai, porque o 422 real também é Problem Details.
    - Rotas de escrita (menos `ROTAS_SEM_CSRF`) exigem o header CSRF, além do cookie.
    """
    if app.openapi_schema:
        return app.openapi_schema
    esquema = get_openapi(
        title=app.title,
        version=app.version,
        openapi_version=app.openapi_version,
        description=app.description,
        routes=app.routes,
    )
    componentes = esquema.setdefault("components", {})
    schemas = componentes.setdefault("schemas", {})
    for nome in ("HTTPValidationError", "ValidationError"):
        schemas.pop(nome, None)
    problema = Problema.model_json_schema(ref_template="#/components/schemas/{model}")
    schemas.update(problema.pop("$defs", {}))
    schemas["Problema"] = problema
    componentes.setdefault("securitySchemes", {})[ESQUEMA_CSRF] = {
        "type": "apiKey",
        "in": "header",
        "name": settings.csrf_header_name,
        "description": "Double-submit (ADR-003): o mesmo valor do cookie `csrf_token`.",
    }
    for caminho, operacoes in esquema["paths"].items():
        for metodo, operacao in operacoes.items():
            for status, resposta in operacao["responses"].items():
                if int(status) >= 400:
                    resposta["content"] = {MEDIA_TYPE: {"schema": REF_PROBLEMA}}
            if metodo.upper() in METODOS_DE_ESCRITA and caminho not in ROTAS_SEM_CSRF:
                exigencias = operacao.get("security") or [{}]
                operacao["security"] = [{**e, ESQUEMA_CSRF: []} for e in exigencias]
    app.openapi_schema = esquema
    return esquema


app.openapi = _openapi  # type: ignore[method-assign]

# Registrado depois do middleware do 500 para ficar por fora dele: assim a resposta 500
# também leva os cabeçalhos CORS e o navegador recebe o Problem Details.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_lista,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", settings.csrf_header_name],
)
