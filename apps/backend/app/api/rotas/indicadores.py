"""Indicadores do gestor (`GET /equipe/indicadores`). GESTOR e ADMIN; ATENDENTE recebe 403.

Só contagens e razões: nenhum dado de paciente. O escopo (ADR-025) filtra as filas dentro da
consulta; fila ou unidade fora do escopo responde 404. A leitura é auditada com período e filtros.
"""

from datetime import date
from typing import Annotated
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.api.deps import (
    Problema,
    escopo_da_equipe,
    exige_papel,
    get_relogio,
    get_session,
    ip_do_cliente,
)
from app.api.problemas import NAO_AUTENTICADO, SEM_PERMISSAO, erros
from app.api.tipos import ClassificacaoRisco
from app.config import get_settings
from app.dominio.indicadores import (
    limites_do_periodo,
    razao,
    semanas_do_periodo,
    verificar_periodo,
)
from app.dominio.relogio import Relogio
from app.dominio.vocabulario import RISCOS
from app.infra import indicadores as consultas
from app.infra.modelos import Auditoria, Usuario

router = APIRouter(prefix="/equipe", tags=["equipe"])

GestorDep = Annotated[Usuario, Depends(exige_papel("GESTOR", "ADMIN"))]
Dia = Annotated[date, Query(ge=date(2000, 1, 1), le=date(2100, 12, 31))]


class Resumo(BaseModel):
    """Contagens e razões de um recorte de tempo (o período todo ou uma semana).

    Uma razão é `null` quando o denominador é 0. Cada família usa a própria âncora de tempo,
    descrita nos campos."""

    confirmadas: int = Field(
        description="Propostas feitas no recorte e confirmadas (`proposto_em`)."
    )
    recusadas: int = Field(description="Propostas feitas no recorte e recusadas pelo paciente.")
    expiradas: int = Field(description="Propostas feitas no recorte e expiradas sem resposta.")
    propostas_encerradas: int = Field(
        description="Confirmadas + recusadas + expiradas: denominador das taxas."
    )
    propostas_canceladas_sem_resposta: int = Field(
        description="Propostas canceladas por outro motivo, sem resposta. Fora das taxas."
    )
    taxa_confirmacao: float | None
    taxa_recusa: float | None
    taxa_expiracao: float | None
    realizadas: int = Field(
        description="Atendimentos realizados com vaga no recorte (`vaga.inicio`)."
    )
    faltas: int = Field(description="Faltas registradas com vaga no recorte (`vaga.inicio`).")
    taxa_faltas: float | None = Field(description="Faltas ÷ (realizadas + faltas).")
    solicitacoes_criadas: int = Field(description="Solicitações criadas no recorte (`criada_em`).")
    desistencias: int = Field(
        description="Dessas solicitações, as que o paciente cancelou (estão CANCELADA com motivo)."
    )
    taxa_desistencia: float | None
    vagas_ofertadas: int = Field(description="Vagas ATIVAS com início no recorte.")
    vagas_ocupadas: int = Field(
        description="Vagas ofertadas com agendamento CONFIRMADO, REALIZADO ou FALTOU. Inclui "
        "CONFIRMADO de vaga futura: nem toda ocupada já foi atendida."
    )
    vagas_reaproveitadas: int = Field(
        description="Vagas com proposta desfeita que outra solicitação confirmou depois."
    )
    vagas_perdidas: int = Field(
        description="Vagas ofertadas já iniciadas sem agendamento CONFIRMADO, REALIZADO ou FALTOU."
    )


class Semana(Resumo):
    semana: date = Field(description="Segunda-feira da semana, em Recife.")


class TempoDeEspera(BaseModel):
    """Da entrada na fila até a primeira confirmação, em dias. Só solicitações cuja primeira
    confirmação cai no período."""

    confirmacoes: int
    mediana_dias: float | None
    p90_dias: float | None


class IndicadoresSaida(BaseModel):
    de: date
    ate: date
    unidade_id: UUID | None
    fila_id: UUID | None
    totais: Resumo
    semanas: list[Semana]
    tempo_de_espera: TempoDeEspera
    fila_atual: dict[ClassificacaoRisco, int] = Field(
        description="Solicitações NA_FILA agora, por cor de risco. Não depende do período."
    )


