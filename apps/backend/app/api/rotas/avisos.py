"""Avisos do site (RF-019). Qualquer usuário autenticado, só os próprios.

O filtro por `usuario_id` da sessão fica dentro da query: aviso de outro usuário → 404.
As respostas não trazem o canal EMAIL nem o status de envio.
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.api.deps import get_relogio, get_session, usuario_da_sessao
from app.api.paginacao import Limit, Offset, Pagina
from app.api.problemas import CSRF, NAO_AUTENTICADO, erros
from app.api.tipos import TipoAviso
from app.config import get_settings
from app.dominio.relogio import Relogio
from app.infra.modelos import Notificacao, Usuario

router = APIRouter(prefix="/avisos", tags=["avisos"])

UsuarioDep = Annotated[Usuario, Depends(usuario_da_sessao)]
SessionDep = Annotated[Session, Depends(get_session)]
RelogioDep = Annotated[Relogio, Depends(get_relogio)]
LEITURA = (NAO_AUTENTICADO, 422)
ESCRITA = (*LEITURA, CSRF)


class AvisoSaida(BaseModel):
    id: UUID
    tipo: TipoAviso
    titulo: str
    corpo: str
    solicitacao_id: UUID | None
    criado_em: datetime
    lido_em: datetime | None


class PaginaAvisos(Pagina[AvisoSaida]):
    pass


class ContagemSaida(BaseModel):
    nao_lidos: int


def _meus(usuario: Usuario):
    return (Notificacao.usuario_id == usuario.id, Notificacao.canal == "IN_APP")


@router.get("", responses=erros(*LEITURA))
def listar(
    usuario: UsuarioDep,
    session: SessionDep,
    somente_nao_lidos: bool = False,
    limit: Limit = 50,
    offset: Offset = 0,
) -> PaginaAvisos:
    """Mais recentes primeiro."""
    consulta = select(Notificacao).where(*_meus(usuario))
    if somente_nao_lidos:
        consulta = consulta.where(Notificacao.lida_em.is_(None))
    fuso = ZoneInfo(get_settings().timezone_exibicao)
    total = session.scalar(select(func.count()).select_from(consulta.subquery()))
    itens = [
        AvisoSaida(
            id=n.id,
            tipo=n.tipo,
            titulo=n.titulo,
            corpo=n.corpo,
            solicitacao_id=n.solicitacao_id,
            criado_em=n.criada_em.astimezone(fuso),
            lido_em=n.lida_em.astimezone(fuso) if n.lida_em else None,
        )
        for n in session.scalars(
            consulta.order_by(Notificacao.criada_em.desc(), Notificacao.id.desc())
            .limit(limit)
            .offset(offset)
        )
    ]
    return PaginaAvisos(total=total or 0, itens=itens)


@router.get("/contagem", responses=erros(NAO_AUTENTICADO))
def contagem(usuario: UsuarioDep, session: SessionDep) -> ContagemSaida:
    """Para o sino do menu."""
    total = session.scalar(
        select(func.count())
        .select_from(Notificacao)
        .where(*_meus(usuario), Notificacao.lida_em.is_(None))
    )
    return ContagemSaida(nao_lidos=total or 0)


@router.post("/lidos", status_code=204, responses=erros(NAO_AUTENTICADO, CSRF))
def marcar_todos(usuario: UsuarioDep, session: SessionDep, relogio: RelogioDep) -> Response:
    session.execute(
        update(Notificacao)
        .where(*_meus(usuario), Notificacao.lida_em.is_(None))
        .values(lida_em=relogio.agora())
    )
    session.commit()
    return Response(status_code=204)


@router.post("/{aviso_id}/lido", status_code=204, responses=erros(*ESCRITA, 404))
def marcar_lido(
    aviso_id: UUID, usuario: UsuarioDep, session: SessionDep, relogio: RelogioDep
) -> Response:
    """Idempotente: já lido continua com a data da primeira leitura."""
    n = session.scalar(select(Notificacao).where(Notificacao.id == aviso_id, *_meus(usuario)))
    if n is None:
        raise HTTPException(404, "Aviso não encontrado.")
    if n.lida_em is None:
        n.lida_em = relogio.agora()
        session.commit()
    return Response(status_code=204)
