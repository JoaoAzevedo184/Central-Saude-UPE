"""Restrições do banco (migração 0002). Cada teste confere a restrição exata que disparou."""

from datetime import UTC, date, datetime, time, timedelta

import pytest
from sqlalchemy import insert, text
from sqlalchemy.exc import DBAPIError

from app.infra.db import Base

pytestmark = pytest.mark.integracao

T0 = datetime(2026, 11, 3, 13, 0, tzinfo=UTC)


def inserir(c, tabela, **valores):
    t = Base.metadata.tables[tabela]
    stmt = insert(t).values(**valores)
    if "id" in t.c:
        return c.execute(stmt.returning(t.c.id)).scalar_one()
    c.execute(stmt)


def viola(c, restricao, sql_ou_funcao, params=None):
    """Executa dentro de um savepoint e confere o nome da restrição violada."""
    with pytest.raises(DBAPIError) as erro, c.begin_nested():
        if callable(sql_ou_funcao):
            sql_ou_funcao()
        else:
            c.execute(text(sql_ou_funcao), params or {})
    assert erro.value.orig.diag.constraint_name == restricao


def append_only(c, sql, params):
    with pytest.raises(DBAPIError) as erro, c.begin_nested():
        c.execute(text(sql), params)
    assert erro.value.orig.sqlstate == "23001"
    assert "append-only" in str(erro.value.orig)


_contador = iter(range(10**6))


def usuario(c, papel="PACIENTE", **extra):
    return inserir(
        c, "usuario", email=f"u{next(_contador)}@exemplo.com", senha_hash="!", papel=papel, **extra
    )


def solicitacao(c, grafo, **extra):
    valores = {"status": "NA_FILA", "classificacao_risco": "VERDE", "data_entrada_fila": T0}
    valores.update(extra)
    return inserir(
        c,
        "solicitacao",
        paciente_id=grafo["paciente"],
        fila_id=grafo["fila"],
        data_pedido=date(2026, 10, 1),
        **valores,
    )


def vaga(c, grafo, horas=0):
    inicio = T0 + timedelta(days=7, hours=horas)
    return inserir(
        c, "vaga", agenda_id=grafo["agenda"], inicio=inicio, fim=inicio + timedelta(minutes=30)
    )


def agendamento(c, solicitacao_id, vaga_id, status="PROPOSTO"):
    return inserir(
        c,
        "agendamento",
        solicitacao_id=solicitacao_id,
        vaga_id=vaga_id,
        status=status,
        proposto_em=T0,
        expira_em=T0 + timedelta(hours=48),
    )


@pytest.fixture
def grafo(conexao):
    """Grafo mínimo válido: unidade → especialidade → fila → agenda; usuário → paciente."""
    c = conexao
    g = {"unidade": inserir(c, "unidade", sigla="TESTE", nome="Unidade de Teste")}
    g["especialidade"] = inserir(c, "especialidade", nome="Especialidade de Teste")
    g["fila"] = inserir(
        c,
        "fila",
        unidade_id=g["unidade"],
        especialidade_id=g["especialidade"],
        nome="Fila de Teste",
        descricao_paciente="Fila sintética.",
    )
    g["agenda"] = inserir(
        c,
        "agenda",
        fila_id=g["fila"],
        profissional="Profissional Sintético",
        dias_semana=[1, 3],
        hora_inicio=time(8),
        hora_fim=time(12),
        duracao_min=30,
        vigencia_inicio=date(2026, 11, 1),
    )
    g["usuario"] = usuario(c)
    g["paciente"] = inserir(
        c,
        "paciente",
        usuario_id=g["usuario"],
        nome="Paciente Sintético",
        cpf="12345678909",
        data_nascimento=date(1990, 1, 1),
    )
    g["criterio"] = inserir(
        c,
        "criterio_fila",
        fila_id=g["fila"],
        codigo="C1",
        descricao="Critério sintético",
        tipo="SIM_NAO",
        peso=10,
        origem="PACIENTE",
    )
    return g


