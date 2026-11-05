#!/bin/sh
# Roda DENTRO do contêiner certbot (root). Toda verificação, limpeza e criação de certificado passa
# por aqui, nunca pelo host: o certbot cria archive/ com permissão 0700 (dono root), então do host o
# symlink de live/ fica inacessível e `test -f` mente.
#   preparar.sh existe       # sai 0 se já há certificado emitido (renewal/central.conf)
#   preparar.sh limpar       # apaga só o conteúdo de live/archive/renewal; NUNCA a raiz montada
#   preparar.sh temporario   # cria um autoassinado de 1 dia em live/central, se não houver certificado
set -eu
base=/etc/letsencrypt
vivo=$base/live/central

case ${1:-} in
    existe)
        [ -f "$base/renewal/central.conf" ]
        ;;
    limpar)
        rm -rf "$vivo" "$base/archive/central" "$base/renewal/central.conf"
        ;;
    temporario)
        if [ -f "$vivo/fullchain.pem" ] && [ -f "$vivo/privkey.pem" ]; then
            exit 0
        fi
        # Remove restos (inclusive symlinks quebrados) antes de gravar: gravar por cima seguiria o symlink.
        rm -rf "$vivo"
        mkdir -p "$vivo"
        python - "$vivo" <<'PY'
import datetime
import sys

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa

destino = sys.argv[1]
chave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
nome = x509.Name([x509.NameAttribute(x509.oid.NameOID.COMMON_NAME, "temporario")])
agora = datetime.datetime.now(datetime.timezone.utc)
cert = (
    x509.CertificateBuilder()
    .subject_name(nome)
    .issuer_name(nome)
    .public_key(chave.public_key())
    .serial_number(x509.random_serial_number())
    .not_valid_before(agora - datetime.timedelta(minutes=5))
    .not_valid_after(agora + datetime.timedelta(days=1))
    .sign(chave, hashes.SHA256())
)
with open(f"{destino}/privkey.pem", "wb") as f:
    f.write(
        chave.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    )
with open(f"{destino}/fullchain.pem", "wb") as f:
    f.write(cert.public_bytes(serialization.Encoding.PEM))
PY
        chmod 0600 "$vivo/privkey.pem"
        ;;
    *)
        echo "Uso: preparar.sh existe|limpar|temporario" >&2
        exit 2
        ;;
esac
