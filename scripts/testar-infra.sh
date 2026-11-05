#!/usr/bin/env bash
# Testa a infraestrutura sem subir o compose do projeto:
#   1. shellcheck em scripts/*.sh e infra/certbot/*.sh;
#   2. nginx -t com a configuração de produção;
#   3. preparo do certificado dentro do contêiner do certbot, com dono root e permissão 0700
#      (como o certbot cria), executado por usuário comum;
#   4. nginx real contra uma API de mentira: redirect, SPA, cabeçalhos, X-Forwarded-For
#      substituído, erros da API repassados sem alteração (404, 409, 422, 429, 502, 503, 504),
#      Problem Details do próprio nginx (upstream recusando conexão, conexão fechada, 429 do
#      limite) e troca de certificado;
#   5. teste negativo: com proxy_intercept_errors on o teste de erros TEM que falhar.
# Todo recurso criado leva o rótulo $ROTULO e é removido ao sair, inclusive em caso de falha.
# Precisa de Docker (baixa nginx, certbot e shellcheck) e openssl.
set -euo pipefail

raiz=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)
cd "$raiz"
IMAGEM=nginx:stable-alpine
CERTBOT=certbot/certbot
ROTULO="infra-teste=$$"
rede="infra-teste-$$"
rede_b="infra-teste-$$-b"
raiz_nginx="$raiz/infra/nginx"
tmp=$(mktemp -d)

limpar() {
    docker ps -aq --filter "label=$ROTULO" | xargs -r docker rm -f >/dev/null 2>&1 || true
    docker network rm "$rede" "$rede_b" >/dev/null 2>&1 || true
    # Arquivos criados como root pelo contêiner: só um contêiner consegue apagá-los.
    docker run --rm -v "$tmp:/t" "$IMAGEM" rm -rf /t/certbot-certs >/dev/null 2>&1 || true
    rm -rf "$tmp"
}
trap limpar EXIT
trap 'exit 130' INT TERM

falhou() { echo "FALHOU: $*" >&2; exit 1; }
confere() { # confere "descrição" "texto" "trecho esperado" (sem diferença de caixa)
    [[ ${2,,} == *"${3,,}"* ]] || falhou "$1 (esperava '$3', veio: $2)"
    echo "ok: $1"
}
igual() { # igual "descrição" "obtido" "esperado" (valor completo, caixa exata)
    [[ $2 == "$3" ]] || falhou "$1 (esperava '$3', veio '$2')"
    echo "ok: $1"
}

