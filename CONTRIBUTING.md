# Como contribuir

Guia de trabalho da equipe. As ferramentas marcadas como *proposta* ainda podem mudar na primeira semana de código.

## Organização das tarefas

- Toda tarefa nasce como cartão no Kanban do Notion (Backlog → Doing → Finish).
- Cada integrante é dono de uma **frente vertical** (tela, API e banco):
  1. Autenticação, papéis e LGPD
  2. Cadastros e agendas
  3. Solicitação, fila e prioridade
  4. Ciclo do agendamento
  5. Notificações
  6. Painel e dados sintéticos
- Antes de começar, mova o cartão para **Doing** e coloque seu nome em Responsável.

## Branches

- `main` é protegida: só recebe código por pull request aprovado e com a CI verde.
- Uma branch por cartão, a partir da `main` atualizada:

  ```
  feat/fila-motor-de-prioridade
  fix/agendamento-expiracao-duplicada
  docs/adr-escopo-por-unidade
  chore/ci-cache-pip
  ```

## Commits

Padrão [Conventional Commits](https://www.conventionalcommits.org/pt-br/) *(proposta)*, em português:

```
feat(agendamento): confirmar presença com validação de prazo
fix(worker): evitar expirar proposta já respondida
docs(adr): registrar decisão sobre escopo por unidade
test(fila): cobrir empate na data do pedido
```

Tipos: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`, `ci`.

## Pull requests

- Pequenos: de preferência um cartão por PR, com menos de ~400 linhas alteradas.
- Preencha o modelo do PR (o GitHub carrega automaticamente).
- Pelo menos **uma aprovação** de outro integrante.
- Quem abriu o PR é quem faz o merge, depois da aprovação.

## Backend

- **Lint e formatação:** Ruff *(proposta)*. A CI falha se o código não estiver formatado.
- **Testes:** Pytest. Regra de negócio nova vem com teste; correção de bug vem com o teste que reproduz o bug.
- **Migrações (Alembic):**
  - uma migração por mudança de esquema, gerada e **revisada à mão** antes do PR;
  - nunca editar uma migração que já está na `main`; para corrigir, crie uma nova;
  - restrições importantes (índices únicos parciais, `CHECK`) ficam na migração, não só no código Python.
- **Onde fica o código:** tudo do backend em `apps/backend`; o frontend web em `apps/web`.
- **Camadas do backend:** rotas em `app/api`, jobs em `app/worker`, regras de negócio em `app/dominio` (sem importar FastAPI nem SQLAlchemy), acesso a banco e serviços externos em `app/infra`. Regra nova vai para `dominio`, nunca direto na rota ou no job, para a API e o Worker usarem a mesma implementação.

## Dados e segurança

- **Somente dados sintéticos.** Nenhum dado real de paciente, nem em teste, nem em print.
- Nunca suba segredos (`.env`, senhas, chaves). Use o `.env.example` como modelo.
- Respostas da API para o paciente nunca incluem posição na fila ([ADR-007](docs/decisions/ADR-007-paciente-ve-status.md)).
- Toda mudança de estado de solicitação ou agendamento registra auditoria (RN-010 nas [regras de negócio](docs/requirements/business-rules.md)).

## Documentação

A estrutura e a responsabilidade de cada documento estão em [docs/README.md](docs/README.md). Requisito, regra ou caso de uso novo ganha um ID estável (`RF-`, `RN-`, `UC-`), e o PR que implementa cita esse ID.

## Decisões de arquitetura

Mudou algo estrutural (tecnologia, padrão, regra que afeta várias frentes)? Escreva um ADR em `docs/decisions/` usando o [modelo](docs/decisions/template.md) e abra um PR só com ele para o grupo discutir.

## Definição de pronto

Um cartão vai para **Finish** quando:

- [ ] o código está na `main`, com a CI verde;
- [ ] há testes da regra de negócio;
- [ ] a migração, se houver, foi aplicada e revisada;
- [ ] a documentação afetada foi atualizada: requisitos e casos de uso, SDD, segurança, OpenAPI ou ADR;
- [ ] os testes citam o ID do caso de uso ou da regra que cobrem (`test_uc004_...`);
- [ ] o comportamento foi conferido rodando localmente com o Docker Compose.
