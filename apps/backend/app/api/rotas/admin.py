"""Administração da equipe: contas, senha temporária, atribuições e suspensão (RF-035, ADR-028).

Só ADMIN. Nunca grava senha, nem em hash, na auditoria; a senha temporária sai uma única vez
na resposta e não passa por log.
"""

import logging
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import delete, func, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import Problema, exige_papel, get_relogio, get_session, ip_do_cliente
from app.api.paginacao import Limit, Offset, Pagina
from app.api.problemas import CSRF, NAO_AUTENTICADO, SEM_PERMISSAO, erros
from app.api.tipos import Papel
from app.dominio.acesso import (
    PAPEIS_EQUIPE,
    verificar_atribuicao_de_filas,
    verificar_atribuicao_de_unidades,
    verificar_criacao_de_usuario,
    verificar_reativacao,
    verificar_redefinicao_de_senha,
    verificar_suspensao,
)
from app.dominio.cadastro import EMAIL
from app.dominio.erros import EntradaInvalida
from app.dominio.relogio import Relogio
from app.infra.autenticacao import (
    aplicar_senha_temporaria,
    gerar_senha_temporaria,
    hash_senha,
    revogar_sessoes,
)
from app.infra.modelos import (
    Auditoria,
    Especialidade,
    Fila,
    SessaoRefresh,
    Unidade,
    Usuario,
    usuario_fila,
    usuario_unidade,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])

AdminDep = Annotated[Usuario, Depends(exige_papel("ADMIN"))]
SessionDep = Annotated[Session, Depends(get_session)]
RelogioDep = Annotated[Relogio, Depends(get_relogio)]

PapelEquipe = Literal["ATENDENTE", "GESTOR", "ADMIN"]
Situacao = Literal["ATIVO", "SUSPENSO"]


class SuspensaoEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    motivo: str = Field(min_length=3, max_length=500)


