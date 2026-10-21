import hashlib
import os
import re
from pathlib import Path

LIMITE_POSTGRES = 63


def raiz_git(inicio: Path) -> Path | None:
    """Pasta que contém o `.git` (pasta no checkout principal, arquivo num worktree vinculado)."""
    for pai in (inicio, *inicio.parents):
        if (pai / ".git").exists():
            return pai
    return None


def sufixo_do_worktree(raiz: Path | None) -> str:
    if raiz is not None and (raiz / ".git").is_file():
        return raiz.name
    return ""


def nome_banco_teste(base: str, raiz: Path | None, env: dict[str, str] | None = None) -> str:
    """`<base>_test` + sufixo: TEST_DB_SUFIXO, ou a pasta do worktree vinculado; nenhum no
    checkout principal, no CI e no container. Passa de 63 caracteres: corta e põe um hash."""
    env = os.environ if env is None else env
    sufixo = env.get("TEST_DB_SUFIXO") or sufixo_do_worktree(raiz)
    sufixo = re.sub(r"[^a-z0-9_]", "_", sufixo.lower())
    nome = f"{base}_test" + (f"_{sufixo}" if sufixo else "")
    if len(nome) > LIMITE_POSTGRES:
        curto = hashlib.sha1(nome.encode()).hexdigest()[:8]
        nome = f"{nome[: LIMITE_POSTGRES - 9]}_{curto}"
    return nome
