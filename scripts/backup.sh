#!/usr/bin/env bash
# Backup do PostgreSQL pelo serviço `postgres` do compose.
#   scripts/backup.sh                              # dump comprimido (pg_dump -Fc), guarda 7 dias
#   scripts/backup.sh --testar-restauracao [arq]   # restaura num banco temporário e confere (último dump se omitido)
# Pasta: BACKUP_DIR (padrão ~/backups/central-saude-upe), sempre fora do repositório.
# Crontab de exemplo (todo dia às 03:00):
#   0 3 * * * /CAMINHO/DO/REPOSITORIO/scripts/backup.sh >> "$HOME/backups/backup.log" 2>&1
set -euo pipefail

raiz=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)
cd "$raiz"

destino=${BACKUP_DIR:-$HOME/backups/central-saude-upe}
mkdir -p "$destino"
destino=$(cd "$destino" && pwd -P)
case $destino/ in
    "$raiz"/*) echo "BACKUP_DIR não pode ficar dentro do repositório." >&2; exit 1 ;;
esac

# As credenciais vêm do ambiente do próprio contêiner: a senha nunca passa pelo host.
psql_banco() { docker compose exec -T postgres sh -c "psql -U \"\$POSTGRES_USER\" -d $1 -v ON_ERROR_STOP=1 -tAc \"$2\""; }

if [[ ${1:-} == --testar-restauracao ]]; then
    arquivo=${2:-$(find "$destino" -maxdepth 1 -name 'central-*.dump' | sort | tail -n 1)}
    [[ -n $arquivo && -s $arquivo ]] || { echo "Nenhum dump para testar." >&2; exit 1; }
    temp="restore_teste_$(date +%s)"
    # shellcheck disable=SC2329  # chamada pelo trap
    limpar() { docker compose exec -T postgres sh -c "dropdb -U \"\$POSTGRES_USER\" --if-exists $temp" >/dev/null 2>&1 || true; }
    trap limpar EXIT
    docker compose exec -T postgres sh -c "createdb -U \"\$POSTGRES_USER\" $temp"
    docker compose exec -T postgres sh -c "pg_restore -U \"\$POSTGRES_USER\" -d $temp --no-owner --exit-on-error" < "$arquivo"
    tabelas=$(psql_banco "$temp" "select count(*) from information_schema.tables where table_schema='public'")
    versao=$(psql_banco "$temp" "select version_num from alembic_version")
    [[ $tabelas -gt 0 && -n $versao ]] || { echo "Restauração incompleta." >&2; exit 1; }
    echo "OK: $arquivo restaurado em banco temporário ($tabelas tabelas, migração $versao). Banco temporário apagado."
    exit 0
fi

umask 077
arquivo="$destino/central-$(date +%Y%m%d-%H%M%S).dump"
trap 'rm -f "$arquivo.parcial"' EXIT
docker compose exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$arquivo.parcial"
[[ -s $arquivo.parcial ]] || { echo "Dump vazio." >&2; exit 1; }
mv "$arquivo.parcial" "$arquivo"
# Só apaga os antigos depois que o novo existe.
find "$destino" -maxdepth 1 -name 'central-*.dump' -mtime +6 -delete
echo "Backup salvo: $arquivo"
