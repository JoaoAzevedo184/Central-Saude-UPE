"""O seed com histórico é determinístico: a mesma semente dá as mesmas linhas, com os mesmos ids.

Fica em arquivo próprio porque cada carga toma a trava consultiva do seed e as duas rodam em
sequência, cada uma na sua transação desfeita no fim."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.infra.indicadores import propostas, solicitacoes
from app.infra.modelos import (
    Agendamento,
    Auditoria,
    HistoricoSolicitacao,
    Outbox,
    Solicitacao,
    Usuario,
    Vaga,
)
from app.infra.relogio import RelogioFixo
from app.infra.seed import Opcoes, executar_seed

pytestmark = [pytest.mark.integracao, pytest.mark.lento]

AGORA = datetime(2026, 10, 19, 15, 20, tzinfo=UTC)
SEMANAS = 2


def carregar_e_fotografar(banco) -> dict:
    with banco.connect() as conexao:
        transacao = conexao.begin()
        try:
            with Session(bind=conexao, join_transaction_mode="create_savepoint") as sessao:
                settings = get_settings().model_copy(update={"app_env": "development"})
                executar_seed(
                    sessao,
                    settings,
                    RelogioFixo(AGORA),
                    Opcoes(historico=True, semanas=SEMANAS),
                    lambda _linha: None,
                    "senha-de-teste-123",
                )
                sessao.flush()
                filas = list(sessao.scalars(select(Solicitacao.fila_id).distinct()))
                inicio, fim = AGORA - timedelta(weeks=SEMANAS), AGORA
                return {
                    "solicitacoes": sorted(
                        sessao.execute(
                            select(Solicitacao.id, Solicitacao.status, Solicitacao.fila_id)
                        ).all()
                    ),
                    "agendamentos": sorted(
                        sessao.execute(
                            select(Agendamento.id, Agendamento.status, Agendamento.vaga_id)
                        ).all()
                    ),
                    "vagas": sorted(sessao.scalars(select(Vaga.id))),
                    "usuarios": sorted(sessao.scalars(select(Usuario.id))),
                    "historico": sessao.scalar(
                        select(func.count()).select_from(HistoricoSolicitacao)
                    ),
                    "auditoria": sessao.scalar(select(func.count()).select_from(Auditoria)),
                    "outbox": sessao.scalar(select(func.count()).select_from(Outbox)),
                    "indicadores": {
                        "propostas": propostas(sessao, filas, inicio, fim, "America/Recife"),
                        "solicitacoes": solicitacoes(sessao, filas, inicio, fim, "America/Recife"),
                    },
                }
        finally:
            transacao.rollback()


def test_mesma_semente_da_as_mesmas_linhas_e_os_mesmos_indicadores(banco):
    primeira = carregar_e_fotografar(banco)
    segunda = carregar_e_fotografar(banco)
    assert len(primeira["solicitacoes"]) > 50 and len(primeira["agendamentos"]) > 20
    for chave in primeira:
        assert primeira[chave] == segunda[chave], chave
