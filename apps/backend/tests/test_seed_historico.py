"""Seed com histórico e as travas de production (banco de demonstração).

Cobre o Passo 0 da Parte 3: travas, nenhuma senha conhecida em production, histórico coerente com
as regras (gerado pelos mesmos jobs e transições da API), outbox que não dispara e-mail e
idempotência sem troca de senha. As cargas de 2 semanas custam ~35 s cada e são feitas uma vez
por módulo; os testes só leem.
"""

import re
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, insert, select
from sqlalchemy.orm import Session

from app.api.deps import get_relogio, get_session
from app.api.main import app
from app.config import get_settings
from app.dominio.cadastro import cpf_valido
from app.infra.autenticacao import conferir_senha
from app.infra.indicadores import propostas, solicitacoes
from app.infra.modelos import (
    Agendamento,
    Auditoria,
    HistoricoSolicitacao,
    Notificacao,
    Outbox,
    Paciente,
    Solicitacao,
    Unidade,
    Usuario,
    Vaga,
    usuario_unidade,
)
from app.infra.relogio import RelogioFixo
from app.infra.seed import Opcoes, SeedRecusado, executar_seed
from app.infra.seed_historico import (
    PRE_PERIODO,
    RAMPA,
    cpf_de_apresentacao,
    cpf_do_pool,
    cpf_e_do_seed,
)
from app.worker import jobs
from tests.fila_sintetica import criar_paciente

pytestmark = pytest.mark.integracao

AGORA = datetime(2026, 10, 19, 15, 20, tzinfo=UTC)
SEMANAS = 2
SENHA_DEV = "senha-comum-de-desenvolvimento"
EQUIPE = (
    "admin@exemplo.com",
    "gestor.cisam@exemplo.com",
    "gestor.central@exemplo.com",
    "atendente.huoc@exemplo.com",
    "atendente.cisam@exemplo.com",
    "atendente.procape@exemplo.com",
)


def config(ambiente: str, *, demo: bool = False):
    return get_settings().model_copy(update={"app_env": ambiente, "demo_seed_permitido": demo})


def relogio() -> RelogioFixo:
    return RelogioFixo(AGORA)


# --- travas ---------------------------------------------------------------------------------


def test_trava_production_sem_a_variavel_recusa_e_explica(sessao):
    with pytest.raises(SeedRecusado, match="DEMO_SEED_PERMITIDO=true") as erro:
        executar_seed(sessao, config("production"), relogio(), Opcoes(confirmo=True), print)
    assert "--confirmo-banco-de-demonstracao" in str(erro.value)
    assert sessao.scalar(select(func.count()).select_from(Unidade)) == 0


def test_trava_production_sem_a_flag_recusa_e_explica(sessao):
    with pytest.raises(SeedRecusado, match="--confirmo-banco-de-demonstracao"):
        executar_seed(sessao, config("production", demo=True), relogio(), Opcoes(), print)
    assert sessao.scalar(select(func.count()).select_from(Unidade)) == 0


def test_trava_production_com_paciente_que_nao_e_do_seed_recusa(sessao):
    _, cadastro_do_site = criar_paciente(sessao, login=False)
    with pytest.raises(SeedRecusado, match="não é do seed") as erro:
        executar_seed(
            sessao, config("production", demo=True), relogio(), Opcoes(confirmo=True), print
        )
    assert cadastro_do_site.cpf not in str(erro.value)  # a mensagem nunca traz CPF
    assert sessao.scalar(select(func.count()).select_from(Unidade)) == 0


def test_trava_vale_tambem_sem_historico_e_em_qualquer_ambiente_fora_da_lista(sessao):
    _, _ = criar_paciente(sessao, login=False)
    with pytest.raises(SeedRecusado, match="não é do seed"):
        executar_seed(
            sessao, config("production", demo=True), relogio(), Opcoes(confirmo=True), print
        )
    with pytest.raises(SeedRecusado, match="development"):
        executar_seed(sessao, config("test"), relogio(), Opcoes(), print)


@pytest.mark.parametrize("semanas", [1, 27])
def test_semanas_fora_do_intervalo_recusa(sessao, semanas):
    with pytest.raises(SeedRecusado, match="--semanas"):
        executar_seed(sessao, config("development"), relogio(), Opcoes(True, semanas), print)