echo "==> shellcheck"
docker run --rm -v "$raiz:/mnt" -w /mnt koalaman/shellcheck:stable scripts/*.sh infra/certbot/*.sh
echo "ok: shellcheck"

echo "==> nginx -t"
mkdir -p "$tmp/certs/live/central" "$tmp/dist"
openssl req -x509 -nodes -newkey rsa:2048 -days 1 -subj "/CN=teste" \
    -keyout "$tmp/certs/live/central/privkey.pem" -out "$tmp/certs/live/central/fullchain.pem" 2>/dev/null
echo '<!doctype html><title>spa</title>' > "$tmp/dist/index.html"
chmod -R a+rX "$tmp"
docker run --rm \
    -v "$raiz_nginx/default.conf:/etc/nginx/conf.d/default.conf:ro" \
    -v "$raiz_nginx/snippets:/etc/nginx/snippets:ro" \
    -v "$tmp/certs:/etc/nginx/certs:ro" -v "$tmp/dist:/usr/share/nginx/html:ro" "$IMAGEM" nginx -t
echo "ok: nginx -t"

echo "==> certificado: preparo dentro do contêiner (root, 0700), rodando como usuário comum"
[[ $(id -u) != 0 ]] || falhou "rode como usuário comum: o teste prova que o host sem root não enxerga o archive/"
certs_root="$tmp/certbot-certs"
mkdir -p "$certs_root"
chmod 755 "$certs_root"
# Estado que o certbot deixa: dono root, archive/ 0700, live/ com symlinks relativos, privkey 0600.
docker run --rm -v "$certs_root:/etc/letsencrypt" --entrypoint sh "$CERTBOT" -c '
    set -e; cd /etc/letsencrypt
    mkdir -p archive/central live/central renewal
    echo antigo > archive/central/fullchain1.pem; echo antigo > archive/central/privkey1.pem
    ln -s ../../archive/central/fullchain1.pem live/central/fullchain.pem
    ln -s ../../archive/central/privkey1.pem live/central/privkey.pem
    echo "# renovação" > renewal/central.conf
    chmod 0700 archive archive/central; chmod 0600 archive/central/*'
if [[ -f $certs_root/live/central/fullchain.pem ]]; then
    falhou "o host enxergou o certificado: o teste não reproduz a permissão 0700 do certbot"
fi
echo "ok: do host, o symlink de live/ é inacessível (verificação pelo host mentiria)"
preparar() { # preparar ação: o mesmo arquivo que o certificado.sh executa no contêiner do certbot
    docker run --rm -v "$certs_root:/etc/letsencrypt" -v "$raiz/infra/certbot:/infra:ro" \
        --entrypoint sh "$CERTBOT" /infra/preparar.sh "$@"
}
preparar existe || falhou "existe: não achou o certificado emitido"
echo "ok: existe vê o certificado (dentro do contêiner)"
preparar temporario
echo "ok: temporario não toca num certificado existente"
preparar limpar
if preparar existe; then falhou "limpar não apagou o certificado"; fi
echo "ok: limpar apagou o conteúdo (existe agora diz que não há)"
docker run --rm -v "$certs_root:/etc/letsencrypt" --entrypoint sh "$CERTBOT" -c \
    'test -d /etc/letsencrypt && test ! -e /etc/letsencrypt/live/central' \
    || falhou "a raiz montada sumiu ou live/central continua lá"
echo "ok: a raiz montada continua; só o conteúdo foi apagado"
preparar temporario
preparar temporario
echo "ok: temporario cria o autoassinado (e é idempotente)"
docker run --rm -v "$certs_root:/etc/nginx/certs:ro" -v "$raiz_nginx/default.conf:/etc/nginx/conf.d/default.conf:ro" \
    -v "$raiz_nginx/snippets:/etc/nginx/snippets:ro" "$IMAGEM" nginx -t >/dev/null 2>&1 \
    || falhou "o nginx não carregou o certificado temporário"
echo "ok: o nginx aceita o certificado temporário (par chave/cert válido)"

echo "==> nginx em funcionamento"
# API de mentira: devolve erros reais, com corpo application/problem+json, e fecha a conexão em /fecha.
{
    echo 'server {'
    echo '    listen 8000;'
    echo '    location ~ /fecha { return 444; }'
    for c in 404 409 422 429 502 503 504; do
        ra=""
        [[ $c == 429 ]] && ra='add_header Retry-After "7" always;'
        [[ $c == 503 ]] && ra='add_header Retry-After "5" always;'
        echo "    location = /api/v1/e/$c { default_type application/problem+json; $ra return $c '{\"type\":\"/problemas/da-api\",\"title\":\"T$c\",\"status\":$c,\"detail\":\"da-api\"}'; }"
    done
    # shellcheck disable=SC2016  # $vars são do nginx da API falsa
    echo '    location / { return 200 "xff=$http_x_forwarded_for proto=$http_x_forwarded_proto"; }'
    echo '}'
} > "$tmp/falsa-api.conf"
docker network create --label "$ROTULO" "$rede" >/dev/null
docker network create --label "$ROTULO" "$rede_b" >/dev/null
docker run -d --label "$ROTULO" --network "$rede" --network-alias api \
    -v "$tmp/falsa-api.conf:/etc/nginx/conf.d/default.conf:ro" "$IMAGEM" >/dev/null
# Rede B: o nome `api` existe, mas nada escuta na 8000 (conexão recusada de verdade).
docker run -d --label "$ROTULO" --network "$rede_b" --network-alias api "$IMAGEM" sleep 3600 >/dev/null

# Sobe um nginx e define NG_ID, NG_HTTP e NG_HTTPS. Chamado direto (sem subshell) para o rótulo valer.
subir_nginx() { # subir_nginx rede conf snippets
    NG_ID=$(docker run -d --label "$ROTULO" --network "$1" -p 127.0.0.1::80 -p 127.0.0.1::443 \
        -v "$2:/etc/nginx/conf.d/default.conf:ro" -v "$3:/etc/nginx/snippets:ro" \
        -v "$tmp/certs:/etc/nginx/certs:ro" -v "$tmp/dist:/usr/share/nginx/html:ro" "$IMAGEM")
    NG_HTTP=$(docker port "$NG_ID" 80/tcp | head -n 1 | sed 's/.*://')
    NG_HTTPS=$(docker port "$NG_ID" 443/tcp | head -n 1 | sed 's/.*://')
    for _ in $(seq 1 20); do curl -ksf -o /dev/null "https://127.0.0.1:$NG_HTTPS/" && break; sleep 0.5; done
}

# buscar URL: grava cabeçalhos em $tmp/h e corpo em $tmp/b; STATUS = código HTTP.
buscar() { STATUS=$(curl -ks -D "$tmp/h" -o "$tmp/b" -w '%{http_code}' "$@"); }
# valor_do_cabecalho nome: todos os valores (um por linha), sem o nome; vazio se não houver.
valor_do_cabecalho() { grep -i "^$1:" "$tmp/h" | tr -d '\r' | sed 's/^[^:]*:[[:space:]]*//' || true; }
# conferir_resposta nome status content-type retry-after corpo: tudo por valor completo, corpo byte a byte.
conferir_resposta() {
    igual "$1: status" "$STATUS" "$2"
    igual "$1: Content-Type" "$(valor_do_cabecalho content-type)" "$3"
    igual "$1: Retry-After" "$(valor_do_cabecalho retry-after)" "$4"
    printf '%s' "$5" | cmp -s - "$tmp/b" || falhou "$1: corpo difere (esperava '$5', veio '$(cat "$tmp/b")')"
    echo "ok: $1: corpo idêntico, byte a byte"
}

