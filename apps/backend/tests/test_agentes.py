"""Agentes do Claude Code (.md) e do Codex (.toml) não podem divergir."""

import tomllib

import pytest

from tests.raiz import raiz_do_repositorio

RAIZ = raiz_do_repositorio()
pytestmark = pytest.mark.skipif(
    RAIZ is None, reason="raiz do repositório (.claude/, .codex/) fora da imagem"
)
MDS = {p.stem: p for p in (RAIZ / ".claude/agents").glob("*.md")} if RAIZ else {}
TOMLS = {p.stem: p for p in (RAIZ / ".codex/agents").glob("*.toml")} if RAIZ else {}
SOMENTE_LEITURA = "Você é SOMENTE LEITURA: nunca crie, edite ou apague arquivos"


def test_agentes_mesmos_nomes_nas_duas_ferramentas():
    assert MDS
    assert MDS.keys() == TOMLS.keys()


@pytest.mark.parametrize("nome", sorted(MDS))
def test_agente_toml_espelha_md(nome):
    _, fm, corpo = MDS[nome].read_text().split("---\n", 2)
    meta = dict(linha.split(": ", 1) for linha in fm.strip().splitlines())
    toml = tomllib.loads(TOMLS[nome].read_text())

    assert toml["name"] == nome.replace("-", "_")
    assert toml["description"] == meta["description"]
    assert "model" not in toml
    # CLAUDE.md -> AGENTS.md é a única troca de texto no corpo
    assert corpo.strip().replace("CLAUDE.md", "AGENTS.md") in toml["developer_instructions"]
    assert "não faça commit, push nem crie branch" in toml["developer_instructions"].lower()
    assert nome.startswith("revisor") == (SOMENTE_LEITURA in toml["developer_instructions"])