def test_grafo_minimo_completo_e_aceito(conexao, grafo):
    s = solicitacao(conexao, grafo)
    a = agendamento(conexao, s, vaga(conexao, grafo))
    inserir(
        conexao,
        "resposta_criterio",
        solicitacao_id=s,
        criterio_id=grafo["criterio"],
        fila_id=grafo["fila"],
        valor=True,
        pontos=10,
    )
    inserir(
        conexao, "historico_solicitacao", solicitacao_id=s, tipo="CRIADA", visivel_paciente=True
    )
    inserir(
        conexao,
        "notificacao",
        usuario_id=grafo["usuario"],
        agendamento_id=a,
        canal="IN_APP",
        tipo="PROPOSTA",
        titulo="Vaga",
        corpo="Há uma vaga para você.",
    )

    assert conexao.execute(text("SELECT count(*) FROM agendamento")).scalar_one() == 1


@pytest.mark.parametrize("liberado", ["CANCELADO", "EXPIRADO"])
def test_adr004_vaga_so_tem_um_agendamento_ativo(conexao, grafo, liberado):
    v = vaga(conexao, grafo)
    # Duas solicitações diferentes: senão quem dispara é o índice da RN-002.
    s1, s2 = solicitacao(conexao, grafo), solicitacao(conexao, grafo)
    a1 = agendamento(conexao, s1, v)

    viola(conexao, "ux_agendamento_vaga_ativa", lambda: agendamento(conexao, s2, v))
    viola(
        conexao,
        "ux_agendamento_vaga_ativa",
        lambda: agendamento(conexao, s2, v, status="CONFIRMADO"),
    )

    conexao.execute(
        text("UPDATE agendamento SET status = :s WHERE id = :id"), {"s": liberado, "id": a1}
    )
    agendamento(conexao, s2, v)  # com a primeira liberada, a vaga aceita nova proposta


def test_rn002_solicitacao_so_tem_uma_proposta_ativa(conexao, grafo):
    s = solicitacao(conexao, grafo)
    agendamento(conexao, s, vaga(conexao, grafo))

    viola(
        conexao,
        "ux_agendamento_solicitacao_ativa",
        lambda: agendamento(conexao, s, vaga(conexao, grafo, horas=1)),
    )


def test_vaga_duplicada_na_mesma_agenda(conexao, grafo):
    vaga(conexao, grafo)

    viola(conexao, "uq_vaga_agenda_inicio", lambda: vaga(conexao, grafo))


def test_um_consentimento_vigente_por_finalidade(conexao, grafo):
    def consentir(**extra):
        return inserir(
            conexao,
            "consentimento",
            paciente_id=grafo["paciente"],
            finalidade="AGENDAMENTO",
            versao_termo="v1",
            **extra,
        )

    consentir(revogado_em=T0)
    consentir()  # o revogado não conta

    viola(conexao, "ux_consentimento_vigente", consentir)


def test_adr027_fila_com_idade_minima_maior_que_maxima(conexao, grafo):
    viola(
        conexao,
        "ck_fila_faixa_etaria",
        lambda: inserir(
            conexao,
            "fila",
            unidade_id=grafo["unidade"],
            especialidade_id=grafo["especialidade"],
            nome="Faixa invertida",
            descricao_paciente="x",
            idade_minima=60,
            idade_maxima=18,
        ),
    )


def test_adr024_solicitacao_na_fila_sem_classificacao_de_risco(conexao, grafo):
    viola(
        conexao,
        "ck_solicitacao_classificada",
        lambda: solicitacao(conexao, grafo, classificacao_risco=None),
    )


def test_adr024_em_analise_pode_ficar_sem_risco(conexao, grafo):
    solicitacao(
        conexao, grafo, status="EM_ANALISE", classificacao_risco=None, data_entrada_fila=None
    )


def test_adr024_risco_azul_nao_existe_mais(conexao, grafo):
    viola(
        conexao,
        "ck_solicitacao_classificacao_risco",
        lambda: solicitacao(conexao, grafo, classificacao_risco="AZUL"),
    )


def test_adr026_na_fila_exige_hora_de_chegada(conexao, grafo):
    viola(
        conexao,
        "ck_solicitacao_na_fila_com_entrada",
        lambda: solicitacao(conexao, grafo, data_entrada_fila=None),
    )