PROBLEMA_NGINX='application/problem+json; charset=utf-8'
CORPO_503_NGINX='{"type":"about:blank","title":"Service Unavailable","status":503,"detail":"Serviço indisponível no momento. Tente de novo em instantes."}'

# Erros reais da API têm que chegar iguais: mesmo status, Content-Type, Retry-After e corpo.
# Roda em subshell: falhou() só encerra a checagem.
checar_erros_da_api() { # checar_erros_da_api porta_https
    local c ra
    for c in 404 409 422 429 502 503 504; do
        ra=""
        [[ $c == 429 ]] && ra=7
        [[ $c == 503 ]] && ra=5
        buscar "https://127.0.0.1:$1/api/v1/e/$c"
        conferir_resposta "API $c" "$c" "application/problem+json" "$ra" \
            "{\"type\":\"/problemas/da-api\",\"title\":\"T$c\",\"status\":$c,\"detail\":\"da-api\"}"
    done
}

subir_nginx "$rede" "$raiz_nginx/default.conf" "$raiz_nginx/snippets"
nginx_id=$NG_ID http=$NG_HTTP https=$NG_HTTPS

r=$(curl -si "http://127.0.0.1:$http/api/v1/health")
confere "HTTP redireciona para HTTPS" "$r" "301"
r=$(curl -si "http://127.0.0.1:$http/.well-known/acme-challenge/x")
confere "desafio ACME não redireciona" "$r" "404"

r=$(curl -ksi "https://127.0.0.1:$https/paciente/qualquer-rota")
confere "SPA: rota desconhecida cai no index.html" "$r" "<title>spa</title>"
confere "HSTS" "$r" "Strict-Transport-Security"
confere "CSP" "$r" "frame-ancestors 'none'"
confere "nosniff" "$r" "X-Content-Type-Options: nosniff"
confere "Referrer-Policy" "$r" "Referrer-Policy"

