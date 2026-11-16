"""Consulta da trilha de auditoria (RF-023, RN-010, RNF-004). Só ADMIN, só leitura.

Nunca devolve `dados_antes`/`dados_depois` crus nem o `ip`: o resumo sai de
`dominio.auditoria.montar_campos`, com lista permitida por ação.
"""

from datetime import date
from typing import Annotated, Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import exige_papel, get_session, ip_do_cliente
from app.api.paginacao import Limit, Offset, Pagina
from app.api.problemas import NAO_AUTENTICADO, SEM_PERMISSAO, erros
from app.api.tipos import Papel
from app.config import get_settings
from app.dominio.auditoria import (
    fim_do_dia,
    inicio_do_dia,
    montar_campos,
    verificar_data_da_consulta,
)
from app.dominio.erros import EntradaInvalida
from app.infra.modelos import Agendamento, Auditoria, Usuario

router = APIRouter(prefix="/admin", tags=["admin"])

AdminDep = Annotated[Usuario, Depends(exige_papel("ADMIN"))]
SessionDep = Annotated[Session, Depends(get_session)]

# Escritos à mão (o mypy não aceita Literal dinâmico); um teste confere com `PERMITIDAS`.
Entidade = Literal["solicitacao", "agendamento", "usuario", "paciente", "fila", "unidade"]
Acao = Literal[
    "CRIAR_SOLICITACAO",
    "CLASSIFICAR",
    "RECLASSIFICAR",
    "RESPONDER_CRITERIOS",
    "CANCELAR_SOLICITACAO",
    "CANCELAR_AGENDAMENTO",
    "CONFIRMAR_AGENDAMENTO",
    "RECUSAR_PROPOSTA",
    "EXPIRAR_PROPOSTA",
    "REGISTRAR_COMPARECIMENTO",
    "REGISTRAR_FALTA",
    "PROPOR_VAGA",
    "CRIAR_USUARIO",
    "REDEFINIR_SENHA",
    "ATRIBUIR_FILAS",
    "ATRIBUIR_UNIDADES",
    "SUSPENDER",
    "REATIVAR",
    "LOGIN",
    "TROCAR_SENHA",
    "REGISTRO",
    "CONSULTAR_PAINEL",
    "CONSULTAR_SOLICITACAO",
    "CONSULTAR_AGENDAMENTOS",
    "CONSULTAR_VAGAS",
    "CONSULTAR_INDICADORES",
    "CONSULTAR_AUDITORIA",
]

Valor = str | int | bool | list[str]


class AtorAuditoria(BaseModel):
    tipo: Literal["EQUIPE", "PACIENTE", "SISTEMA"]
    id: UUID | None = Field(description="Só para EQUIPE.")
    papel: Papel | None = Field(description="Nulo para SISTEMA.")
    email: str | None = Field(description="Só para EQUIPE.")


class CampoAuditoria(BaseModel):
    campo: str
    antes: Valor | None
    depois: Valor | None
    oculto: bool = Field(
        description="Campo sensível (`nota`, `respostas`): mudou, mas o valor nunca sai."
    )


class ItemAuditoria(BaseModel):
    id: UUID
    ocorrido_em: str = Field(description="ISO 8601 com fuso.")
    acao: str
    entidade: str
    entidade_id: UUID
    ator: AtorAuditoria
    campos: list[CampoAuditoria]
    detalhes_omitidos: bool = Field(
        description="Chave fora da lista, valor fora do formato ou ação desconhecida."
    )


def _ator(ator_id: UUID | None, usuario: Usuario | None) -> AtorAuditoria:
    if ator_id is None or usuario is None:
        return AtorAuditoria(tipo="SISTEMA", id=None, papel=None, email=None)
    if usuario.papel == "PACIENTE":
        return AtorAuditoria(tipo="PACIENTE", id=None, papel="PACIENTE", email=None)
    return AtorAuditoria(tipo="EQUIPE", id=usuario.id, papel=usuario.papel, email=usuario.email)


