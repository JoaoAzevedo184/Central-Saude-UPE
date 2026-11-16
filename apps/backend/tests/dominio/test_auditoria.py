"""Função pura que monta os campos da consulta da auditoria (RF-023, RN-010)."""

from datetime import date

import pytest

from app.dominio.auditoria import (
    OCULTOS,
    PERMITIDAS,
    VALIDADORES,
    CampoAuditoria,
    montar_campos,
    verificar_data_da_consulta,
)
from app.dominio.erros import EntradaInvalida

UUID_X = "11111111-2222-3333-4444-555555555555"
EXEMPLOS = {
    "status": "NA_FILA",
    "classificacao_risco": "AMARELO",
    "data_entrada_fila": "2026-10-19T12:00:00+00:00",
    "respondido_em": "2026-10-19T12:00:00+00:00",
    "confirmado_em": "2026-10-19T12:00:00+00:00",
    "motivo_cancelamento": "CANCELADO_PELO_PACIENTE",
    "solicitacao_id": UUID_X,
    "vaga_id": UUID_X,
    "expira_em": "2026-10-21T12:00:00+00:00",
    "papel": "ATENDENTE",
    "unidades": [UUID_X],
    "origem": "terminal",
    "filas": [UUID_X],
    "visao_central": True,
    "situacao": "SUSPENSO",
    "consentimentos": ["AGENDAMENTO"],
    "versao_termo": "v1",
    "ordenacao": "prioridade",
    "limit": 50,
    "offset": 0,
    "data": "2026-10-19",
    "de": "2026-10-05",
    "ate": "2026-10-18",
    "unidade_id": UUID_X,
    "fila_id": None,
    "entidade": "fila",
    "entidade_id": UUID_X,
    "acao": "CLASSIFICAR",
    "ator_usuario_id": None,
}


@pytest.mark.parametrize("acao", sorted(PERMITIDAS))
def test_rf023_cada_acao_devolve_seus_campos_na_ordem_da_lista_permitida(acao):
    chaves = PERMITIDAS[acao]
    assert all(c in EXEMPLOS for c in chaves), "falta exemplo"
    depois = {c: EXEMPLOS[c] for c in reversed(chaves)} | {c: 7 for c in OCULTOS[acao]}

    campos, omitidos = montar_campos(acao, None, depois)

    assert omitidos is False
    assert [c.campo for c in campos] == [*chaves, *OCULTOS[acao]]
    for c in campos:
        assert c.oculto == (c.campo in OCULTOS[acao])
        assert c.antes is None
        assert c.depois == (None if c.oculto else EXEMPLOS[c.campo])


def test_rf023_antes_e_depois_saem_lado_a_lado():
    campos, omitidos = montar_campos("SUSPENDER", {"situacao": "ATIVO"}, {"situacao": "SUSPENSO"})
    assert campos == [CampoAuditoria("situacao", "ATIVO", "SUSPENSO", False)]
    assert omitidos is False


def test_rf023_nota_e_respostas_aparecem_ocultas_sem_ligar_a_flag():
    campos, omitidos = montar_campos(
        "RESPONDER_CRITERIOS",
        {"respostas": {"a": 1}, "nota": 10},
        {"respostas": {"a": 2}, "nota": 20},
    )
    assert campos == [
        CampoAuditoria("respostas", None, None, True),
        CampoAuditoria("nota", None, None, True),
    ]
    assert omitidos is False


def test_rf023_chave_inesperada_liga_a_flag_e_nao_sai():
    campos, omitidos = montar_campos("CLASSIFICAR", None, {"status": "NA_FILA", "ip": "1.2.3.4"})
    assert [c.campo for c in campos] == ["status"]
    assert omitidos is True


def test_rf023_ip_nunca_e_campo_nem_oculto():
    assert all("ip" not in chaves for chaves in PERMITIDAS.values())
    assert all("ip" not in chaves for chaves in OCULTOS.values())


def test_rf023_acao_desconhecida_devolve_vazio_e_liga_a_flag():
    assert montar_campos("ACAO_NOVA", {"x": 1}, {"y": 2}) == ([], True)


def test_rf023_todo_campo_permitido_tem_validador():
    campos = {c for chaves in PERMITIDAS.values() for c in chaves}
    assert campos <= set(VALIDADORES)


def test_rf023_campo_sem_validador_e_reprovado(monkeypatch):
    monkeypatch.setitem(PERMITIDAS, "ACAO_TESTE", ("campo_novo",))
    monkeypatch.setitem(OCULTOS, "ACAO_TESTE", ())
    assert montar_campos("ACAO_TESTE", None, {"campo_novo": "NA_FILA"}) == ([], True)