def test_main_production_com_a_variavel_mas_sem_a_flag_sai_com_explicacao(monkeypatch):
    from app import config as modulo
    from app.infra import seed

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DEMO_SEED_PERMITIDO", "true")
    monkeypatch.setenv("JWT_SECRET_KEY", "x" * 64)
    monkeypatch.setenv("LOGIN_HASH_KEY", "y" * 64)
    monkeypatch.setenv("COOKIE_SECURE", "true")
    monkeypatch.setenv("APP_URL_PUBLICA", "https://central.exemplo.com")
    modulo.get_settings.cache_clear()
    try:
        with pytest.raises(SystemExit, match="--confirmo-banco-de-demonstracao"):
            seed.main(["--historico"])
    finally:
        modulo.get_settings.cache_clear()


def test_cpf_do_seed_so_dentro_das_faixas_reservadas():
    assert cpf_e_do_seed(cpf_do_pool(1)) and cpf_e_do_seed(cpf_do_pool(99_999))
    assert cpf_e_do_seed(cpf_de_apresentacao(1)) and cpf_e_do_seed(cpf_de_apresentacao(2))
    assert cpf_e_do_seed("12345678909")  # paciente do seed de desenvolvimento
    assert not cpf_e_do_seed(cpf_do_pool(100_000))
    assert not cpf_e_do_seed("52998224725")
    assert not cpf_e_do_seed(cpf_do_pool(1)[:10] + "0")  # faixa certa, verificador errado
    assert all(cpf_valido(cpf_do_pool(i)) for i in (1, 2, 500))


# --- cargas de 2 semanas (uma por módulo) ------------------------------------------------------


def _carga(banco, ambiente, **opcoes):
    with banco.connect() as conexao:
        transacao = conexao.begin()
        with Session(bind=conexao, join_transaction_mode="create_savepoint") as sessao:
            saida: list[str] = []
            executar_seed(
                sessao,
                config(ambiente, demo=True),
                relogio(),
                Opcoes(historico=True, semanas=SEMANAS, **opcoes),
                saida.append,
                SENHA_DEV if ambiente == "development" else None,
            )
            sessao.flush()
            yield sessao, saida
        transacao.rollback()


@pytest.fixture(scope="module")
def desenvolvimento(banco):
    """Carga em development, lida e desfeita antes de `producao` começar: as duas criam as mesmas
    chaves únicas, então não podem ficar abertas ao mesmo tempo."""
    for sessao, saida in _carga(banco, "development"):
        senhas_ok = all(
            conferir_senha(usuario(sessao, e).senha_hash, SENHA_DEV)
            and not usuario(sessao, e).senha_temporaria
            for e in (*EQUIPE, "atendente.suspenso@exemplo.com", "paciente@exemplo.com")
        )
        apresentacao = sessao.scalar(
            select(Usuario)
            .join(Paciente, Paciente.usuario_id == Usuario.id)
            .where(Paciente.cpf == cpf_de_apresentacao(1))
        )
        resumo = {
            "senhas_ok": senhas_ok,
            "apresentacao_ok": conferir_senha(apresentacao.senha_hash, SENHA_DEV)
            and not apresentacao.senha_temporaria,
            "sem_temporarias": "SENHAS TEMPORÁRIAS" not in "\n".join(saida),
            "solicitacoes": contagem(sessao, Solicitacao),
            "agendamentos": contagem(sessao, Agendamento),
        }
    return resumo


@pytest.fixture(scope="module")
def evento_alheio(banco):
    """Evento de outbox pendente, gravado e confirmado antes da carga por outra transação."""
    with banco.begin() as conexao:
        id_ = conexao.execute(
            insert(Outbox)
            .values(
                tipo_evento="SOLICITACAO_CRIADA",
                agregado_tipo="solicitacao",
                agregado_id=uuid4(),
                payload={},
                criado_em=AGORA - timedelta(days=1),
            )
            .returning(Outbox.id)
        ).scalar_one()
    yield id_
    with banco.begin() as conexao:
        conexao.execute(delete(Outbox).where(Outbox.id == id_))


@pytest.fixture(scope="module")
def producao(banco, desenvolvimento, evento_alheio):
    yield from _carga(banco, "production", confirmo=True)


def contagem(sessao, modelo):
    return dict(sessao.execute(select(modelo.status, func.count()).group_by(modelo.status)).all())


def usuario(sessao, email):
    return sessao.scalar(select(Usuario).where(Usuario.email == email))


def senhas_impressas(saida):
    return re.findall(
        r"^\s+(?:ADMIN|GESTOR|ATENDENTE|PACIENTE)\s+(\S+)\s+(\S+)$", "\n".join(saida), re.M
    )


