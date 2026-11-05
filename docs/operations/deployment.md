# Implantação

Roteiro de produção da demonstração ([ADR-012](../decisions/ADR-012-implantacao.md)). Serve a qualquer servidor Linux com Docker: uma VM (Oracle Ampere ARM64 ou x86) ou um computador local. Nada aqui depende de um provedor.

## Ambientes

| Ambiente | Onde | Para quê |
| --- | --- | --- |
| Desenvolvimento | Computador de cada integrante, com Docker Compose | Programar e rodar os testes |
| CI | GitHub Actions | Lint, testes e `scripts/testar-infra.sh` em todo pull request |
| Produção (demo) | Servidor com Docker Compose (VM ou máquina local) | Apresentação, testes de usabilidade e avaliação |

Todos usam o mesmo `docker-compose.yml`, na raiz. O que muda é o `.env` e os **perfis** do Compose:

| Serviço | Perfil | Função |
| --- | --- | --- |
| `postgres`, `migrate`, `api`, `worker` | (sempre) | Banco, migração, API e Worker (mesma imagem de `apps/backend`) |
| `mailpit` | `dev` | Caixa de e-mail falsa; nunca em produção |
| `nginx` | `proxy` | TLS, estáticos de `apps/web/dist` e proxy de `/api/` (`infra/nginx/`) |
| `certbot` | `certbot` | Renova o certificado Let's Encrypt a cada 12 h |
| `web-build` | `build` | Gera `apps/web/dist` com `npm ci` + build, sem Node no servidor |

## Regra de rede que não pode quebrar

A API só confia no `X-Forwarded-For` vindo do IP fixo `172.30.0.10` (o nginx do compose, por `--forwarded-allow-ips`). O limite de tentativas de login usa esse IP. **O nginx de produção é o do compose.** Um nginx instalado na própria máquina faria todas as requisições chegarem do gateway do Docker, e a API trataria todos os visitantes como um só.

O nginx **substitui** o `X-Forwarded-For` por `$remote_addr`, nunca o acrescenta, para o visitante não forjar o IP. Só o nginx publica portas para fora (80 e 443). Postgres e API ficam em `127.0.0.1`.

## Pré-requisitos do servidor

- Docker com Compose v2 e `git`, `curl` e `openssl`. Funciona em ARM64 e x86.
- Portas **80 e 443** liberadas para a internet (regra de firewall do provedor); SSH restrito às chaves da equipe. O Docker publica portas por cima do `ufw`: o firewall do provedor é a barreira.
- Domínio apontando para o IP público do servidor (por exemplo, um subdomínio do DuckDNS). A emissão do certificado usa o desafio HTTP-01, que precisa da porta 80.
- Um clone do repositório na branch `main`. **Compose só no checkout principal**, nunca num worktree.

## Primeira implantação

Máquinas: **PC (Linux)** de quem implanta e **Servidor** (VM ou máquina local).

1. **PC:** conectar por SSH no Servidor.
2. **Servidor:** clonar o repositório e criar o `.env`: `cp .env.example .env`. Ajustar, com segredos novos gerados no servidor:
   - `APP_ENV=production`;
   - `POSTGRES_PASSWORD`: senha nova;
   - `JWT_SECRET_KEY` e `LOGIN_HASH_KEY`: cada um com `openssl rand -hex 32`, valores diferentes entre si (a API recusa chave curta, com prefixo `troque-` ou igual à outra);
   - `COOKIE_SECURE=true`, `COOKIE_DOMAIN` vazio, `CORS_ORIGINS` vazio (site e API no mesmo domínio);
   - `APP_URL_PUBLICA=https://SEU_DOMINIO` (a API recusa `http://` e `localhost`);
   - `DOMINIO=SEU_DOMINIO` e `EMAIL_DO_CERTIFICADO=EMAIL_DO_CERTIFICADO`, com os valores reais, só no `.env`;
   - `INSTALL_DEV=false`: a imagem da produção não leva pytest nem ruff;
   - SMTP real (`SMTP_*`, `SMTP_STARTTLS=true`) se a demonstração enviar e-mail.
