"""Suspender e reativar contas da equipe (ADR-028). Só ADMIN."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import exige_papel, get_relogio, get_session, ip_do_cliente
from app.api.problemas import CSRF, NAO_AUTENTICADO, SEM_PERMISSAO, erros
from app.dominio.acesso import verificar_reativacao, verificar_suspensao
from app.dominio.relogio import Relogio
from app.infra.autenticacao import revogar_sessoes
from app.infra.modelos import Auditoria, SessaoRefresh, Usuario

router = APIRouter(prefix="/usuarios", tags=["usuarios"])

AdminDep = Annotated[Usuario, Depends(exige_papel("ADMIN"))]
SessionDep = Annotated[Session, Depends(get_session)]
RelogioDep = Annotated[Relogio, Depends(get_relogio)]


class SuspensaoEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    motivo: str = Field(min_length=3, max_length=500)


def _travar_alvo(session: Session, usuario_id: UUID) -> Usuario:
    alvo = session.scalar(
        select(Usuario)
        .where(Usuario.id == usuario_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if alvo is None:
        raise HTTPException(404, "Usuário não encontrado.")
    return alvo


@router.post(
    "/{usuario_id}/suspender",
    status_code=204,
    responses=erros(
        NAO_AUTENTICADO,
        SEM_PERMISSAO,
        CSRF,
        404,
        (409, "transicao-invalida", "operacao-nao-permitida"),
        422,
    ),
)
def suspender(
    usuario_id: UUID,
    dados: SuspensaoEntrada,
    request: Request,
    admin: AdminDep,
    session: SessionDep,
    relogio: RelogioDep,
) -> Response:
    """Grava a suspensão e revoga todas as sessões do usuário. O access token que ainda não
    venceu deixa de valer na próxima requisição, porque `usuario_da_sessao` relê a situação."""
    # Trava os ADMIN ativos antes de contar, sempre na mesma ordem: dois admins suspendendo
    # um ao outro ao mesmo tempo não podem deixar a central sem nenhum.
    admins_ativos = session.scalars(
        select(Usuario.id)
        .where(Usuario.papel == "ADMIN", Usuario.situacao == "ATIVO")
        .order_by(Usuario.id)
        .with_for_update()
    ).all()
    alvo = _travar_alvo(session, usuario_id)
    verificar_suspensao(admin.id, alvo.id, alvo.papel, alvo.situacao, len(admins_ativos))

    agora = relogio.agora()
    alvo.situacao = "SUSPENSO"
    alvo.suspenso_em = agora
    alvo.motivo_suspensao = dados.motivo
    revogar_sessoes(session, agora, SessaoRefresh.usuario_id == alvo.id)
    session.add(
        Auditoria(
            ator_usuario_id=admin.id,
            acao="SUSPENDER",
            entidade="usuario",
            entidade_id=alvo.id,
            dados_antes={"situacao": "ATIVO"},
            dados_depois={"situacao": "SUSPENSO"},
            ip=ip_do_cliente(request),
        )
    )
    session.commit()
    return Response(status_code=204)


@router.post(
    "/{usuario_id}/reativar",
    status_code=204,
    responses=erros(NAO_AUTENTICADO, SEM_PERMISSAO, CSRF, 404, (409, "transicao-invalida"), 422),
)
def reativar(usuario_id: UUID, request: Request, admin: AdminDep, session: SessionDep) -> Response:
    """Volta a ATIVO. `suspenso_em` e `motivo_suspensao` ficam como registro (ADR-028)."""
    alvo = _travar_alvo(session, usuario_id)
    verificar_reativacao(alvo.situacao)
    alvo.situacao = "ATIVO"
    session.add(
        Auditoria(
            ator_usuario_id=admin.id,
            acao="REATIVAR",
            entidade="usuario",
            entidade_id=alvo.id,
            dados_antes={"situacao": "SUSPENSO"},
            dados_depois={"situacao": "ATIVO"},
            ip=ip_do_cliente(request),
        )
    )
    session.commit()
    return Response(status_code=204)