@pytest.mark.lento
def test_production_ninguem_tem_senha_conhecida_e_a_equipe_troca_no_primeiro_acesso(producao):
    sessao, saida = producao
    impressas = dict(senhas_impressas(saida))
    cpfs_de_apresentacao = {cpf_de_apresentacao(1), cpf_de_apresentacao(2)}
    assert set(impressas) == {*EQUIPE, *cpfs_de_apresentacao}
    for identificador, senha in impressas.items():
        if identificador in cpfs_de_apresentacao:
            u = sessao.scalar(
                select(Usuario)
                .join(Paciente, Paciente.usuario_id == Usuario.id)
                .where(Paciente.cpf == identificador)
            )
            assert u.email is None  # sem e-mail
        else:
            u = usuario(sessao, identificador)
        assert u.senha_temporaria is True
        assert conferir_senha(u.senha_hash, senha)
    # cada senha aparece uma única vez no que foi escrito
    texto = "\n".join(saida)
    assert all(texto.count(senha) == 1 for senha in impressas.values())
    # os demais pacientes e a conta suspensa: senha aleatória, não impressa, sem login possível
    outros = sessao.scalars(
        select(Usuario).where(
            Usuario.senha_temporaria.is_(False), Usuario.email.is_distinct_from("nunca")
        )
    ).all()
    assert len(outros) > 50
    assert not any(conferir_senha(u.senha_hash, SENHA_DEV) for u in outros)
    assert usuario(sessao, "atendente.suspenso@exemplo.com").senha_temporaria is False
    assert usuario(sessao, "paciente@exemplo.com") is None  # sem e-mail na demonstração


@pytest.mark.lento
def test_production_senha_nao_vai_para_auditoria_nem_para_historico(producao):
    sessao, saida = producao
    impressas = [senha for _, senha in senhas_impressas(saida)]
    registros = [
        str(a.dados_antes) + str(a.dados_depois) for a in sessao.scalars(select(Auditoria)).all()
    ] + [str(h.motivo) for h in sessao.scalars(select(HistoricoSolicitacao)).all()]
    assert not any(senha in r for senha in impressas for r in registros)


@pytest.mark.lento
def test_production_o_login_da_equipe_pede_troca_antes_de_qualquer_coisa(producao):
    sessao, saida = producao
    senha = dict(senhas_impressas(saida))["admin@exemplo.com"]
    app.dependency_overrides[get_session] = lambda: sessao
    app.dependency_overrides[get_relogio] = relogio
    try:
        with TestClient(app, client=("203.0.113.9", 50000)) as cliente:
            entrou = cliente.post(
                "/api/v1/auth/login",
                json={"identificador": "admin@exemplo.com", "senha": senha},
            )
            assert entrou.status_code == 200 and entrou.json()["trocar_senha"] is True
            negado = cliente.get(
                "/api/v1/equipe/indicadores", params={"de": "2026-10-05", "ate": "2026-10-18"}
            )
            assert negado.status_code == 403
            assert negado.json()["type"] == "/problemas/troca-de-senha-obrigatoria"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.lento
def test_outbox_do_historico_nao_dispara_aviso_nem_email(producao, evento_alheio):
    sessao, _ = producao
    assert sessao.scalar(select(func.count()).select_from(Outbox)) > 100
    # só o evento alheio (de outra transação) continua pendente: a carga não toca no que não criou
    pendentes = sessao.scalars(select(Outbox.id).where(Outbox.status != "PROCESSADO")).all()
    assert pendentes == [evento_alheio]
    assert sessao.scalar(select(func.count()).select_from(Notificacao)) == 0
    assert (
        sessao.scalar(
            select(func.count())
            .select_from(Usuario)
            .where(Usuario.papel == "PACIENTE", Usuario.email.is_not(None))
        )
        == 0
    )

    def fabrica():
        return Session(bind=sessao.connection(), join_transaction_mode="create_savepoint")

    # o único pendente é o evento alheio (payload vazio): o job falha nele e não o conta
    assert jobs.processar_outbox(fabrica, relogio()) == 0
    assert jobs.enviar_emails(fabrica, relogio()) == 0
    # O lembrete de consulta próxima ainda nasce no site (IN_APP), como para qualquer paciente;
    # por e-mail não: os pacientes sintéticos não têm e-mail nem consentimento de lembrete.
    jobs.enviar_lembretes(fabrica, relogio())
    assert (
        sessao.scalar(
            select(func.count()).select_from(Notificacao).where(Notificacao.canal == "EMAIL")
        )
        == 0
    )
    assert jobs.enviar_emails(fabrica, relogio()) == 0