3. **Servidor:** emitir o certificado: `scripts/certificado.sh emitir`. O script cria um certificado temporário, sobe o nginx, pede o certificado ao Let's Encrypt e **recria o contêiner do nginx** para ele usar o certificado novo. Para ensaiar sem gastar o limite de emissões, rode antes `scripts/certificado.sh emitir --staging` e, depois, `scripts/certificado.sh emitir --substituir` para trocar pelo de produção. **Nunca apague nem recrie a pasta `infra/nginx/certs/`:** o nginx a monta, e uma pasta nova no mesmo caminho deixa o contêiner olhando a antiga. O `--substituir` limpa só o conteúdo (`live/`, `archive/`, `renewal/`) e depois recria o nginx (`docker compose up -d --force-recreate nginx`).
4. **Servidor:** `scripts/deploy.sh`. Ele atualiza o código, constrói as imagens e o frontend, aplica as migrações, sobe tudo (inclusive o `certbot`) e confere `https://SEU_DOMINIO/api/v1/health`.
5. **Servidor:** carregar os dados sintéticos, uma única vez, com o roteiro do [README](../../README.md#dados-da-demonstração): parar API e Worker, ligar `DEMO_SEED_PERMITIDO`, rodar o seed com `--confirmo-banco-de-demonstracao`, **desligar a variável** e subir de novo (`scripts/deploy.sh`).
6. **Servidor:** agendar o backup (seção abaixo) e conferir a renovação: `scripts/certificado.sh testar-renovacao`.
7. **PC:** abrir o domínio no navegador, conferir o cadeado e entrar com uma conta da demonstração.

## Atualização

1. Pull request aprovado e CI verde na `main`.
2. **Servidor:** `scripts/deploy.sh`. Ele roda `git pull --ff-only`, constrói imagens e frontend, aplica as migrações, sobe de novo e confere o HTTPS. Para no primeiro erro (`set -euo pipefail`); a mensagem diz o que olhar (`docker compose logs --tail 50 nginx api`).
3. Conferir um fluxo do paciente.

A API fica indisponível por alguns segundos enquanto o contêiner é recriado. O deploy é manual; automatizar pelo GitHub Actions é evolução possível depois.

## Certificado (Let's Encrypt)

- O certificado fica em `infra/nginx/certs/live/central/` (fora do Git). O nome fixo `central` mantém o domínio fora de `infra/nginx/default.conf`.
- O serviço `certbot` roda `certbot renew` a cada 12 h; o nginx se recarrega sozinho a cada 6 h e passa a usar o certificado novo. Sem cron no servidor.
- Testar a renovação sem emitir nada de verdade: `scripts/certificado.sh testar-renovacao` (`certbot renew --dry-run` no ambiente de testes do Let's Encrypt, seguido de reload do nginx).
- Se a renovação falhar, o certificado atual segue valendo até vencer (90 dias). Veja `docker compose logs certbot`.

## Backup e restauração

```bash
scripts/backup.sh                                # dump comprimido (pg_dump -Fc)
scripts/backup.sh --testar-restauracao           # restaura o último dump num banco temporário e confere
scripts/backup.sh --testar-restauracao ARQUIVO   # idem, para um dump específico
```

- Pasta: `BACKUP_DIR` (padrão `~/backups/central-saude-upe`), fora do repositório. O script recusa uma pasta dentro dele. Os arquivos ficam com permissão `600`.
- Guarda 7 dias. Os antigos só são apagados depois que o dump novo existe.
- Agendar (`crontab -e`, todo dia às 03:00): `0 3 * * * /CAMINHO/DO/REPOSITORIO/scripts/backup.sh >> $HOME/backups/backup.log 2>&1`.
- Teste a restauração antes da apresentação. **Copie os dumps para fora do servidor** (`scp`, `rclone`): se o disco da VM for perdido, o backup local vai junto. O script não faz essa cópia.
- Restaurar de verdade num banco novo: `docker compose exec -T postgres sh -c 'pg_restore -U "$POSTGRES_USER" -d BANCO --no-owner' < ARQUIVO`.

## Configuração do nginx (`infra/nginx/`)

| Item | Valor |
| --- | --- |
| HTTP (80) | Só o desafio do certificado (`/.well-known/acme-challenge/`) e `301` para HTTPS |
| HTTPS (443) | Serve `apps/web/dist` com fallback para `index.html`; `/assets/` com cache de 1 ano (nome com hash) |
| Proxy | `/api/` para `api:8000`; `Host`, `X-Forwarded-For $remote_addr` (substitui) e `X-Forwarded-Proto` |
| Cabeçalhos | HSTS (`max-age=15552000`, sem `includeSubDomains` nem `preload`: o DuckDNS é domínio compartilhado), CSP restritiva (`default-src 'self'`, `frame-ancestors 'none'`; o build do Vite não exige `unsafe-inline`), `nosniff`, `Referrer-Policy`, `X-Frame-Options: DENY` |
| Limite por IP | `/api/`: 30 r/s, *burst* 150. `/api/v1/auth/`: 5 r/s, *burst* 40. `/api/v1/equipe/indicadores`: 1 r/s, *burst* 5, atrasando em vez de recusar |
| Corpo | `client_max_body_size 1m` |
| gzip | Só nos estáticos (a API não é comprimida) |
| Erros do nginx | `429` com `application/problem+json` e o mesmo `type` da API (`/problemas/muitas-tentativas`); `502` e `504` viram `503` Problem Details neutro; `413` idem. Nada da página padrão do nginx |

Os limites foram pensados para uma sala inteira atrás do mesmo IP público (NAT do Wi-Fi). Eles só seguram rajadas. **Atenção:** o limite de login da **API** (AM-004) é bem mais apertado e conta por IP **ou** por CPF/e-mail (vale o maior): `LOGIN_MAX_TENTATIVAS=5` falhas de login vindas do mesmo IP em `LOGIN_JANELA_MIN=15` minutos bloqueiam o login de **todos** que compartilham aquele IP, e o registro tem `REGISTRO_MAX_TENTATIVAS=20` por IP. Numa apresentação com a plateia no mesmo Wi-Fi, suba esses dois valores no `.env` antes (por exemplo 60 e 100) e volte aos padrões depois. O limite por CPF/e-mail continua protegendo cada conta com o mesmo valor, então ele também sobe: é a troca consciente de uma demonstração.

A API **não serve** `/api/v1/docs` nem `/api/v1/openapi.json` em `APP_ENV=production`. O contrato versionado é `docs/architecture/openapi.json`.

## Plano B: computador local com Cloudflare Tunnel (só documentado)

Não implementado: se o servidor da nuvem não sair, vira uma tarefa própria. O que muda:

- O túnel termina o TLS na Cloudflare; o nginx não precisa de certificado nem de redirecionamento para HTTPS, e **não pode** redirecionar (daria laço).
- O nginx precisa ler o IP real em `CF-Connecting-IP`. Isso só é seguro se o cabeçalho vier **apenas** do contêiner `cloudflared`. Por isso, um `server` interno, **sem porta publicada**, que só o `cloudflared` alcança:

```nginx
# Sem "ports:" no compose: só quem está na rede borda enxerga a :8080.
server {
    listen 8080;
    server_name _;
    set_real_ip_from 172.30.0.11;      # IP fixo do serviço cloudflared na rede borda
    real_ip_header   CF-Connecting-IP; # só vale vindo do IP acima
    # ... mesmos locations do server 443, com:
    #   proxy_set_header X-Forwarded-Proto https;
}
```

- No compose: serviço `cloudflared` (perfil `tunnel`, `TUNNEL_TOKEN` só no `.env`) com `ipv4_address: 172.30.0.11` na rede `borda`, apontando para `http://nginx:8080`.
- O `X-Forwarded-For $remote_addr` continua valendo: depois do `real_ip`, `$remote_addr` já é o IP do visitante, e a API continua confiando só em `172.30.0.10`.
- Como a `:8080` não é publicada, ninguém de fora forja `CF-Connecting-IP` com o túnel desligado.
- O `.env` fica igual: `APP_URL_PUBLICA=https://...`, `COOKIE_SECURE=true`.

## O que só se confirma no servidor de destino

- Emissão e renovação reais do certificado (`scripts/certificado.sh emitir` e `testar-renovacao`).
- IP real do visitante no log do nginx (`docker compose logs nginx`): deve ser o do visitante, nunca `172.30.0.1`.
- Build do frontend e imagem do backend em ARM64 (`scripts/deploy.sh` na VM Ampere).
- O túnel da Cloudflare, se o plano B for usado.
