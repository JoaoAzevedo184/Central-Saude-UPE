import hmac
import ipaddress
from collections.abc import Callable, Iterator
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, Security
from fastapi.security import APIKeyCookie
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.dominio.acesso import pode_autenticar
from app.dominio.relogio import Relogio
from app.infra.acesso import carregar_escopo
from app.infra.autenticacao import familia_ativa, ler_access_token
from app.infra.db import SessionLocal
from app.infra.modelos import Paciente, Usuario
from app.infra.relogio import RelogioReal

COOKIE_ACCESS = "access_token"
COOKIE_REFRESH = "refresh_token"
COOKIE_CSRF = "csrf_token"

# Só documentação: declaram os cookies no OpenAPI. `auto_error=False` mantém o comportamento
# (a leitura e o 401 continuam em `usuario_da_sessao` e `/auth/refresh`).
esquema_acesso = APIKeyCookie(
    name=COOKIE_ACCESS,
    scheme_name="cookieSessao",
    auto_error=False,
    description="Access token em cookie httpOnly, emitido por login, registro e refresh.",
)
esquema_refresh = APIKeyCookie(
    name=COOKIE_REFRESH,
    scheme_name="cookieRefresh",
    auto_error=False,
    description="Refresh token em cookie httpOnly, com path /api/v1/auth.",
)


class Problema(HTTPException):
    """HTTPException com o `type` do Problem Details (RFC 9457)."""

    def __init__(
        self, status: int, tipo: str, detail: str, headers: dict[str, str] | None = None
    ) -> None:
        super().__init__(status_code=status, detail=detail, headers=headers)
        self.tipo = tipo


def get_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session


def get_relogio() -> Relogio:
    return RelogioReal()


def ip_do_cliente(request: Request) -> str | None:
    """IP de quem chamou. Atrás do nginx, o uvicorn só confia no X-Forwarded-For vindo do IP
    fixo do nginx (`--forwarded-allow-ips` no docker-compose.yml). Valor não-IP vira None."""
    host = request.client.host if request.client else None
    try:
        return str(ipaddress.ip_address(host)) if host else None
    except ValueError:
        return None


def csrf_valido(request: Request) -> bool:
    """Double-submit: o header precisa ser igual ao cookie `csrf_token` (ADR-003)."""
    cookie = request.cookies.get(COOKIE_CSRF, "")
    header = request.headers.get(get_settings().csrf_header_name, "")
    return bool(cookie) and hmac.compare_digest(cookie.encode(), header.encode())


def usuario_da_sessao_sem_troca(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    relogio: Annotated[Relogio, Depends(get_relogio)],
    _cookie: Annotated[str | None, Security(esquema_acesso)] = None,
) -> Usuario:
    """Usuário do access token, carregado do banco a cada requisição, sem exigir a troca de senha.

    Só `/me` e `/auth/trocar-senha` o usam direto; o resto passa por `usuario_da_sessao`.
    Suspenso (ADR-028) ou família de sessão revogada (logout, reuso do refresh) não passam:
    o acesso cai na hora, sem esperar o access token vencer.
    """
    token = request.cookies.get(COOKIE_ACCESS)
    chave = get_settings().jwt_secret_key.get_secret_value()
    lido = ler_access_token(token, relogio.agora(), chave) if token else None
    usuario = session.get(Usuario, lido[0]) if lido else None
    if (
        usuario is None
        or not pode_autenticar(usuario.situacao)
        or not familia_ativa(session, lido[1])
    ):
        raise Problema(401, "/problemas/nao-autenticado", "Sessão inválida ou expirada.")
    return usuario


def usuario_da_sessao(
    usuario: Annotated[Usuario, Depends(usuario_da_sessao_sem_troca)],
) -> Usuario:
    """Usuário da sessão. Com senha temporária (criada ou redefinida pelo admin), toda rota
    que não seja a troca de senha, `/me`, logout ou refresh responde 403: negar por padrão."""
    if usuario.senha_temporaria:
        raise Problema(
            403,
            "/problemas/troca-de-senha-obrigatoria",
            "Troque a senha temporária para continuar.",
        )
    return usuario


def exige_papel(*papeis: str) -> Callable[[Usuario], Usuario]:
    """Dependência que só deixa passar os papéis indicados (403 para os demais)."""

    def dependencia(usuario: Annotated[Usuario, Depends(usuario_da_sessao)]) -> Usuario:
        if usuario.papel not in papeis:
            raise Problema(403, "/problemas/sem-permissao", "Sem permissão para esta ação.")
        return usuario

    return dependencia


def escopo_da_equipe(
    usuario: Annotated[Usuario, Depends(usuario_da_sessao)],
    session: Annotated[Session, Depends(get_session)],
) -> frozenset[UUID]:
    """Filas que o usuário da equipe pode ver e operar (ADR-025).

    Toda rota da equipe deve recebê-lo via `Depends(escopo_da_equipe)` e filtrar as consultas
    por `fila_id IN escopo` dentro da query. A regra está em `dominio.acesso.calcular_escopo`.
    """
    return carregar_escopo(session, usuario.id)


def paciente_da_sessao(
    usuario: Annotated[Usuario, Depends(exige_papel("PACIENTE"))],
    session: Annotated[Session, Depends(get_session)],
) -> Paciente:
    """Paciente do usuário da sessão. Toda consulta do paciente filtra por `paciente.id`
    dentro da query; recurso de outro paciente responde 404 (AM-001)."""
    paciente = session.scalar(select(Paciente).where(Paciente.usuario_id == usuario.id))
    if paciente is None:
        raise Problema(403, "/problemas/sem-permissao", "Sem permissão para esta ação.")
    return paciente
