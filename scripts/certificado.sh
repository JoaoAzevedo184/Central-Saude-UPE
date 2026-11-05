#!/usr/bin/env bash
# Certificado Let's Encrypt para o nginx do compose (desafio HTTP-01, webroot).
#   scripts/certificado.sh emitir [--staging] [--substituir]
#                       # 1ª emissão (--staging é só ensaio, cert não confiável);
#                       # --substituir troca um certificado já emitido (ex.: staging -> produção)
#   scripts/certificado.sh testar-renovacao     # certbot renew --dry-run + reload do nginx
# Lê DOMINIO e EMAIL_DO_CERTIFICADO do .env. A renovação real é o serviço `certbot` (perfil certbot).
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

ler() {
    local valor
    valor=$(grep -m1 "^$1=" .env | cut -d= -f2- || true)
    valor=${valor%\"}; valor=${valor#\"}
    printf '%s' "${valor:-${2:-}}"
}

certbot() {
    docker compose --profile certbot run --rm --entrypoint certbot certbot "$@"
}

# Verificação, limpeza e certificado temporário rodam DENTRO do contêiner (root): o certbot cria
# archive/ com 0700, então do host o symlink de live/ fica inacessível. Nada disso passa pelo host.
no_certbot() {
    docker compose --profile certbot run --rm --entrypoint sh certbot /infra/preparar.sh "$@"
}

comando=${1:-}
[[ -f .env ]] || { echo "Sem .env na raiz." >&2; exit 1; }

case $comando in
    emitir)
        staging=(); substituir=0
        for flag in "${@:2}"; do
            case $flag in
                --staging) staging=(--staging) ;;
                --substituir) substituir=1 ;;
                *) echo "Flag desconhecida: $flag" >&2; exit 2 ;;
            esac
        done
        dominio=$(ler DOMINIO); email=$(ler EMAIL_DO_CERTIFICADO)
        if [[ -z $dominio || $dominio == SEU_DOMINIO || -z $email || $email == EMAIL_DO_CERTIFICADO ]]; then
            echo "Defina DOMINIO e EMAIL_DO_CERTIFICADO no .env." >&2
            exit 1
        fi
        if [[ $substituir == 0 ]] && no_certbot existe; then
            echo "Já existe certificado emitido. Para ensaiar a renovação: scripts/certificado.sh testar-renovacao"
            echo "Para trocar (por exemplo, de staging para produção): scripts/certificado.sh emitir --substituir"
            exit 0
        fi
        # O nginx não sobe sem certificado: cria um autoassinado de 1 dia (e recria um se a emissão falhar).
        no_certbot temporario
        docker compose --profile proxy up -d nginx
        # O certbot não adota um diretório que ele não criou. Limpa só o CONTEÚDO de certs/ (live,
        # archive, renewal). Nunca apague nem recrie a raiz infra/nginx/certs: o nginx a monta, e um
        # diretório novo no mesmo caminho deixa o contêiner olhando o antigo.
        no_certbot limpar
        if ! certbot certonly --webroot -w /var/www/certbot --cert-name central \
            -d "$dominio" -m "$email" --agree-tos --no-eff-email --non-interactive "${staging[@]}"; then
            no_certbot temporario
            echo "Emissão falhou. O certificado temporário foi recriado para o nginx poder reiniciar." >&2
            exit 1
        fi
        # Recria o contêiner (não só reload): garante que ele enxergue os arquivos novos.
        docker compose --profile proxy up -d --force-recreate nginx
        echo "Certificado emitido. Suba a renovação automática com: scripts/deploy.sh"
        ;;
    testar-renovacao)
        certbot renew --dry-run --webroot -w /var/www/certbot
        docker compose exec -T nginx nginx -s reload
        echo "Renovação simulada OK e nginx recarregado."
        ;;
    *)
        echo "Uso: scripts/certificado.sh emitir [--staging] [--substituir] | testar-renovacao" >&2
        exit 2
        ;;
esac