r=$(curl -ks -H 'X-Forwarded-For: 203.0.113.9' "https://127.0.0.1:$https/api/v1/health")
confere "API recebe o proto" "$r" "proto=https"
[[ $r != *203.0.113.9* ]] || falhou "X-Forwarded-For forjado chegou à API: $r"
echo "ok: X-Forwarded-For do cliente é substituído"

( checar_erros_da_api "$https" )

# Upstream que ACEITA a conexão e a fecha sem responder (444 na API falsa): 502 interno, 503 do nginx.
buscar "https://127.0.0.1:$https/api/v1/fecha"
conferir_resposta "upstream aceita e fecha a conexão" 503 "$PROBLEMA_NGINX" 10 "$CORPO_503_NGINX"

# Upstream que RECUSA a conexão (nada escuta na 8000 da rede B): Problem Details do próprio nginx.
subir_nginx "$rede_b" "$raiz_nginx/default.conf" "$raiz_nginx/snippets"
buscar "https://127.0.0.1:$NG_HTTPS/api/v1/health"
conferir_resposta "upstream recusa a conexão" 503 "$PROBLEMA_NGINX" 10 "$CORPO_503_NGINX"

# 5 r/s com burst 40 em /auth/: a rajada estoura o limite. Valida-se o PRÓPRIO 429 da rajada
# (uma requisição posterior dependeria do tempo: o limite se recupera a 5 por segundo).
for i in $(seq 1 300); do
    buscar "https://127.0.0.1:$https/api/v1/auth/x$i"
    [[ $STATUS == 429 ]] && break
done
[[ $STATUS == 429 ]] || falhou "a rajada de 300 requisições em /auth/ não recebeu 429"
echo "ok: a rajada em /auth/ recebeu 429 (na requisição $i)"
conferir_resposta "429 do limite do nginx" 429 "$PROBLEMA_NGINX" 30 \
    '{"type":"/problemas/muitas-tentativas","title":"Too Many Requests","status":429,"detail":"Muitas tentativas. Aguarde alguns minutos e tente de novo."}'
sleep 10
r=$(curl -ks -o /dev/null -w '%{http_code}' "https://127.0.0.1:$https/api/v1/health")
igual "rota fora do /auth/ não foi limitada" "$r" "200"

echo "==> troca de certificado"
assunto() { echo | openssl s_client -connect "127.0.0.1:$https" 2>/dev/null | openssl x509 -noout -subject; }
confere "serve o certificado inicial" "$(assunto)" "teste"
# Troca só o CONTEÚDO de certs/ (como o certificado.sh --substituir); a raiz montada não é recriada.
rm -rf "$tmp/certs/live"
mkdir -p "$tmp/certs/live/central"
openssl req -x509 -nodes -newkey rsa:2048 -days 1 -subj "/CN=novo-certificado" \
    -keyout "$tmp/certs/live/central/privkey.pem" -out "$tmp/certs/live/central/fullchain.pem" 2>/dev/null
chmod -R a+rX "$tmp/certs"
docker exec "$nginx_id" nginx -s reload >/dev/null 2>&1
sleep 1
confere "depois da troca o nginx serve o certificado novo" "$(assunto)" "novo-certificado"

echo "==> teste negativo: proxy_intercept_errors on tem que FALHAR"
mkdir -p "$tmp/neg"
cp -r "$raiz_nginx/snippets" "$tmp/neg/snippets"
cp "$raiz_nginx/default.conf" "$tmp/neg/default.conf"
echo "proxy_intercept_errors on;" >> "$tmp/neg/snippets/proxy-api.conf"
chmod -R a+rX "$tmp/neg"
subir_nginx "$rede" "$tmp/neg/default.conf" "$tmp/neg/snippets"
https_neg=$NG_HTTPS
if saida=$( ( checar_erros_da_api "$https_neg" ) 2>&1 ); then
    echo "$saida"
    falhou "o teste de erros passou com proxy_intercept_errors on: ele não detecta o defeito"
fi
echo "$saida" | grep -m1 "^FALHOU" | cut -c1-140
echo "ok: teste negativo falhou como esperado (o teste detecta proxy_intercept_errors on)"

echo "Infraestrutura OK."