# (acao, campo, valor): todos descartados, com detalhes_omitidos=True.
REPROVADOS = [
    ("CLASSIFICAR", "status", 10**100),
    ("CLASSIFICAR", "status", True),
    ("CLASSIFICAR", "status", 1),
    ("CLASSIFICAR", "status", "MARIA_SINTETICA"),
    ("CLASSIFICAR", "status", ""),
    ("CLASSIFICAR", "status", ["NA_FILA"]),
    ("CLASSIFICAR", "status", {"a": 1}),
    ("CLASSIFICAR", "classificacao_risco", "MARIA_SINTETICA"),
    ("CLASSIFICAR", "data_entrada_fila", "Maria Sintética"),
    ("CLASSIFICAR", "data_entrada_fila", "2026-13-45"),
    ("CLASSIFICAR", "data_entrada_fila", 20261019),
    ("CONFIRMAR_AGENDAMENTO", "motivo_cancelamento", "MARIA_SINTETICA"),
    ("CRIAR_USUARIO", "papel", "MARIA_SINTETICA"),
    ("CRIAR_USUARIO", "unidades", ["MARIA_SINTETICA"]),
    ("CRIAR_USUARIO", "unidades", [UUID_X, {"a": 1}]),
    ("CRIAR_USUARIO", "unidades", UUID_X),
    ("CRIAR_USUARIO", "unidades", [UUID_X] * 501),
    ("ATRIBUIR_FILAS", "filas", ["não-é-uuid"]),
    ("ATRIBUIR_FILAS", "filas", [[UUID_X]]),
    ("ATRIBUIR_UNIDADES", "visao_central", 1),
    ("ATRIBUIR_UNIDADES", "visao_central", 0),
    ("ATRIBUIR_UNIDADES", "visao_central", "true"),
    ("SUSPENDER", "situacao", "MARIA_SINTETICA"),
    ("REGISTRO", "consentimentos", ["MARIA_SINTETICA"]),
    ("REGISTRO", "versao_termo", "Maria Sintética"),
    ("REGISTRO", "versao_termo", ""),
    ("REDEFINIR_SENHA", "origem", "MARIA_SINTETICA"),
    ("CONSULTAR_PAINEL", "ordenacao", "MARIA_SINTETICA"),
    ("CONSULTAR_PAINEL", "limit", True),
    ("CONSULTAR_PAINEL", "limit", 10**100),
    ("CONSULTAR_PAINEL", "limit", -1),
    ("CONSULTAR_PAINEL", "limit", 10_001),
    ("CONSULTAR_PAINEL", "offset", 1.5),
    ("CONSULTAR_PAINEL", "status", "MARIA_SINTETICA"),
    ("CONSULTAR_INDICADORES", "fila_id", "MARIA_SINTETICA"),
    ("CONSULTAR_INDICADORES", "de", "texto livre"),
    ("CONSULTAR_AUDITORIA", "entidade", "MARIA_SINTETICA"),
    ("CONSULTAR_AUDITORIA", "acao", "MARIA_SINTETICA"),
    ("CONSULTAR_AUDITORIA", "ator_usuario_id", "MARIA_SINTETICA"),
]


@pytest.mark.parametrize(("acao", "campo", "valor"), REPROVADOS)
def test_rf023_valor_reprovado_e_descartado_e_liga_a_flag(acao, campo, valor):
    for antes, depois in (({campo: valor}, None), (None, {campo: valor})):
        campos, omitidos = montar_campos(acao, antes, depois)
        assert campos == [] and omitidos is True


@pytest.mark.parametrize(
    ("acao", "campo", "valor"),
    [
        ("CLASSIFICAR", "status", None),
        ("CLASSIFICAR", "status", "NA_FILA"),
        ("CONFIRMAR_AGENDAMENTO", "status", "CONFIRMADO"),
        ("CLASSIFICAR", "data_entrada_fila", "2026-10-19T12:00:00Z"),
        ("CONSULTAR_VAGAS", "de", "2026-10-19"),
        ("CONFIRMAR_AGENDAMENTO", "motivo_cancelamento", "RECUSADO_PELO_PACIENTE"),
        ("CANCELAR_SOLICITACAO", "motivo_cancelamento", "NAO_PRECISO_MAIS"),
        ("ATRIBUIR_UNIDADES", "visao_central", False),
        ("CONSULTAR_PAINEL", "limit", 0),
        ("CONSULTAR_PAINEL", "limit", 10_000),
        ("ATRIBUIR_FILAS", "filas", []),
        ("ATRIBUIR_FILAS", "filas", [UUID_X]),
        ("REGISTRO", "consentimentos", ["AGENDAMENTO", "LEMBRETE_EMAIL"]),
        ("REGISTRO", "versao_termo", "v1.0-2026"),
    ],
)
def test_rf023_valor_valido_passa(acao, campo, valor):
    campos, omitidos = montar_campos(acao, None, {campo: valor})
    assert [c.depois for c in campos] == [valor] and omitidos is False


@pytest.mark.parametrize("dia", [date(1999, 12, 31), date.min, date(2101, 1, 1), date.max])
def test_rf023_data_fora_do_intervalo_e_recusada(dia):
    with pytest.raises(EntradaInvalida):
        verificar_data_da_consulta(dia)