@pytest.mark.lento
def test_a_simulacao_comeca_com_a_fila_formada_pelas_rotinas_reais(producao):
    sessao, _ = producao
    inicio = AGORA - timedelta(weeks=SEMANAS)
    # solicitações de antes do período, já classificadas (passaram por `classificar_na_fila`)
    antigas = sessao.scalars(select(Solicitacao).where(Solicitacao.criada_em < inicio)).all()
    assert len(antigas) > 100
    assert all(
        s.status != "EM_ANALISE" for s in antigas if s.criada_em < inicio - timedelta(days=3)
    )
    na_fila_no_inicio = sessao.scalar(
        select(func.count())
        .select_from(HistoricoSolicitacao)
        .where(
            HistoricoSolicitacao.tipo == "ENTROU_NA_FILA", HistoricoSolicitacao.ocorrido_em < inicio
        )
    )
    assert na_fila_no_inicio > 100
    # a primeira proposta é de quando as vagas abriram, nunca de antes
    assert sessao.scalar(select(func.min(Agendamento.proposto_em))) >= inicio - RAMPA


@pytest.mark.lento
def test_gestor_da_central_nao_tem_unidade_e_entra_com_senha_temporaria(producao):
    sessao, saida = producao
    gestor = usuario(sessao, "gestor.central@exemplo.com")
    assert gestor.papel == "GESTOR" and gestor.senha_temporaria is True
    assert (
        sessao.scalar(
            select(func.count())
            .select_from(usuario_unidade)
            .where(usuario_unidade.c.usuario_id == gestor.id)
        )
        == 0
    )
    assert "gestor.central@exemplo.com" in dict(senhas_impressas(saida))


@pytest.mark.lento
def test_historico_respeita_a_janela_e_os_estados(producao):
    sessao, _ = producao
    inicio = AGORA - timedelta(weeks=SEMANAS)
    assert sessao.scalar(select(func.count()).where(HistoricoSolicitacao.ocorrido_em > AGORA)) == 0
    # a fila inicial nasce no pré-período, antes da primeira vaga
    assert sessao.scalar(select(func.min(HistoricoSolicitacao.ocorrido_em))) >= (
        inicio - RAMPA - PRE_PERIODO
    )
    assert sessao.scalar(select(func.min(Agendamento.proposto_em))) >= inicio - RAMPA
    assert sessao.scalar(select(func.max(Agendamento.proposto_em))) <= AGORA
    assert sessao.scalar(select(func.min(Solicitacao.criada_em))) >= inicio - RAMPA - PRE_PERIODO
    por_status = contagem(sessao, Solicitacao)
    assert {"ATENDIDA", "AGENDADA", "CANCELADA"} <= set(por_status)
    # solicitação AGENDADA tem exatamente um CONFIRMADO; EM_PROPOSTA, exatamente um PROPOSTO
    for status_solicitacao, status_agendamento in (
        ("AGENDADA", "CONFIRMADO"),
        ("EM_PROPOSTA", "PROPOSTO"),
    ):
        sem_par = sessao.scalar(
            select(func.count())
            .select_from(Solicitacao)
            .where(
                Solicitacao.status == status_solicitacao,
                select(func.count())
                .where(
                    Agendamento.solicitacao_id == Solicitacao.id,
                    Agendamento.status == status_agendamento,
                )
                .scalar_subquery()
                != 1,
            )
        )
        assert sem_par == 0, status_solicitacao
    # proposta aberta ainda está no prazo no momento da carga
    assert (
        sessao.scalar(
            select(func.count()).where(
                Agendamento.status == "PROPOSTO", Agendamento.expira_em <= AGORA
            )
        )
        == 0
    )
    # presença só depois do início da vaga
    assert (
        sessao.scalar(
            select(func.count())
            .select_from(Agendamento)
            .join(Vaga, Vaga.id == Agendamento.vaga_id)
            .where(Agendamento.status.in_(("REALIZADO", "FALTOU")), Vaga.inicio > AGORA)
        )
        == 0
    )


