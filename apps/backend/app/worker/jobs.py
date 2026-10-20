"""Jobs do Worker (SDD 5.5). Cada job é idempotente e devolve quantos itens processou.

Por enquanto são esqueletos: registram log e devolvem 0.
"""

import logging

from app.infra.autenticacao import apagar_dados_vencidos
from app.infra.db import SessionLocal
from app.infra.relogio import RelogioReal

logger = logging.getLogger(__name__)


def expirar_propostas() -> int:
    """Expira agendamentos PROPOSTO com `expira_em < agora` (UC-004, ADR-005)."""
    logger.info("expirar_propostas: nada a fazer (esqueleto)")
    return 0


def processar_outbox() -> int:
    """Consome eventos PENDENTE da outbox com `FOR UPDATE SKIP LOCKED` (ADR-006)."""
    logger.info("processar_outbox: nada a fazer (esqueleto)")
    return 0


def propor_vagas_livres() -> int:
    """Matching automático: chama `propor_vaga()` para vagas livres (ADR-021)."""
    logger.info("propor_vagas_livres: nada a fazer (esqueleto)")
    return 0


def limpar_dados_de_autenticacao() -> int:
    """Retenção: apaga `tentativa_login` com mais de 24 h e `sessao_refresh` vencidas."""
    with SessionLocal() as session:
        apagados = apagar_dados_vencidos(session, RelogioReal().agora())
        session.commit()
    logger.info("limpar_dados_de_autenticacao: %d linhas apagadas", apagados)
    return apagados
