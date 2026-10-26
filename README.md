# Central Inteligente de Teleagendamento — CH/UPE

Plataforma web para marcação, confirmação e reagendamento de consultas, exames e procedimentos dos usuários do SUS atendidos pelo Complexo Hospitalar da Universidade de Pernambuco (CISAM, HUOC e PROCAPE).

> **Status:** 🚧 em desenvolvimento (outubro/2026). Backend em implementação; base técnica do frontend disponível, ainda sem telas de negócio.
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
- WhatsApp e SMS
- Integração real com sistemas de regulação
- Chatbot e modelos preditivos

**Fora do escopo (descartado)**
- App mobile nativo e notificações push ([ADR-015](docs/decisions/ADR-015-app-mobile.md)): o paciente usa o site responsivo, mobile-first, no celular
- Telegram ([ADR-013](docs/decisions/ADR-013-n8n-telegram.md))

## Arquitetura em uma frase

Uma API FastAPI e um Worker Python compartilham o mesmo código e o mesmo PostgreSQL; o Nginx entrega o frontend e faz proxy para `/api/v1`; tudo roda com Docker Compose numa VM Oracle. Detalhes no [SDD](docs/architecture/SDD.md).

## Stack

| Camada | Tecnologia |
| --- | --- |
| Backend | Python, FastAPI (síncrono), SQLAlchemy 2, Alembic, Pydantic, Pytest |
| Banco | PostgreSQL |
| Frontend | React + TypeScript + Vite; base técnica implementada, sem telas de negócio |
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
│   ├── web/                  # base React + TypeScript + Vite, sem telas de negócio
├── infra/
│   └── nginx/                # configuração do Nginx
├── scripts/                  # backup, carga de dados sintéticos, utilitários
├── docs/                     # documentação
├── docker-compose.yml        # sobe tudo a partir da raiz
└── .env.example
```

**API e Worker** usam o mesmo código e a mesma imagem Docker; o que muda é o comando de inicialização no `docker-compose.yml`. A API responde às requisições do frontend. O Worker roda sozinho, guiado pelo relógio: expira propostas vencidas e envia os avisos. Os dois se comunicam pelo banco, não diretamente ([SDD](docs/architecture/SDD.md#2-organização-do-código)).

## Como rodar

Para executar e validar a base web, consulte [apps/web/README.md](apps/web/README.md).

Requisitos: Docker com Compose v2.

```bash
cp .env.example .env                                    # ajuste a senha e o JWT_SECRET_KEY
docker compose --profile dev up -d --build              # postgres, migrate, api, worker e mailpit
curl http://127.0.0.1:8000/api/v1/health                # {"status":"ok"}
docker compose exec api pytest                          # testes
docker compose exec api sh -c "ruff check . && ruff format --check ."   # lint
docker compose logs -f worker                           # laço de jobs
```

O `.env` é obrigatório: o `docker-compose.yml` lê dele as credenciais do banco e os segredos, e sem ele os serviços não sobem. Ele nunca é versionado; variáveis novas aparecem primeiro no `.env.example`. Os testes usam um banco separado, `<POSTGRES_DB>_test`, apagado e recriado a cada execução. Para carregar dados sintéticos no banco de desenvolvimento, rode `docker compose exec api python -m app.infra.seed` (com histórico para a demonstração: veja [Dados da demonstração](#dados-da-demonstração)).

### Testes no host (fora do container)

Dentro do container (`docker compose exec api pytest`) nada além disso é necessário: o Compose já injeta a `DATABASE_URL`. No host, o `pytest` precisa dela apontando para o Postgres do Compose em `127.0.0.1` (porta publicada só na máquina local). Monte a URL a partir das `POSTGRES_*` do `.env`, sem copiar a senha para lugar nenhum:

```bash
set -a; . ./.env; set +a
export DATABASE_URL="postgresql+psycopg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@127.0.0.1:5432/${POSTGRES_DB}"
cd apps/backend && uv run pytest
```

Sem a variável, os testes de integração falham com `password authentication failed`. Fora do container, os testes que leem arquivos da raiz do repositório (`.env.example`, `.claude/`, `.codex/`) rodam; dentro dele são pulados, porque a imagem só leva `apps/backend`. O teste de e-mail real é pulado se o mailpit estiver fora do ar (`--profile dev`).

Pelo `scripts/testar.sh`, a opção `--rapido` pula os testes marcados `lento` (a carga do histórico do seed, alguns minutos). Sem ela a suíte roda completa (valores observados, aproximados: cerca de 7 minutos):

```bash
scripts/testar.sh --rapido            # sem os testes lentos (cerca de 1,5 minuto observado)
scripts/testar.sh                     # suíte completa
scripts/testar.sh --rapido tests/test_admin.py -q   # os demais argumentos vão para o pytest
```

- Documentação da API: http://127.0.0.1:8000/api/v1/docs
- E-mails enviados em desenvolvimento (mailpit): http://127.0.0.1:8025

### Senha de um usuário da equipe pelo terminal

Contas da equipe nascem com senha temporária, e quem entra com ela só consegue trocar a senha. Para gerar uma nova (por exemplo, a de um ADMIN que se esqueceu, que a API não redefine), no servidor:

```bash
docker compose exec api python -m app.infra.admin redefinir-senha --email admin@exemplo.com
```

A senha temporária aparece **uma única vez** na saída, nunca em log nem na auditoria, e todas as sessões da conta são revogadas. A pessoa troca a senha no primeiro acesso. Para atendente e gestor, o ADMIN também faz isso pela API (`POST /admin/usuarios/{id}/redefinir-senha`).

## Dados da demonstração

> **Os números da demonstração são simulados.** Nenhum dado é real: pacientes, filas, propostas, faltas e indicadores saem de uma simulação com a mesma regra de negócio do sistema, calibrada para a apresentação.

### Carregar o seed

```bash
docker compose exec api python -m app.infra.seed                                   # estrutura e contas de desenvolvimento
docker compose exec api python -m app.infra.seed --historico                       # + 8 semanas de histórico
docker compose exec api python -m app.infra.seed --historico --semanas 4           # de 2 a 26 semanas
```

- **Desenvolvimento** (`APP_ENV=development`): todas as contas do seed usam a mesma senha, a de `SEED_SENHA` ou uma gerada e impressa. O histórico termina no instante da carga e leva, nas medições feitas, de 3 a 6 minutos para 8 semanas.
- Rodar de novo **não troca nenhuma senha** nem duplica dados: o seed avisa o que já existia.

### Em production (VM da demonstração)

Em `APP_ENV=production` o seed só roda com **duas chaves**: `DEMO_SEED_PERMITIDO=true` no `.env` e a flag `--confirmo-banco-de-demonstracao`. Sem as duas, ele se recusa e explica. Ele também se recusa se o banco tiver algum paciente que não seja do seed (cadastro feito pelo site). Nenhuma conta do seed tem senha conhecida: cada conta da equipe e cada paciente de apresentação recebe uma senha temporária, impressa **uma só vez** no fim da carga; os demais pacientes não têm login. Guarde a saída. Roteiro:

1. Pare a API e o Worker, para nenhum cadastro novo entrar no meio da carga (o seed trava a tabela de pacientes):
   ```bash
   docker compose stop api worker
   ```
2. Confira que o `.env` tem `APP_ENV=production` e ligue a trava: `DEMO_SEED_PERMITIDO=true`.
3. Rode o seed (o `run` usa o `.env` e aplica as migrações antes, pelo `migrate`):
   ```bash
   docker compose run --rm api python -m app.infra.seed --historico --confirmo-banco-de-demonstracao
   ```
4. **Desligue a trava**: `DEMO_SEED_PERMITIDO=false` no `.env`.
5. Suba de novo:
   ```bash
   docker compose up -d api worker
   ```

Cuidados:
- Rode num **banco novo**. Se o banco veio de um seed de desenvolvimento, as contas dele têm a senha comum, e o seed em production **não** a troca: ele avisa, e você precisa rodar `redefinir-senha` para cada conta antes de expor o banco.
- As senhas temporárias não expiram; cada pessoa troca a sua no primeiro acesso.
- Em production a variável `SEED_SENHA` é ignorada.
- Se a carga falhar, nada é gravado; a mensagem omite dados para não imprimir CPF nem nome.

### Contas criadas

Com `--historico`, o seed cria as contas abaixo (as de equipe que já existem de uma carga anterior são mantidas, sem trocar a senha). Sem `--historico`, só as contas básicas de desenvolvimento: `admin@`, `gestor.cisam@`, `atendente.huoc@`, um atendente suspenso e a paciente de teste.

| Conta | Papel | Escopo |
| --- | --- | --- |
| `admin@exemplo.com` | ADMIN | tudo |
| `gestor.central@exemplo.com` | GESTOR sem unidade | a central inteira |
| `gestor.cisam@exemplo.com` | GESTOR | CISAM |
| `atendente.cisam@exemplo.com` | ATENDENTE | filas do CISAM |
| `atendente.huoc@exemplo.com` | ATENDENTE | filas do HUOC |
| `atendente.procape@exemplo.com` | ATENDENTE | fila do PROCAPE |
| `Paciente Demonstração Um` (CPF `91000000192`) | PACIENTE | o próprio |
| `Paciente Demonstração Dois` (CPF `91000000273`) | PACIENTE | o próprio |

Os dois pacientes de apresentação entram com o CPF (sem e-mail) e têm um roteiro fixo: o **Um** tem uma consulta de cardiologia já realizada e, nas últimas horas, outra solicitação de cardiologia com a **proposta aberta**, dentro do prazo; o **Dois** tem um pedido de mamografia **cancelado** e uma consulta de cardiologia **confirmada no futuro**. Os demais pacientes (mais de mil numa carga de 8 semanas) têm nome do tipo "Ana Exemplo 001" e não têm login nem e-mail.

### Como os números são calibrados

A simulação usa a semente fixa `20261019`, avança de 2 em 2 horas e chama os mesmos jobs e as mesmas rotinas de transição da API e do Worker (confirmar, recusar, cancelar, classificar, registrar presença). Os identificadores gerados são deterministas: duas cargas com a mesma semente dão as mesmas linhas.

| Calibração | Valor | Por quê |
| --- | --- | --- |
| Múltiplo de procura | 1,3 a 1,35 vez as vagas semanais de cada fila | Procura maior que a oferta forma fila |
| Fila inicial | 48 dias de chegadas antes do período, mais 7 dias com os jobs rodando | A primeira semana não mostra vagas perdidas de arranque |
| Desistência na fila | 22% dos pedidos | Sem ela a fila cresceria sem parar; quem espera semanas desiste de parte dos pedidos |
| Risco dos pedidos | 4% vermelho, 10% amarelo, 86% verde | Os casos graves ganham vaga na hora; a espera de semanas aparece nos verdes |
| Respostas dos critérios | a maioria responde igual; idades de 30 a 70 anos | As notas empatam e o desempate é a chegada; com notas todas diferentes só os de nota alta seriam atendidos e a mediana de espera cairia para poucos dias |
| Resposta às propostas | 62% confirmam, 15% recusam, o resto deixa expirar | |
| Comparecimento | 85% | |
| Cancelamento depois de confirmar | 6% | |
| **Lote de última hora** | 3 vermelhos e 2 amarelos por fila, duas horas antes do fim | Casos graves ganham vaga assim que aparece uma; sem o lote, a fila do instante da carga nunca teria vermelho nem amarelo |
| **Vagas abertas no fim** | 8 desistências de consultas futuras de cardiologia, duas horas antes do fim | Com a fila funda, o roteiro dos pacientes de apresentação precisa de vagas livres |
| Pacientes de apresentação | roteiro fixo, acima | Estados garantidos para a demonstração; se faltar um, a carga falha em vez de mentir |

Exemplo observado numa carga de 8 semanas, em 25/10/2026 (aproximado; varia pouco a cada carga): cerca de 2.000 solicitações; 61% das propostas confirmadas; 98% das vagas ocupadas e 2% perdidas; mediana de espera de cerca de 2 semanas (p90 de 6); fila atual com 14 vermelhos, 13 amarelos e 465 verdes (entre 100 e 230 pessoas por unidade).

**Limite conhecido:** a auditoria, a outbox e os avisos gerados pelo seed levam a hora da carga, não a data simulada ([modelo de dados](docs/architecture/data-model.md)). A linha do tempo dos pacientes e os horários dos agendamentos usam a data simulada.

## Trabalhando com o Orca

O Orca roda um agente por tarefa, cada um num worktree. Regras (detalhes no [AGENTS.md](AGENTS.md)):

- O Compose sobe **só no checkout principal**; nunca dentro de um worktree.
- Nos worktrees, rode os testes com `scripts/testar.sh [args do pytest]`. Ele usa o `.env` e o Postgres do checkout principal e um banco de teste próprio por worktree. `scripts/testar.sh --limpar-bancos-orfaos` limpa os de worktrees removidos.
- Deixe o Orca em modo **Manual** (Settings → Agents → Agent Permissions). **Nunca use o Yolo.**
- O commit é sempre da pessoa, depois de revisar o diff.

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