def _resumo(c: dict[str, int]) -> dict[str, int | float | None]:
    encerradas = c["confirmadas"] + c["recusadas"] + c["expiradas"]
    return {
        **c,
        "propostas_encerradas": encerradas,
        "taxa_confirmacao": razao(c["confirmadas"], encerradas),
        "taxa_recusa": razao(c["recusadas"], encerradas),
        "taxa_expiracao": razao(c["expiradas"], encerradas),
        "taxa_faltas": razao(c["faltas"], c["realizadas"] + c["faltas"]),
        "taxa_desistencia": razao(c["desistencias"], c["solicitacoes_criadas"]),
    }


def _agregar(session, filas, de, ate, inicio, fim, agora, fuso):
    familias = [
        consultas.propostas(session, filas, inicio, fim, fuso),
        consultas.presencas(session, filas, inicio, fim, fuso),
        consultas.solicitacoes(session, filas, inicio, fim, fuso),
        consultas.vagas(session, filas, inicio, fim, agora, fuso),
    ]
    semanas = []
    for segunda in semanas_do_periodo(de, ate):
        contagens = dict.fromkeys(consultas.CONTAGENS, 0)
        for familia in familias:
            contagens.update(familia.get(segunda, {}))
        semanas.append((segunda, contagens))
    totais = {k: sum(c[k] for _, c in semanas) for k in consultas.CONTAGENS}
    return (
        semanas,
        totais,
        consultas.tempo_de_espera(session, filas, inicio, fim),
        consultas.fila_atual(session, filas),
    )


@router.get(
    "/indicadores",
    responses=erros(NAO_AUTENTICADO, SEM_PERMISSAO, 404, 422, (503, "consulta-demorada")),
)
def indicadores(
    de: Dia,
    ate: Dia,
    request: Request,
    usuario: GestorDep,
    escopo: Annotated[frozenset[UUID], Depends(escopo_da_equipe)],
    session: Annotated[Session, Depends(get_session)],
    relogio: Annotated[Relogio, Depends(get_relogio)],
    unidade_id: UUID | None = None,
    fila_id: UUID | None = None,
) -> IndicadoresSaida:
    """Indicadores de `de` a `ate` (dias em Recife, inclusivos, até 366 dias), com totais,
    série semanal e a fila atual. `unidade_id` e `fila_id` restringem o escopo do usuário."""
    verificar_periodo(de, ate)
    filas = consultas.filas_do_escopo(session, escopo, unidade_id, fila_id)
    if (unidade_id or fila_id) and not filas:
        raise HTTPException(404, "Unidade ou fila não encontrada.")

    fuso = get_settings().timezone_exibicao
    inicio, fim = limites_do_periodo(de, ate, ZoneInfo(fuso))
    try:
        consultas.preparar(session, get_settings().indicadores_timeout_s)
        semanas, totais, (n, mediana, p90), cores = _agregar(
            session, filas, de, ate, inicio, fim, relogio.agora(), fuso
        )
    except OperationalError as erro:
        if not consultas.consulta_cancelada(erro):
            raise
        session.rollback()
        raise Problema(
            503,
            "/problemas/consulta-demorada",
            "A consulta demorou mais que o esperado. Tente de novo em instantes.",
            headers={"Retry-After": "30"},
        ) from None

    session.add(
        Auditoria(
            ator_usuario_id=usuario.id,
            acao="CONSULTAR_INDICADORES",
            entidade="fila" if fila_id else "unidade" if unidade_id else "usuario",
            entidade_id=fila_id or unidade_id or usuario.id,
            dados_depois={
                "de": de.isoformat(),
                "ate": ate.isoformat(),
                "unidade_id": str(unidade_id) if unidade_id else None,
                "fila_id": str(fila_id) if fila_id else None,
            },
            ip=ip_do_cliente(request),
        )
    )
    session.commit()
    return IndicadoresSaida(
        de=de,
        ate=ate,
        unidade_id=unidade_id,
        fila_id=fila_id,
        totais=Resumo(**_resumo(totais)),
        semanas=[Semana(semana=segunda, **_resumo(c)) for segunda, c in semanas],
        tempo_de_espera=TempoDeEspera(confirmacoes=n, mediana_dias=mediana, p90_dias=p90),
        fila_atual={r: cores.get(r, 0) for r in RISCOS},
    )
