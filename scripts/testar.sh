#!/usr/bin/env bash
# Roda o pytest no host a partir de qualquer worktree, contra o Postgres do checkout principal.
#   scripts/testar.sh [args do pytest]
#   scripts/testar.sh --limpar-bancos-orfaos     # lista e apaga (com confirmação) bancos _test_* órfãos
set -euo pipefail

principal=$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")
env_principal="$principal/.env"
raiz=$(git rev-parse --show-toplevel)

if [[ ! -f $env_principal ]]; then
    echo "Sem .env em $principal. Crie-o no checkout principal: cp .env.example .env" >&2
    exit 1
fi

# Lê só a chave pedida; nunca faz `source` do arquivo e nunca imprime valores.
ler() {
    local valor
    valor=$(grep -m1 "^$1=" "$env_principal" | cut -d= -f2- || true)
    valor=${valor%\"}; valor=${valor#\"}
    printf '%s' "${valor:-${2:-}}"
}

usuario=$(ler POSTGRES_USER); senha=$(ler POSTGRES_PASSWORD)
banco=$(ler POSTGRES_DB); porta=$(ler POSTGRES_PORT_HOST 5432)
if [[ -z $usuario || -z $senha || -z $banco ]]; then
    echo "POSTGRES_USER, POSTGRES_PASSWORD e POSTGRES_DB precisam estar no .env do checkout principal." >&2
    exit 1
fi

if ! (exec 3<>"/dev/tcp/127.0.0.1/$porta") 2>/dev/null; then
    echo "Postgres fora do ar em 127.0.0.1:$porta. Suba no checkout principal:" >&2
    echo "  cd $principal && docker compose up -d postgres" >&2
    exit 1
fi

DATABASE_URL=$(python3 -c '
import sys
from urllib.parse import quote
u, s, b, p = sys.argv[1:]
print("postgresql+psycopg://" + quote(u, safe="") + ":" + quote(s, safe="") + "@127.0.0.1:" + p + "/" + b)
' "$usuario" "$senha" "$banco" "$porta")
export DATABASE_URL
export APP_ENV=test
cd "$raiz/apps/backend"

if [[ ${1:-} == --limpar-bancos-orfaos ]]; then
    # worktrees vivos (menos o principal): o nome do banco de cada um vem da mesma função dos testes
    mapfile -t vivos < <(git worktree list --porcelain | sed -n 's/^worktree //p' | grep -vxF "$principal" || true)
    orfaos() {
        uv run python -c '
import os, sys
from pathlib import Path
from sqlalchemy import create_engine, make_url, text
from tests.banco_teste import nome_banco_teste
url = make_url(os.environ["DATABASE_URL"])
vivos = {nome_banco_teste(url.database, Path(p), {}) for p in sys.argv[2:]}
motor = create_engine(url, isolation_level="AUTOCOMMIT")
with motor.connect() as c:
    nomes = [r[0] for r in c.execute(
        text("select datname from pg_database where datname like :p order by 1"),
        {"p": url.database.replace("_", "\\_") + "\\_test\\_%"})]
    nomes = [n for n in nomes if n not in vivos]
    for n in nomes:
        print(n)
        if sys.argv[1] == "apagar":
            c.execute(text("DROP DATABASE " + chr(34) + n + chr(34) + " WITH (FORCE)"))
' "$1" "${vivos[@]}"
    }
    lista=$(orfaos listar)
    if [[ -z $lista ]]; then echo "Nenhum banco órfão."; exit 0; fi
    echo "Bancos órfãos:"; echo "$lista"
    read -r -p "Apagar todos? [s/N] " resposta
    if [[ $resposta == [sS] ]]; then orfaos apagar >/dev/null; echo "Apagados."; else echo "Nada apagado."; fi
    exit 0
fi

# Uma execução por worktree por vez: o conftest recria o banco de teste (DROP ... WITH (FORCE)),
# então duas execuções simultâneas derrubam as conexões uma da outra. A segunda espera a primeira.
trava="${TMPDIR:-/tmp}/testar-$(printf '%s' "$raiz" | cksum | cut -d' ' -f1).lock"
exec 9>"$trava"
if ! flock -n 9; then
    echo "Outra execução de testes neste worktree está em andamento; aguardando..." >&2
    flock 9
fi
uv run pytest "$@"