def test_adr028_suspenso_sem_data_de_suspensao(conexao):
    viola(
        conexao,
        "ck_usuario_suspensao_datada",
        lambda: usuario(conexao, "ATENDENTE", situacao="SUSPENSO"),
    )


def test_adr028_suspenso_com_data_e_aceito(conexao):
    usuario(conexao, "ATENDENTE", situacao="SUSPENSO", suspenso_em=T0)


def test_adr024_duas_respostas_para_o_mesmo_criterio(conexao, grafo):
    s = solicitacao(conexao, grafo)

    def responder():
        inserir(
            conexao,
            "resposta_criterio",
            solicitacao_id=s,
            criterio_id=grafo["criterio"],
            fila_id=grafo["fila"],
            valor=True,
            pontos=10,
        )

    responder()
    viola(conexao, "pk_resposta_criterio", responder)


@pytest.fixture
def outra_fila(conexao, grafo):
    fila = inserir(
        conexao,
        "fila",
        unidade_id=grafo["unidade"],
        especialidade_id=grafo["especialidade"],
        nome="Outra fila",
        descricao_paciente="Fila sintética.",
    )
    criterio = inserir(
        conexao,
        "criterio_fila",
        fila_id=fila,
        codigo="C1",
        descricao="Critério de outra fila",
        tipo="SIM_NAO",
        peso=50,
        origem="PACIENTE",
    )
    return fila, criterio


@pytest.mark.parametrize("fila_declarada", ["da_solicitacao", "do_criterio"])
def test_adr024_resposta_com_criterio_de_outra_fila(conexao, grafo, outra_fila, fila_declarada):
    s = solicitacao(conexao, grafo)
    fila, criterio = outra_fila
    # Declarando a fila da solicitação, falha a FK do critério; declarando a do critério,
    # falha a FK da solicitação. Não há valor de fila_id que aceite a mistura.
    fila_id, restricao = {
        "da_solicitacao": (grafo["fila"], "fk_resposta_criterio_criterio_id_criterio_fila"),
        "do_criterio": (fila, "fk_resposta_criterio_solicitacao_id_solicitacao"),
    }[fila_declarada]

    viola(
        conexao,
        restricao,
        lambda: inserir(
            conexao,
            "resposta_criterio",
            solicitacao_id=s,
            criterio_id=criterio,
            fila_id=fila_id,
            valor=True,
            pontos=50,
        ),
    )


def test_adr024_trocar_fila_de_solicitacao_com_respostas_e_bloqueado(conexao, grafo, outra_fila):
    s = solicitacao(conexao, grafo)
    inserir(
        conexao,
        "resposta_criterio",
        solicitacao_id=s,
        criterio_id=grafo["criterio"],
        fila_id=grafo["fila"],
        valor=True,
        pontos=10,
    )

    viola(
        conexao,
        "fk_resposta_criterio_solicitacao_id_solicitacao",
        "UPDATE solicitacao SET fila_id = :f WHERE id = :id",
        {"f": outra_fila[0], "id": s},
    )


def test_historico_solicitacao_e_append_only(conexao, grafo):
    s = solicitacao(conexao, grafo)
    h = inserir(
        conexao, "historico_solicitacao", solicitacao_id=s, tipo="CRIADA", visivel_paciente=True
    )

    append_only(conexao, "UPDATE historico_solicitacao SET motivo = 'x' WHERE id = :id", {"id": h})
    append_only(conexao, "DELETE FROM historico_solicitacao WHERE id = :id", {"id": h})
    append_only(conexao, "TRUNCATE historico_solicitacao", {})


def test_auditoria_e_append_only(conexao):
    a = inserir(
        conexao,
        "auditoria",
        acao="TESTE",
        entidade="usuario",
        entidade_id="00000000-0000-0000-0000-000000000001",
    )

    append_only(conexao, "UPDATE auditoria SET acao = 'x' WHERE id = :id", {"id": a})
    append_only(conexao, "DELETE FROM auditoria WHERE id = :id", {"id": a})
    append_only(conexao, "TRUNCATE auditoria", {})
