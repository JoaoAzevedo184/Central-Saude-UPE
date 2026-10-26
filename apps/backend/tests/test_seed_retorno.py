"""Retorno de `executar_seed`.

Fica fora de `test_seed_historico.py` de propósito: lá, a fixture `producao` mantém aberta a trava
consultiva do seed e qualquer outra carga no mesmo módulo esperaria por ela para sempre.
"""

from datetime import UTC, datetime

from app.config import get_settings
from app.infra.relogio import RelogioFixo
from app.infra.seed import Opcoes, executar_seed


def test_desenvolvimento_so_diz_que_gerou_senha_quando_criou_contas(sessao):
    settings = get_settings().model_copy(update={"app_env": "development"})
    relogio = RelogioFixo(datetime(2026, 10, 20, 12, tzinfo=UTC))

    def rodar():
        return executar_seed(sessao, settings, relogio, Opcoes(), print, "x" * 12)

    assert rodar() is True
    assert rodar() is False  # estrutura já existia: a senha gerada não valeria para ninguém
