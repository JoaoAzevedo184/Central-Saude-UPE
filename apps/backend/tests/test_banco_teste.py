from pathlib import Path

from tests.banco_teste import nome_banco_teste, raiz_git


def checkout(tmp_path: Path) -> Path:
    (tmp_path / ".git").mkdir()
    return tmp_path


def worktree(tmp_path: Path, nome: str) -> Path:
    raiz = tmp_path / nome
    raiz.mkdir(exist_ok=True)
    (raiz / ".git").write_text("gitdir: /algum/lugar/.git/worktrees/x\n")
    return raiz


def test_checkout_principal_mantem_o_nome_atual(tmp_path):
    assert nome_banco_teste("teleagendamento", checkout(tmp_path), {}) == "teleagendamento_test"


def test_sem_repositorio_git_mantem_o_nome_atual():
    assert nome_banco_teste("teleagendamento", None, {}) == "teleagendamento_test"


def test_worktree_usa_o_nome_da_pasta(tmp_path):
    raiz = worktree(tmp_path, "feature-UC-004")
    assert nome_banco_teste("teleagendamento", raiz, {}) == "teleagendamento_test_feature_uc_004"


def test_variavel_vence_o_worktree(tmp_path):
    raiz = worktree(tmp_path, "outro")
    env = {"TEST_DB_SUFIXO": "Ana"}
    assert nome_banco_teste("teleagendamento", raiz, env) == "teleagendamento_test_ana"


def test_variavel_vale_tambem_no_checkout_principal(tmp_path):
    env = {"TEST_DB_SUFIXO": "ana"}
    assert (
        nome_banco_teste("teleagendamento", checkout(tmp_path), env) == "teleagendamento_test_ana"
    )


def test_caracteres_especiais_viram_sublinhado(tmp_path):
    raiz = worktree(tmp_path, "fix é ç;DROP-x")
    nome = nome_banco_teste("teleagendamento", raiz, {})
    assert nome.startswith("teleagendamento_test_")
    assert nome.replace("_", "").isalnum() and nome == nome.lower()


def test_nome_longo_fica_em_63_caracteres_com_hash_estavel(tmp_path):
    a = nome_banco_teste("teleagendamento", worktree(tmp_path, "a" * 80), {})
    b = nome_banco_teste("teleagendamento", worktree(tmp_path, "a" * 79 + "b"), {})
    assert len(a) == len(b) == 63
    assert a != b  # o hash separa nomes que só diferem no trecho cortado
    assert a == nome_banco_teste("teleagendamento", worktree(tmp_path, "a" * 80), {})


def test_raiz_git_sobe_ate_o_git(tmp_path):
    raiz = checkout(tmp_path)
    fundo = raiz / "apps" / "backend"
    fundo.mkdir(parents=True)
    assert raiz_git(fundo) == raiz
