"""Contrato OpenAPI que o frontend consome: erros, enums, segurança e snapshot."""

import json
import os
from enum import StrEnum

import pytest
from starlette.routing import Match

from app.api import tipos
from app.api.main import ROTAS_SEM_CSRF, app
from app.dominio import vocabulario
from app.dominio.notificacoes.avisos import TIPOS_AVISO
from tests.conftest import ERROS_PROVOCADOS
from tests.raiz import raiz_do_repositorio

RAIZ = raiz_do_repositorio()
SNAPSHOT = RAIZ / "docs/architecture/openapi.json" if RAIZ else None
ESQUEMA = app.openapi()
OPERACOES = [
    (metodo.upper(), caminho, operacao)
    for caminho, operacoes in ESQUEMA["paths"].items()
    for metodo, operacao in operacoes.items()
]

# schema do OpenAPI -> constante do domínio (a única definição dos valores)
ENUMS = {
    "Papel": vocabulario.PAPEIS,
    "StatusSolicitacao": vocabulario.STATUS_SOLICITACAO,
    "StatusAgendamento": vocabulario.STATUS_AGENDAMENTO,
    "ClassificacaoRisco": vocabulario.RISCOS,
    "Turno": vocabulario.TURNOS,
    "MotivoCancelamento": tuple(vocabulario.MOTIVOS_CANCELAMENTO),
    "TipoEventoLinhaDoTempo": vocabulario.TIPOS_HISTORICO,
    "TipoAviso": TIPOS_AVISO,
    "SituacaoVaga": vocabulario.SITUACOES_VAGA,
    "TipoCriterio": vocabulario.TIPOS_CRITERIO,
    "OrigemCriterio": vocabulario.ORIGENS_CRITERIO,
}


@pytest.mark.parametrize(("schema", "valores"), ENUMS.items())
def test_enum_do_openapi_tem_exatamente_os_valores_do_dominio(schema, valores):
    assert ESQUEMA["components"]["schemas"][schema]["enum"] == list(valores)
    assert issubclass(getattr(tipos, schema), StrEnum)


def test_todo_enum_do_contrato_esta_na_tabela():
    nomes = {n for n, s in ESQUEMA["components"]["schemas"].items() if "enum" in s}
    assert nomes == ENUMS.keys()


def test_campos_de_vocabulario_nao_sao_string_livre():
    livres = {
        (nome, campo)
        for nome, schema in ESQUEMA["components"]["schemas"].items()
        for campo, prop in schema.get("properties", {}).items()
        if campo in {"papel", "status", "turno_preferido", "classificacao_risco", "motivo_codigo"}
        and prop.get("type") == "string"
        and "enum" not in prop
    }
    assert not livres


def test_erros_sao_problem_details_e_sem_http_validation_error():
    schemas = ESQUEMA["components"]["schemas"]
    assert {"Problema"} <= schemas.keys()
    assert not {"HTTPValidationError", "ValidationError"} & schemas.keys()
    assert {"type", "title", "status"} <= set(schemas["Problema"]["required"])
    for metodo, caminho, operacao in OPERACOES:
        for status, resposta in operacao["responses"].items():
            if int(status) >= 400:
                assert list(resposta["content"]) == ["application/problem+json"], (
                    metodo,
                    caminho,
                    status,
                )


@pytest.mark.parametrize(
    ("metodo", "caminho", "operacao"), OPERACOES, ids=[f"{m} {c}" for m, c, _ in OPERACOES]
)
def test_escrita_declara_o_csrf_e_rota_autenticada_declara_o_cookie(metodo, caminho, operacao):
    exigencias = operacao.get("security", [])
    publica = caminho in {
        "/api/v1/health",
        "/api/v1/termos/vigente",
        "/api/v1/auth/registro",
        "/api/v1/auth/login",
    }
    exige_csrf = metodo in {"POST", "PUT", "PATCH", "DELETE"} and caminho not in ROTAS_SEM_CSRF
    assert bool(exigencias) != publica
    if exigencias:
        assert all("csrfToken" in e for e in exigencias) == exige_csrf
    if exige_csrf:
        assert "403" in operacao["responses"]


def test_toda_rota_autenticada_declara_o_403_de_troca_de_senha_obrigatoria():
    sem_troca = {"/api/v1/me", "/api/v1/auth/trocar-senha"}
    autenticadas = [
        (m, c, o)
        for m, c, o in OPERACOES
        if any("cookieSessao" in e for e in o.get("security", [])) and c not in sem_troca
    ]
    assert autenticadas
    for metodo, caminho, operacao in autenticadas:
        assert "troca-de-senha-obrigatoria" in operacao["responses"]["403"]["description"], (
            metodo,
            caminho,
        )
    for caminho in sem_troca:
        for operacao in ESQUEMA["paths"][caminho].values():
            assert "troca-de-senha-obrigatoria" not in operacao["responses"].get("403", {}).get(
                "description", ""
            )


@pytest.mark.ultimo
def test_erros_que_os_testes_provocam_estao_declarados():
    """Cada status de erro que a suíte provocou numa rota consta nas respostas dela."""
    if not ERROS_PROVOCADOS:
        pytest.skip("só confere com a suíte inteira (nenhum teste provocou erro antes)")
    faltando = []
    for metodo, caminho, status in sorted(ERROS_PROVOCADOS):
        escopo = {"type": "http", "path": caminho, "method": metodo}
        rota = next(
            (r for r in app.routes if r.matches(escopo)[0] == Match.FULL and hasattr(r, "path")),
            None,
        )
        operacao = ESQUEMA["paths"].get(getattr(rota, "path_format", ""), {}).get(metodo.lower())
        if operacao and str(status) not in operacao["responses"]:
            faltando.append(f"{metodo} {rota.path_format} -> {status}")
    assert not faltando, "erros não declarados em responses=erros(...):\n" + "\n".join(faltando)


@pytest.mark.skipif(SNAPSHOT is None, reason="docs/ fora da imagem")
def test_snapshot_do_openapi_esta_atualizado():
    """Falha se o contrato mudou sem `docs/architecture/openapi.json` acompanhar.
    Regenere com `ATUALIZAR_OPENAPI=1 scripts/testar.sh tests/test_contrato.py`."""
    atual = json.dumps(ESQUEMA, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    if os.environ.get("ATUALIZAR_OPENAPI") == "1":
        SNAPSHOT.write_text(atual, encoding="utf-8")
    assert SNAPSHOT.exists(), "gere o snapshot com ATUALIZAR_OPENAPI=1"
    assert json.loads(SNAPSHOT.read_text(encoding="utf-8")) == ESQUEMA, (
        "o contrato mudou: rode com ATUALIZAR_OPENAPI=1 e avise o frontend"
    )
