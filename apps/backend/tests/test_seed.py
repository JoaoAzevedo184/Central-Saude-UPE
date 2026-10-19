from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.infra.acesso import carregar_escopo
from app.infra.modelos import CriterioFila, Fila, Paciente, Unidade, Usuario
from app.infra.relogio import RelogioFixo
from app.infra.seed import cpf_sintetico, semear

pytestmark = pytest.mark.integracao


@pytest.fixture
def sessao(conexao):
    with Session(bind=conexao, join_transaction_mode="create_savepoint") as s:
        yield s


def usuario(sessao, email):
    return sessao.scalar(select(Usuario).where(Usuario.email == email))


def filas_de(sessao, *siglas):
    return frozenset(sessao.scalars(select(Fila.id).join(Unidade).where(Unidade.sigla.in_(siglas))))


def test_seed_cria_dados_e_e_idempotente(sessao):
    relogio = RelogioFixo(datetime(2026, 10, 19, 12, tzinfo=UTC))

    assert semear(sessao, relogio) is True
    assert semear(sessao, relogio) is False

    assert sessao.scalar(select(func.count()).select_from(Unidade)) == 3
    assert sessao.scalar(select(func.count()).select_from(Fila)) == 5
    assert sessao.scalar(select(func.count()).select_from(CriterioFila)) == 7
    assert all(sessao.scalars(select(CriterioFila.simulado)))
    assert usuario(sessao, "atendente.suspenso@exemplo.com").situacao == "SUSPENSO"
    assert sessao.scalar(select(Paciente.cpf)) == "12345678909"


def test_adr025_escopo_a_partir_do_seed(sessao):
    semear(sessao, RelogioFixo(datetime(2026, 10, 19, 12, tzinfo=UTC)))

    def escopo(email):
        return carregar_escopo(sessao, usuario(sessao, email).id)

    assert escopo("admin@exemplo.com") == filas_de(sessao, "CISAM", "HUOC", "PROCAPE")
    assert escopo("gestor.cisam@exemplo.com") == filas_de(sessao, "CISAM")
    assert escopo("atendente.huoc@exemplo.com") == filas_de(sessao, "HUOC")
    assert escopo("atendente.suspenso@exemplo.com") == frozenset()
    assert escopo("paciente@exemplo.com") == frozenset()


def test_cpf_sintetico_tem_digitos_verificadores_validos():
    assert cpf_sintetico("123456789") == "12345678909"
    assert cpf_sintetico("529982247") == "52998224725"


@pytest.mark.parametrize("ambiente", ["production", "test"])
def test_seed_so_roda_em_desenvolvimento(monkeypatch, ambiente):
    from app import config
    from app.infra import seed

    monkeypatch.setenv("APP_ENV", ambiente)
    config.get_settings.cache_clear()
    try:
        with pytest.raises(SystemExit, match="development"):
            seed.main()
    finally:
        config.get_settings.cache_clear()
