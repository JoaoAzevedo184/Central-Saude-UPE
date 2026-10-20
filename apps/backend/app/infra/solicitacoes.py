"""Persistência da solicitação: ordem da fila em SQL e gravação das transições."""

from collections.abc import Iterable
from typing import Any
from uuid import UUID

from sqlalchemy import ColumnElement, case, func, select
from sqlalchemy.orm import Session

from app.dominio.fila.criterios import Criterio
from app.dominio.fila.ordenacao import PESO_RISCO
from app.dominio.solicitacao import EventoHistorico
from app.dominio.solicitacao import Solicitacao as SolicitacaoDominio
from app.infra.modelos import (
    Auditoria,
    CriterioFila,
    HistoricoSolicitacao,
    Outbox,
    Solicitacao,
)

# Eventos que mexem na posição: alimentam a "última mudança" do painel (RN-007).
TIPOS_MUDANCA_DE_POSICAO = ("ENTROU_NA_FILA", "REENTROU_NA_FILA", "RECLASSIFICADA")


def ordem_da_fila() -> list[ColumnElement[Any]]:
    """A mesma ordem de `ordenar_fila()`, em SQL: risco, nota decrescente, chegada, `id`.

    O peso do risco vem do domínio; um teste confere que as duas ordens são iguais.
    """
    return [
        case(PESO_RISCO, value=Solicitacao.classificacao_risco),
        Solicitacao.nota.desc(),
        Solicitacao.data_entrada_fila,
        Solicitacao.id,
    ]


def posicoes_na_fila(fila_id: UUID):
    """Posição de cada solicitação `NA_FILA` da fila, sobre a fila inteira (antes de paginar).

    Calculada na consulta, nunca gravada (ADR-007).
    """
    return (
        select(Solicitacao.id, func.row_number().over(order_by=ordem_da_fila()).label("posicao"))
        .where(Solicitacao.fila_id == fila_id, Solicitacao.status == "NA_FILA")
        .subquery()
    )


def criterios_da_fila(session: Session, fila_id: UUID) -> dict[UUID, Criterio]:
    linhas = session.scalars(
        select(CriterioFila).where(CriterioFila.fila_id == fila_id, CriterioFila.ativo)
    )
    return {c.id: Criterio(c.codigo, c.tipo, c.peso, c.parametros, c.origem) for c in linhas}


def para_dominio(s: Solicitacao) -> SolicitacaoDominio:
    return SolicitacaoDominio(s.id, s.status, s.classificacao_risco, s.nota, s.data_entrada_fila)


def gravar_transicao(
    session: Session,
    modelo: Solicitacao,
    nova: SolicitacaoDominio,
    eventos: Iterable[EventoHistorico],
    *,
    ator_id: UUID | None,
    acao: str,
    ip: str | None,
    evento_outbox: str | None = None,
    criacao: bool = False,
    auditoria_antes: dict[str, Any] | None = None,
    auditoria_depois: dict[str, Any] | None = None,
    agendamento_id: UUID | None = None,
) -> None:
    """Aplica o resultado do domínio e grava linha do tempo, auditoria e outbox (etapas 4 a 7).

    Quem chama já travou a solicitação (`FOR UPDATE`) e conferiu dono ou escopo, ou acabou de
    inseri-la (`criacao`, já com flush); o commit também é de quem chama. A auditoria guarda
    só os campos de estado que mudaram, mais `auditoria_antes`/`auditoria_depois`.
    `ator_id=None` é o Worker. `agendamento_id` vai no payload da outbox.
    """
    campos = ("status", "classificacao_risco", "nota", "data_entrada_fila")
    antes = dict.fromkeys(campos) if criacao else {c: getattr(modelo, c) for c in campos}
    for campo in campos:
        setattr(modelo, campo, getattr(nova, campo))
    mudou = [c for c in campos if antes[c] != getattr(modelo, c)]
    session.add_all(
        HistoricoSolicitacao(
            solicitacao_id=modelo.id,
            tipo=e.tipo,
            status_anterior=e.status_anterior,
            status_novo=e.status_novo,
            motivo=e.motivo,
            visivel_paciente=e.visivel_paciente,
            ator_usuario_id=ator_id,
            ocorrido_em=e.ocorrido_em,
        )
        for e in eventos
    )
    session.add(
        Auditoria(
            ator_usuario_id=ator_id,
            acao=acao,
            entidade="solicitacao",
            entidade_id=modelo.id,
            dados_antes=None
            if criacao
            else para_json({c: antes[c] for c in mudou} | (auditoria_antes or {})),
            dados_depois=para_json(
                {c: getattr(modelo, c) for c in mudou} | (auditoria_depois or {})
            ),
            ip=ip,
        )
    )
    if evento_outbox:
        session.add(
            Outbox(
                tipo_evento=evento_outbox,
                agregado_tipo="solicitacao",
                agregado_id=modelo.id,
                payload={"solicitacao_id": str(modelo.id)}
                | ({"agendamento_id": str(agendamento_id)} if agendamento_id else {}),
            )
        )


def para_json(dados: dict[str, Any]) -> dict[str, Any]:
    return {k: v.isoformat() if hasattr(v, "isoformat") else v for k, v in dados.items()}
