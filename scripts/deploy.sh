#!/usr/bin/env bash
# Atualiza a produção: código, imagens, frontend, migração, serviços e healthcheck por HTTPS.
# Roda no checkout principal do servidor. Pré-requisito do 1º deploy: scripts/certificado.sh emitir.
#   scripts/deploy.sh
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

# Lê só a chave pedida do .env; nunca faz `source` e nunca imprime valores.
ler() {
    local valor
    valor=$(grep -m1 "^$1=" .env | cut -d= -f2- || true)
    valor=${valor%\"}; valor=${valor#\"}
    printf '%s' "${valor:-${2:-}}"
}

[[ -f .env ]] || { echo "Sem .env na raiz. Crie-o a partir do .env.example." >&2; exit 1; }
[[ $(ler APP_ENV) == production ]] || { echo "APP_ENV precisa ser production no .env." >&2; exit 1; }
dominio=$(ler DOMINIO)
if [[ -z $dominio || $dominio == SEU_DOMINIO ]]; then
    echo "Defina DOMINIO no .env." >&2
    exit 1
fi
# Verifica por dentro do contêiner (root): do host, o archive/ do certbot (0700) é inacessível.
docker compose --profile certbot run --rm --entrypoint sh certbot /infra/preparar.sh existe || {
    echo "Sem certificado emitido. Rode: scripts/certificado.sh emitir" >&2
    exit 1
}
[[ $(git rev-parse --abbrev-ref HEAD) == main ]] || { echo "Deploy só da branch main." >&2; exit 1; }

echo "==> 1/6 Atualizando o código (ff-only)"
git pull --ff-only origin main

echo "==> 2/6 Construindo as imagens"
docker compose --profile proxy --profile certbot --profile build build

echo "==> 3/6 Construindo o frontend"
docker compose --profile build run --rm web-build

echo "==> 4/6 Aplicando as migrações"
docker compose run --rm migrate

echo "==> 5/6 Subindo os serviços"
docker compose --profile proxy --profile certbot up -d --remove-orphans
# O nginx já pode estar de pé com o dist antigo: recarrega para garantir config e certificado atuais.
docker compose exec -T nginx nginx -s reload

echo "==> 6/6 Healthcheck em https://$dominio/api/v1/health"
# --resolve evita depender do DNS ou de hairpin NAT: testa o nginx local, com o certificado real.
for _ in $(seq 1 30); do
    if curl -fsS --max-time 5 --resolve "$dominio:443:127.0.0.1" "https://$dominio/api/v1/health" >/dev/null 2>&1; then
        echo "OK: aplicação no ar."
        exit 0
    fi
    sleep 2
done
echo "FALHOU: sem resposta saudável em 60 s. Veja: docker compose logs --tail 50 nginx api" >&2
exit 1