@router.get("/auditoria", responses=erros(NAO_AUTENTICADO, SEM_PERMISSAO, 422))
def consultar_auditoria(
    request: Request,
    admin: AdminDep,
    session: SessionDep,
    entidade: Entidade | None = None,
    entidade_id: UUID | None = None,
    acao: Acao | None = None,
    ator_usuario_id: UUID | None = None,
    de: Annotated[date | None, Field(description="Dia inicial, em Recife.")] = None,
    ate: Annotated[date | None, Field(description="Dia final (inclusive), em Recife.")] = None,
    limit: Limit = 50,
    offset: Offset = 0,
) -> Pagina[ItemAuditoria]:
    """Trilha de auditoria, da mais recente para a mais antiga.

    `entidade=solicitacao` com `entidade_id` traz também os registros dos agendamentos dessa
    solicitação. Cada leitura grava `CONSULTAR_AUDITORIA` só com os filtros (AM-007).
    """
    if entidade_id and entidade is None:
        raise EntradaInvalida("`entidade_id` exige `entidade`.")
    for dia in (de, ate):
        if dia:
            verificar_data_da_consulta(dia)
    if de and ate and de > ate:
        raise EntradaInvalida("`de` não pode ser depois de `ate`.")

    filtros = []
    if entidade_id and entidade == "solicitacao":
        # Consulta à parte (indexada por `agendamento.solicitacao_id`): com subconsulta o
        # planner varre todas as linhas `entidade = 'agendamento'` da auditoria.
        dos_agendamentos = session.scalars(
            select(Agendamento.id).where(Agendamento.solicitacao_id == entidade_id)
        ).all()
        filtros.append(
            or_(
                and_(Auditoria.entidade == "solicitacao", Auditoria.entidade_id == entidade_id),
                and_(
                    Auditoria.entidade == "agendamento",
                    Auditoria.entidade_id.in_(dos_agendamentos),
                ),
            )
        )
    else:
        if entidade:
            filtros.append(Auditoria.entidade == entidade)
        if entidade_id:
            filtros.append(Auditoria.entidade_id == entidade_id)
    if acao:
        filtros.append(Auditoria.acao == acao)
    if ator_usuario_id:
        filtros.append(Auditoria.ator_usuario_id == ator_usuario_id)
    fuso = ZoneInfo(get_settings().timezone_exibicao)
    if de:
        filtros.append(Auditoria.ocorrido_em >= inicio_do_dia(de, fuso))
    if ate:
        filtros.append(Auditoria.ocorrido_em < fim_do_dia(ate, fuso))

    total = session.scalar(select(func.count()).select_from(Auditoria).where(*filtros)) or 0
    linhas = session.execute(
        select(Auditoria, Usuario)
        .outerjoin(Usuario, Usuario.id == Auditoria.ator_usuario_id)
        .where(*filtros)
        .order_by(Auditoria.ocorrido_em.desc(), Auditoria.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()

    itens = []
    for registro, ator in linhas:
        campos, omitidos = montar_campos(registro.acao, registro.dados_antes, registro.dados_depois)
        itens.append(
            ItemAuditoria(
                id=registro.id,
                ocorrido_em=registro.ocorrido_em.isoformat(),
                acao=registro.acao,
                entidade=registro.entidade,
                entidade_id=registro.entidade_id,
                ator=_ator(registro.ator_usuario_id, ator),
                campos=[CampoAuditoria(**vars(c)) for c in campos],
                detalhes_omitidos=omitidos,
            )
        )

    session.add(
        Auditoria(
            ator_usuario_id=admin.id,
            acao="CONSULTAR_AUDITORIA",
            entidade="usuario",
            entidade_id=admin.id,
            dados_depois={
                "entidade": entidade,
                "entidade_id": str(entidade_id) if entidade_id else None,
                "acao": acao,
                "ator_usuario_id": str(ator_usuario_id) if ator_usuario_id else None,
                "de": de.isoformat() if de else None,
                "ate": ate.isoformat() if ate else None,
            },
            ip=ip_do_cliente(request),
        )
    )
    session.commit()
    return Pagina(total=total, itens=itens)
