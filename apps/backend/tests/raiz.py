from pathlib import Path


def raiz_do_repositorio() -> Path | None:
    """Raiz do repositório, ou None se não estiver acessível (ex.: dentro da imagem, em /app)."""
    for pai in Path(__file__).resolve().parents:
        if all((pai / alvo).exists() for alvo in (".claude", ".codex", ".env.example")):
            return pai
    return None