@pytest.mark.lento
def test_pacientes_de_apresentacao_tem_o_historico_do_roteiro(producao):
    sessao, _ = producao

    def do_paciente(numero, *filtros):
        return sessao.scalars(
            select(Agendamento)
            .join(Solicitacao, Solicitacao.id == Agendamento.solicitacao_id)
            .join(Paciente, Paciente.id == Solicitacao.paciente_id)
            .where(Paciente.cpf == cpf_de_apresentacao(numero), *filtros)
        ).all()

    assert do_paciente(1, Agendamento.status == "REALIZADO")
    aberta = do_paciente(1, Agendamento.status == "PROPOSTO")
    assert len(aberta) == 1 and aberta[0].expira_em > AGORA
    futura = sessao.scalars(
        select(Agendamento)
        .join(Solicitacao, Solicitacao.id == Agendamento.solicitacao_id)
        .join(Paciente, Paciente.id == Solicitacao.paciente_id)
        .join(Vaga, Vaga.id == Agendamento.vaga_id)
        .where(
            Paciente.cpf == cpf_de_apresentacao(2),
            Agendamento.status == "CONFIRMADO",
            Vaga.inicio > AGORA,
        )
    ).all()
    assert len(futura) == 1
    cancelada = sessao.scalar(
        select(func.count())
        .select_from(Solicitacao)
        .join(Paciente, Paciente.id == Solicitacao.paciente_id)
        .where(Paciente.cpf == cpf_de_apresentacao(2), Solicitacao.status == "CANCELADA")
    )
    assert cancelada == 1


@pytest.mark.lento
def test_todo_paciente_criado_e_do_seed_e_o_banco_aceita_o_cpf(producao):
    sessao, _ = producao
    cpfs = sessao.scalars(select(Paciente.cpf)).all()
    assert len(cpfs) > 50 and all(cpf_e_do_seed(c) and cpf_valido(c) for c in cpfs)


@pytest.mark.lento
def test_indicadores_leem_o_historico(producao):
    sessao, _ = producao
    inicio, fim = AGORA - timedelta(weeks=SEMANAS), AGORA
    filas = list(sessao.scalars(select(Solicitacao.fila_id).distinct()))
    fuso = "America/Recife"
    prop = propostas(sessao, filas, inicio, fim, fuso)
    cont = {k: sum(w[k] for w in prop.values()) for k in ("confirmadas", "recusadas", "expiradas")}
    assert all(v > 0 for v in cont.values()), cont
    criadas = sum(
        w["solicitacoes_criadas"] for w in solicitacoes(sessao, filas, inicio, fim, fuso).values()
    )
    assert criadas > 50


@pytest.mark.lento
def test_reexecutar_nao_troca_senha_nem_duplica(producao):
    sessao, _ = producao
    antes = {u.id: u.senha_hash for u in sessao.scalars(select(Usuario)).all()}
    solicitacoes_antes = sessao.scalar(select(func.count()).select_from(Solicitacao))
    saida: list[str] = []
    executar_seed(
        sessao,
        config("production", demo=True),
        relogio(),
        Opcoes(True, SEMANAS, True),
        saida.append,
    )
    depois = {u.id: u.senha_hash for u in sessao.scalars(select(Usuario)).all()}
    assert depois == antes
    assert sessao.scalar(select(func.count()).select_from(Solicitacao)) == solicitacoes_antes
    texto = "\n".join(saida)
    assert "redefinir-senha" in texto and "histórico já existia" in texto
    assert not senhas_impressas(saida) and "SENHAS TEMPORÁRIAS" not in texto


@pytest.mark.lento
def test_desenvolvimento_mantem_a_senha_comum_e_o_historico_e_reprodutivel(
    producao, desenvolvimento
):
    prod, _ = producao
    assert desenvolvimento["senhas_ok"] and desenvolvimento["apresentacao_ok"]
    assert desenvolvimento["sem_temporarias"]
    # Mesma semente e mesmo relógio: o histórico é o mesmo em qualquer ambiente (ids da semente).
    assert desenvolvimento["solicitacoes"] == contagem(prod, Solicitacao)
    assert desenvolvimento["agendamentos"] == contagem(prod, Agendamento)


def test_main_em_production_nao_repete_dado_do_erro(monkeypatch, capsys):
    from app import config as modulo
    from app.infra import seed

    def estoura(*_a, **_k):
        raise RuntimeError("Key (cpf)=(90000000192) already exists")

    monkeypatch.setattr(seed, "executar_seed", estoura)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DEMO_SEED_PERMITIDO", "true")
    monkeypatch.setenv("JWT_SECRET_KEY", "x" * 64)
    monkeypatch.setenv("LOGIN_HASH_KEY", "y" * 64)
    monkeypatch.setenv("COOKIE_SECURE", "true")
    monkeypatch.setenv("APP_URL_PUBLICA", "https://central.exemplo.com")
    modulo.get_settings.cache_clear()
    try:
        with pytest.raises(SystemExit) as saida:
            seed.main(["--confirmo-banco-de-demonstracao"])
    finally:
        modulo.get_settings.cache_clear()
    assert "90000000192" not in str(saida.value) and "nada foi gravado" in str(saida.value)
