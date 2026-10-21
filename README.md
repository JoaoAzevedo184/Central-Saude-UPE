# Central Inteligente de Teleagendamento — CH/UPE

Plataforma web para marcação, confirmação e reagendamento de consultas, exames e procedimentos dos usuários do SUS atendidos pelo Complexo Hospitalar da Universidade de Pernambuco (CISAM, HUOC e PROCAPE).

> **Status:** 🚧 em planejamento (outubro/2026). A arquitetura e o modelo de dados estão definidos; o código ainda não foi iniciado.
>
> **Protótipo acadêmico.** O sistema usa apenas dados sintéticos. Nenhum dado real de paciente é coletado, armazenado ou processado.

## Contexto

Projeto de Intervenção da disciplina **Atividades Práticas Interdisciplinares de Extensão III** (Sistemas de Informação, UNINASSAU Olinda), desenvolvido a partir do desafio *Central Inteligente de Teleagendamento para o Complexo Hospitalar Universitário da UPE*, do programa [Desafios PE](https://desafios.pe.gov.br/).

Hoje parte do agendamento e do reagendamento depende de ligações, atendimento presencial e planilhas. A proposta é tornar esse fluxo previsível, acessível e monitorável: o paciente recebe uma proposta de vaga, confirma ou pede outra data pelo celular, e vagas canceladas voltam automaticamente para a fila.

## Escopo do MVP (novembro/2026)

**Inclui**
- Autenticação com papéis: Paciente, Atendente, Gestor e Admin
- Cadastro de unidades, especialidades, agendas e vagas
- Solicitação de atendimento que entra numa fila ordenada por regras de prioridade configuráveis
- Proposta de vaga com prazo de resposta; confirmação, cancelamento e pedido de outra data
- Reaproveitamento de vagas canceladas, sem risco de entregar a mesma vaga a dois pacientes
- Notificações por e-mail e dentro do site
- Painel de indicadores para gestores
- LGPD: consentimento registrado, trilha de auditoria, CPF mascarado e minimização de dados

**Fica para depois**
- App mobile (React Native) e notificações push
- WhatsApp, SMS e Telegram
- Integração real com sistemas de regulação
- Chatbot e modelos preditivos

## Arquitetura em uma frase

Uma API FastAPI e um Worker Python compartilham o mesmo código e o mesmo PostgreSQL; o Nginx entrega o frontend e faz proxy para `/api/v1`; tudo roda com Docker Compose numa VM Oracle. Detalhes no [SDD](docs/architecture/SDD.md).

## Stack

| Camada | Tecnologia |
| --- | --- |
| Backend | Python, FastAPI (síncrono), SQLAlchemy 2, Alembic, Pydantic, Pytest |
| Banco | PostgreSQL |
| Frontend | Web responsivo — tecnologia em revisão pelo grupo (proposta: React + TypeScript + Vite) |
| Infra | Docker Compose, Nginx, VM Oracle Cloud |
| CI | GitHub Actions |

## Estrutura do repositório

```
.
├── apps/
│   ├── backend/              # um pacote Python, dois processos (API e Worker)
│   │   ├── app/
│   │   │   ├── api/          # rotas /api/v1, dependências, schemas → processo "api"
│   │   │   ├── worker/       # jobs: expiração, outbox, retentativas → processo "worker"
│   │   │   ├── dominio/      # regras de negócio, usadas pelos dois processos
│   │   │   └── infra/        # banco, repositórios, e-mail, gateways
│   │   ├── migrations/       # Alembic
│   │   ├── tests/
│   │   ├── Dockerfile        # uma imagem para a API e o Worker
│   │   └── pyproject.toml
│   ├── web/                  # frontend web (tecnologia em revisão)
│   └── mobile/               # app React Native — fase 2
├── infra/
│   └── nginx/                # configuração do Nginx
├── scripts/                  # backup, carga de dados sintéticos, utilitários
├── docs/                     # documentação
├── docker-compose.yml        # sobe tudo a partir da raiz
└── .env.example
```

**API e Worker** usam o mesmo código e a mesma imagem Docker; o que muda é o comando de inicialização no `docker-compose.yml`. A API responde às requisições do frontend. O Worker roda sozinho, guiado pelo relógio: expira propostas vencidas e envia os avisos. Os dois se comunicam pelo banco, não diretamente ([SDD](docs/architecture/SDD.md#2-organização-do-código)).

## Como rodar

Requisitos: Docker com Compose v2.

```bash
cp .env.example .env                                    # ajuste a senha e o JWT_SECRET_KEY
docker compose --profile dev up -d --build              # postgres, migrate, api, worker e mailpit
curl http://127.0.0.1:8000/api/v1/health                # {"status":"ok"}
docker compose exec api pytest                          # testes
docker compose exec api sh -c "ruff check . && ruff format --check ."   # lint
docker compose logs -f worker                           # laço de jobs
```

O `.env` é obrigatório: o `docker-compose.yml` lê dele as credenciais do banco e os segredos, e sem ele os serviços não sobem. Ele nunca é versionado; variáveis novas aparecem primeiro no `.env.example`. Os testes usam um banco separado, `<POSTGRES_DB>_test`, apagado e recriado a cada execução. Para carregar dados sintéticos no banco de desenvolvimento, rode `docker compose exec api python -m app.infra.seed`.

### Testes no host (fora do container)

Dentro do container (`docker compose exec api pytest`) nada além disso é necessário: o Compose já injeta a `DATABASE_URL`. No host, o `pytest` precisa dela apontando para o Postgres do Compose em `127.0.0.1` (porta publicada só na máquina local). Monte a URL a partir das `POSTGRES_*` do `.env`, sem copiar a senha para lugar nenhum:

```bash
set -a; . ./.env; set +a
export DATABASE_URL="postgresql+psycopg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@127.0.0.1:5432/${POSTGRES_DB}"
cd apps/backend && uv run pytest
```

Sem a variável, os testes de integração falham com `password authentication failed`. Fora do container, os testes que leem arquivos da raiz do repositório (`.env.example`, `.claude/`, `.codex/`) rodam; dentro dele são pulados, porque a imagem só leva `apps/backend`. O teste de e-mail real é pulado se o mailpit estiver fora do ar (`--profile dev`).

- Documentação da API: http://127.0.0.1:8000/api/v1/docs
- E-mails enviados em desenvolvimento (mailpit): http://127.0.0.1:8025

## Documentação

O mapa completo, com a responsabilidade de cada documento, está em [docs/README.md](docs/README.md).

| Pergunta | Documento |
| --- | --- |
| O que estamos construindo e por quê? | [PRD](docs/product/PRD.md) · [escopo e roadmap](docs/product/scope-and-roadmap.md) |
| Como o sistema deve se comportar? | [requisitos](docs/requirements/functional-requirements.md) · [regras de negócio](docs/requirements/business-rules.md) · [casos de uso](docs/requirements/use-cases/README.md) |
| Como o software é organizado? | [SDD](docs/architecture/SDD.md) · [modelo de dados](docs/architecture/data-model.md) · [API](docs/architecture/api-design.md) · [diagramas](docs/architecture/diagrams/) |
| Como protegemos o sistema e os dados? | [segurança](docs/security/security-overview.md) · [SECURITY.md](SECURITY.md) |
| Por que decidimos assim? | [ADRs](docs/decisions/README.md) · [questões em aberto](docs/requirements/open-questions.md) |
| Como implantar e operar? | [implantação](docs/operations/deployment.md) · [backup e restauração](docs/operations/backup-restore.md) |
| Como trabalhamos em equipe? | [CONTRIBUTING](CONTRIBUTING.md) |

Protótipo navegável: [Figma](https://www.figma.com/design/77RlPMwTFvClwHCAUcb71J/Projeto-extensao)

## Equipe

Edilson Pereira da Silva Filho · Gabriel Leal de Andrade Pereira · João Victor Azevedo de Sena · Paulo Gabriel Morais Santana da Silva · Ruan Gabriel Alves Lima da Silva · Vinícius Alencar Murta Costa
