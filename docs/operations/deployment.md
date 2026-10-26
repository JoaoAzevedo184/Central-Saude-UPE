# Implantação

> **Rascunho.** Ainda não há código. Este roteiro descreve o que foi decidido ([ADR-012](../decisions/ADR-012-implantacao.md)) e será completado com os comandos reais no setup do repositório.

## Ambientes

| Ambiente | Onde | Para quê |
| --- | --- | --- |
| Desenvolvimento | Computador de cada integrante, com Docker Compose | Programar e rodar os testes |
| CI | GitHub Actions | Lint e testes em todo pull request |
| Produção (demo) | VM Oracle Cloud, com Docker Compose | Apresentação, testes de usabilidade e avaliação |

Todos usam o mesmo `docker-compose.yml`, na raiz do repositório, com um arquivo de sobreposição para o que muda (portas expostas, volume do código em desenvolvimento, TLS em produção).

| Serviço do Compose | Origem |
| --- | --- |
| `nginx` | Imagem oficial + configuração em `infra/nginx/` + build de `apps/web` |
| `api` | Imagem de `apps/backend`, comando do Uvicorn |
| `worker` | **Mesma imagem** de `apps/backend`, comando `python -m app.worker` |
| `postgres` | Imagem oficial + volume `pgdata` |

Scripts de backup e de carga de dados sintéticos ficam em `scripts/`.

## Pré-requisitos da VM

- Docker e o plugin Docker Compose instalados.
- Lista de segurança da Oracle liberando só as portas 80 e 443; SSH restrito às chaves da equipe.
- Domínio ou subdomínio apontando para o IP da VM *(a definir)*.
- Certificado TLS (proposta: Let's Encrypt).
- Arquivo `.env` de produção criado direto na VM, nunca versionado.

## Primeira implantação (roteiro)

Máquinas envolvidas: **PC (Linux)** de quem implanta e **Servidor (VM Oracle, Linux)**.

1. **PC (Linux):** conectar por SSH no Servidor.
2. **Servidor (VM Oracle, Linux):** clonar o repositório e criar o `.env` a partir do `.env.example`, com segredos novos.
3. **Servidor (VM Oracle, Linux):** subir os containers em modo de produção.
4. **Servidor (VM Oracle, Linux):** aplicar as migrações do Alembic.
5. **Servidor (VM Oracle, Linux):** carregar os dados sintéticos (seed), com o roteiro do [README](../../README.md#dados-da-demonstração): parar API e Worker, ligar `DEMO_SEED_PERMITIDO`, rodar o seed com `--confirmo-banco-de-demonstracao`, **desligar a variável** e subir de novo. O limite de requisições dos indicadores (`limit_req`) deve entrar no Nginx da VM *(proposta; ainda não configurado)* ([AM-025](../security/threat-model.md)).
6. **PC (Linux):** abrir o domínio no navegador e conferir `GET /api/v1/health`.

## Atualização

1. Pull request aprovado e com a CI verde na `main`.
2. **Servidor (VM Oracle, Linux):** atualizar o código, reconstruir as imagens e aplicar as migrações novas.
3. Conferir a saúde da API e um fluxo do paciente.

No MVP a implantação é manual. Automatizar pelo GitHub Actions é uma evolução possível depois do primeiro deploy estável.

## Configuração do Nginx (proposta)

- Redirecionar HTTP para HTTPS; HSTS.
- Servir o frontend compilado como arquivos estáticos.
- Fazer proxy de `/api/v1/` para o serviço `api`.
- Cabeçalhos de segurança: `Content-Security-Policy`, `X-Content-Type-Options: nosniff`, `Referrer-Policy`.
- Limite de requisições em `/api/v1/auth/` (AM-004 no [modelo de ameaças](../security/threat-model.md)).
