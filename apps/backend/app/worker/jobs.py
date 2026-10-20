"""Jobs do Worker (SDD 5.5). Cada job é idempotente e devolve quantos itens processou.

Cada item roda na própria transação: um item com erro não derruba o lote, e o log leva só
IDs e o tipo do erro (nunca a mensagem, que pode repetir valores). A fábrica de sessão e o
relógio são parâmetros para os testes; o Worker usa os padrões.
"""

import logging
from collections.abc import Callable
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.dominio.relogio import Relogio
from app.infra import agendamentos
from app.infra.autenticacao import apagar_dados_vencidos
from app.infra.db import SessionLocal
from app.infra.relogio import RelogioReal
from app.logging import resumo_do_erro

logger = logging.getLogger(__name__)

Fabrica = Callable[[], Session]


def _por_item(
    nome: str,
    fabrica: Fabrica,
    ids: list[UUID],
    processar: Callable[[Session, UUID], bool | int],
) -> int:
    feitos = 0
    for item in ids:
        with fabrica() as session:
            try:
                resultado = processar(session, item)
                session.commit()
                feitos += int(resultado)
            except IntegrityError as exc:
                session.rollback()
                indice = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
                if indice not in agendamentos.INDICES_DE_OCUPACAO:
                    logger.error("%s: item %s falhou: %s", nome, item, resumo_do_erro(exc))
                else:  # corrida decidida pelo índice (ADR-004): segue para o próximo
                    logger.info("%s: item %s descartado por conflito em %s", nome, item, indice)
            except Exception as exc:
                session.rollback()
                logger.error("%s: item %s falhou: %s", nome, item, resumo_do_erro(exc))
    return feitos


def gerar_vagas(fabrica: Fabrica = SessionLocal, relogio: Relogio | None = None) -> int:
    """Vagas das agendas ativas nos próximos `VAGAS_HORIZONTE_DIAS` dias, sem duplicar."""
    agora = (relogio or RelogioReal()).agora()
    cfg = get_settings()
    with fabrica() as session:
        ids = agendamentos.agendas_ativas(session)
    feitos = _por_item(
        "gerar_vagas",
        fabrica,
        ids,
        lambda s, i: agendamentos.gerar_vagas_da_agenda(s, i, agora, cfg),
    )
    logger.info("gerar_vagas: %d vagas novas", feitos)
    return feitos


def propor_vagas(fabrica: Fabrica = SessionLocal, relogio: Relogio | None = None) -> int:
    """Matching automático (UC-003, ADR-021): cada vaga livre vai ao primeiro elegível."""
    agora = (relogio or RelogioReal()).agora()
    cfg = get_settings()
    with fabrica() as session:
        ids = agendamentos.vagas_livres(session, agora)
    feitos = _por_item(
        "propor_vagas", fabrica, ids, lambda s, i: agendamentos.propor_na_vaga(s, i, agora, cfg)
    )
    logger.info("propor_vagas: %d propostas", feitos)
    return feitos


def expirar_propostas(fabrica: Fabrica = SessionLocal, relogio: Relogio | None = None) -> int:
    """Expira agendamentos PROPOSTO com `expira_em <= agora` (UC-006, ADR-005)."""
    agora = (relogio or RelogioReal()).agora()
    with fabrica() as session:
        ids = agendamentos.propostas_vencidas(session, agora)
    feitos = _por_item(
        "expirar_propostas",
        fabrica,
        ids,
        lambda s, i: agendamentos.expirar_agendamento(s, i, agora),
    )
    logger.info("expirar_propostas: %d expiradas", feitos)
    return feitos


def processar_outbox() -> int:
    """Consome eventos PENDENTE da outbox com `FOR UPDATE SKIP LOCKED` (ADR-006)."""
    logger.info("processar_outbox: nada a fazer (esqueleto)")
    return 0


def limpar_dados_de_autenticacao() -> int:
    """Retenção: apaga `tentativa_login` com mais de 24 h e `sessao_refresh` vencidas."""
    with SessionLocal() as session:
        apagados = apagar_dados_vencidos(session, RelogioReal().agora())
        session.commit()
    logger.info("limpar_dados_de_autenticacao: %d linhas apagadas", apagados)
    return apagados