class UsuarioEntrada(BaseModel):
    """Papel só da equipe. `unidade_ids` vale só para GESTOR (outro papel → 422)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    email: str = Field(max_length=254)
    papel: PapelEquipe
    unidade_ids: list[UUID] | None = None
    confirmar_visao_central: bool = False

    @field_validator("email")
    @classmethod
    def _email(cls, valor: str) -> str:
        valor = valor.lower()
        if not EMAIL.match(valor):
            raise ValueError("E-mail inválido.")
        return valor


class FilasEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fila_ids: list[UUID] = Field(max_length=500)


class UnidadesEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    unidade_ids: list[UUID] = Field(max_length=500)
    confirmar_visao_central: bool = False


class UsuarioAdmin(BaseModel):
    """`filas` só para ATENDENTE e `unidades` só para GESTOR; gestor sem unidade vê a central."""

    id: UUID
    email: str | None
    papel: Papel
    situacao: Situacao
    senha_temporaria: bool
    filas: list[UUID]
    unidades: list[UUID]


class SenhaTemporariaSaida(BaseModel):
    """A senha aparece só aqui, uma vez. Não há como lê-la depois."""

    id: UUID
    senha_temporaria: str


class UnidadeResumo(BaseModel):
    id: UUID
    sigla: str


class EspecialidadeResumo(BaseModel):
    id: UUID
    nome: str


class FilaAdmin(BaseModel):
    id: UUID
    nome: str
    ativa: bool
    unidade: UnidadeResumo
    especialidade: EspecialidadeResumo


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


def _auditar(
    session: Session,
    request: Request,
    admin: Usuario,
    acao: str,
    alvo_id: UUID,
    antes: dict | None = None,
    depois: dict | None = None,
) -> None:
    session.add(
        Auditoria(
            ator_usuario_id=admin.id,
            acao=acao,
            entidade="usuario",
            entidade_id=alvo_id,
            dados_antes=antes,
            dados_depois=depois,
            ip=ip_do_cliente(request),
        )
    )


def _exigir_existentes(session: Session, modelo: type, ids: frozenset[UUID], nome: str) -> None:
    if ids and session.scalar(select(func.count()).where(modelo.id.in_(ids))) != len(ids):
        raise EntradaInvalida(f"{nome} inexistente.")


def _ids(valores: frozenset[UUID]) -> list[str]:
    return sorted(str(v) for v in valores)


@router.get("/usuarios", responses=erros(NAO_AUTENTICADO, SEM_PERMISSAO, 422))
def listar_usuarios(
    _admin: AdminDep,
    session: SessionDep,
    limit: Limit = 50,
    offset: Offset = 0,
    papel: PapelEquipe | None = None,
    situacao: Situacao | None = None,
) -> Pagina[UsuarioAdmin]:
    """Contas da equipe (sem pacientes), com as filas e unidades atribuídas."""
    filtros = [Usuario.papel == papel if papel else Usuario.papel.in_(PAPEIS_EQUIPE)]
    if situacao:
        filtros.append(Usuario.situacao == situacao)
    total = session.scalar(select(func.count()).select_from(Usuario).where(*filtros)) or 0
    usuarios = session.scalars(
        select(Usuario)
        .where(*filtros)
        .order_by(Usuario.criado_em, Usuario.id)
        .limit(limit)
        .offset(offset)
    ).all()
    ids = [u.id for u in usuarios]
    filas: dict[UUID, list[UUID]] = {}
    for usuario_id, fila_id in session.execute(
        select(usuario_fila.c.usuario_id, usuario_fila.c.fila_id)
        .where(usuario_fila.c.usuario_id.in_(ids))
        .order_by(usuario_fila.c.fila_id)
    ):
        filas.setdefault(usuario_id, []).append(fila_id)
    unidades: dict[UUID, list[UUID]] = {}
    for usuario_id, unidade_id in session.execute(
        select(usuario_unidade.c.usuario_id, usuario_unidade.c.unidade_id)
        .where(usuario_unidade.c.usuario_id.in_(ids))
        .order_by(usuario_unidade.c.unidade_id)
    ):
        unidades.setdefault(usuario_id, []).append(unidade_id)
    return Pagina(
        total=total,
        itens=[
            UsuarioAdmin(
                id=u.id,
                email=u.email,
                papel=u.papel,
                situacao=u.situacao,
                senha_temporaria=u.senha_temporaria,
                # Linhas de outro papel ficam no banco mas o domínio as ignora (ADR-025).
                filas=filas.get(u.id, []) if u.papel == "ATENDENTE" else [],
                unidades=unidades.get(u.id, []) if u.papel == "GESTOR" else [],
            )
            for u in usuarios
        ],
    )


@router.post(
    "/usuarios",
    status_code=201,
    responses=erros(
        NAO_AUTENTICADO,
        SEM_PERMISSAO,
        CSRF,
        (409, "email-ja-cadastrado", "visao-central-nao-confirmada"),
        422,
    ),
)
def criar_usuario(
    dados: UsuarioEntrada, request: Request, admin: AdminDep, session: SessionDep
) -> SenhaTemporariaSaida:
    """Cria ATENDENTE, GESTOR ou ADMIN com senha temporária forte, devolvida só aqui. A pessoa
    precisa trocá-la no primeiro acesso. GESTOR sem unidade exige `confirmar_visao_central`."""
    unidade_ids = None if dados.unidade_ids is None else frozenset(dados.unidade_ids)
    verificar_criacao_de_usuario(dados.papel, unidade_ids, dados.confirmar_visao_central)
    _exigir_existentes(session, Unidade, unidade_ids or frozenset(), "Unidade")

    senha = gerar_senha_temporaria()
    try:
        with session.begin_nested():
            usuario = Usuario(
                email=dados.email,
                senha_hash=hash_senha(senha),
                papel=dados.papel,
                senha_temporaria=True,
            )
            session.add(usuario)
            session.flush()
    except IntegrityError as exc:
        if getattr(exc.orig, "sqlstate", None) != "23505":
            raise
        raise Problema(409, "/problemas/email-ja-cadastrado", "E-mail já cadastrado.") from None
    if unidade_ids:
        session.execute(
            insert(usuario_unidade),
            [{"usuario_id": usuario.id, "unidade_id": u} for u in unidade_ids],
        )
    _auditar(
        session,
        request,
        admin,
        "CRIAR_USUARIO",
        usuario.id,
        depois={"papel": usuario.papel, "unidades": _ids(unidade_ids or frozenset())},
    )
    session.commit()
    logger.info("usuario criado: id=%s papel=%s", usuario.id, usuario.papel)
    return SenhaTemporariaSaida(id=usuario.id, senha_temporaria=senha)


@router.post(
    "/usuarios/{usuario_id}/redefinir-senha",
    responses=erros(
        NAO_AUTENTICADO, SEM_PERMISSAO, CSRF, 404, (409, "operacao-nao-permitida"), 422
    ),
)
def redefinir_senha(
    usuario_id: UUID, request: Request, admin: AdminDep, session: SessionDep, relogio: RelogioDep
) -> SenhaTemporariaSaida:
    """Nova senha temporária (devolvida uma vez) e revogação de todas as sessões do usuário."""
    alvo = _travar_alvo(session, usuario_id)
    verificar_redefinicao_de_senha(alvo.papel)
    senha = aplicar_senha_temporaria(session, alvo, relogio.agora())
    _auditar(session, request, admin, "REDEFINIR_SENHA", alvo.id)
    session.commit()
    logger.info("senha redefinida: id=%s", alvo.id)
    return SenhaTemporariaSaida(id=alvo.id, senha_temporaria=senha)


@router.put(
    "/usuarios/{usuario_id}/filas",
    status_code=204,
    responses=erros(
        NAO_AUTENTICADO, SEM_PERMISSAO, CSRF, 404, (409, "operacao-nao-permitida"), 422
    ),
)
def atribuir_filas(
    usuario_id: UUID, dados: FilasEntrada, request: Request, admin: AdminDep, session: SessionDep
) -> Response:
    """Substitui as filas do ATENDENTE (RF-035). Outro papel → 409."""
    alvo = _travar_alvo(session, usuario_id)
    verificar_atribuicao_de_filas(alvo.papel)
    novas = frozenset(dados.fila_ids)
    _exigir_existentes(session, Fila, novas, "Fila")
    antes = frozenset(
        session.scalars(select(usuario_fila.c.fila_id).where(usuario_fila.c.usuario_id == alvo.id))
    )
    session.execute(delete(usuario_fila).where(usuario_fila.c.usuario_id == alvo.id))
    if novas:
        session.execute(
            insert(usuario_fila), [{"usuario_id": alvo.id, "fila_id": f} for f in novas]
        )
    _auditar(
        session,
        request,
        admin,
        "ATRIBUIR_FILAS",
        alvo.id,
        antes={"filas": _ids(antes)},
        depois={"filas": _ids(novas)},
    )
    session.commit()
    return Response(status_code=204)


@router.put(
    "/usuarios/{usuario_id}/unidades",
    status_code=204,
    responses=erros(
        NAO_AUTENTICADO,
        SEM_PERMISSAO,
        CSRF,
        404,
        (409, "operacao-nao-permitida", "visao-central-nao-confirmada"),
        422,
    ),
)
def atribuir_unidades(
    usuario_id: UUID,
    dados: UnidadesEntrada,
    request: Request,
    admin: AdminDep,
    session: SessionDep,
) -> Response:
    """Substitui as unidades do GESTOR (RF-035). Outro papel → 409. Lista vazia faz o gestor
    ver a central inteira (ADR-025) e exige `confirmar_visao_central: true`."""
    alvo = _travar_alvo(session, usuario_id)
    novas = frozenset(dados.unidade_ids)
    verificar_atribuicao_de_unidades(alvo.papel, novas, dados.confirmar_visao_central)
    _exigir_existentes(session, Unidade, novas, "Unidade")
    antes = frozenset(
        session.scalars(
            select(usuario_unidade.c.unidade_id).where(usuario_unidade.c.usuario_id == alvo.id)
        )
    )
    session.execute(delete(usuario_unidade).where(usuario_unidade.c.usuario_id == alvo.id))
    if novas:
        session.execute(
            insert(usuario_unidade), [{"usuario_id": alvo.id, "unidade_id": u} for u in novas]
        )
    _auditar(
        session,
        request,
        admin,
        "ATRIBUIR_UNIDADES",
        alvo.id,
        antes={"unidades": _ids(antes)},
        depois={"unidades": _ids(novas), "visao_central": not novas},
    )
    session.commit()
    return Response(status_code=204)


@router.get("/filas", responses=erros(NAO_AUTENTICADO, SEM_PERMISSAO, 422))
def listar_filas(
    _admin: AdminDep, session: SessionDep, limit: Limit = 50, offset: Offset = 0
) -> Pagina[FilaAdmin]:
    """Todas as filas, com unidade e especialidade, para a tela de atribuição."""
    total = session.scalar(select(func.count()).select_from(Fila)) or 0
    linhas = session.execute(
        select(Fila, Unidade, Especialidade)
        .join(Unidade, Unidade.id == Fila.unidade_id)
        .join(Especialidade, Especialidade.id == Fila.especialidade_id)
        .order_by(Unidade.sigla, Especialidade.nome, Fila.nome, Fila.id)
        .limit(limit)
        .offset(offset)
    ).all()
    return Pagina(
        total=total,
        itens=[
            FilaAdmin(
                id=f.id,
                nome=f.nome,
                ativa=f.ativa,
                unidade=UnidadeResumo(id=u.id, sigla=u.sigla),
                especialidade=EspecialidadeResumo(id=e.id, nome=e.nome),
            )
            for f, u, e in linhas
        ],
    )


@router.post(
    "/usuarios/{usuario_id}/suspender",
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
    _auditar(
        session,
        request,
        admin,
        "SUSPENDER",
        alvo.id,
        antes={"situacao": "ATIVO"},
        depois={"situacao": "SUSPENSO"},
    )
    session.commit()
    return Response(status_code=204)


@router.post(
    "/usuarios/{usuario_id}/reativar",
    status_code=204,
    responses=erros(NAO_AUTENTICADO, SEM_PERMISSAO, CSRF, 404, (409, "transicao-invalida"), 422),
)
def reativar(usuario_id: UUID, request: Request, admin: AdminDep, session: SessionDep) -> Response:
    """Volta a ATIVO. `suspenso_em` e `motivo_suspensao` ficam como registro (ADR-028)."""
    alvo = _travar_alvo(session, usuario_id)
    verificar_reativacao(alvo.situacao)
    alvo.situacao = "ATIVO"
    _auditar(
        session,
        request,
        admin,
        "REATIVAR",
        alvo.id,
        antes={"situacao": "SUSPENSO"},
        depois={"situacao": "ATIVO"},
    )
    session.commit()
    return Response(status_code=204)
