# AGENTS.md — Central Inteligente de Teleagendamento (CH/UPE)

Protótipo acadêmico (Extensão III, UNINASSAU Olinda) de teleagendamento para usuários do SUS do Complexo Hospitalar da UPE. **Somente dados sintéticos.** Equipe de 6 estudantes; MVP em novembro/2026.

## Regras inegociáveis

- **Nunca faça commit, push, merge ou rebase**, nem crie branches, sem pedido explícito. Deixe as mudanças no working tree para a pessoa revisar.
- Nunca use dados reais de pessoas (nem em testes, seeds, exemplos ou prints). CPFs válidos, porém fictícios.
- Nunca versione segredos. Configuração nova vai para o `.env.example` com valor de exemplo.
- As questões ABERTO-1 a 4 foram respondidas pela UPE em 15/10/2026; veja os ADR-021 e 024 a 028. Cada regra tem um ponto único no domínio (`propor_vaga`, `calcular_expira_em`, `ordenar_fila`, `calcular_nota`, `calcular_escopo`/`escopo_da_equipe`, `reentrar_no_fim_da_fila`, `verificar_elegibilidade`, `pode_autenticar`): use-o e nunca espalhe a regra pelo código. ADR-029 e 030 são só propostas: não implemente sem pedido.

## Stack

- **Backend:** Python, FastAPI **síncrono**, SQLAlchemy 2, Alembic, Pydantic, Pytest.
- **Banco:** PostgreSQL.
- **Infra:** Docker Compose, Nginx, VM Oracle; CI no GitHub Actions.
- **Web:** tecnologia em revisão pelo grupo; não crie código em `apps/web` sem pedido.
- **Mobile:** fase 2.

## Estrutura

```
apps/backend/app/
  api/        rotas /api/v1, dependências (sessão, papel, escopo), schemas Pydantic
  worker/     jobs: expirar propostas, consumir outbox, retentar avisos
  dominio/    regras de negócio — NÃO importa FastAPI nem SQLAlchemy
  infra/      SQLAlchemy, repositórios, SMTP, ReguladorGateway simulado, Relogio
apps/backend/migrations/   Alembic
apps/backend/tests/
apps/web/  apps/mobile/  infra/nginx/  scripts/  docs/
docker-compose.yml   (raiz)
```

API e Worker são **o mesmo pacote e a mesma imagem**, com comandos diferentes. A API responde a requisições. O Worker roda sozinho, guiado pelo relógio. Os dois só se comunicam pelo banco (tabela `outbox`).

## Comandos (previstos — confirme no `pyproject.toml` e no `docker-compose.yml` quando existirem)

```bash
docker compose up -d                                    # sobe tudo
docker compose exec api alembic upgrade head            # migrações
docker compose exec api pytest                          # testes
docker compose exec api ruff check . && ruff format --check .
```

Antes de dizer que terminou, rode os testes e o lint e informe o resultado real.

## Regras de arquitetura

1. **Regra de negócio vive em `dominio/`.** Nunca direto na rota ou no job; a API e o Worker usam a mesma implementação.
2. **Toda transição de estado** (solicitação ou agendamento) segue, numa única transação:
   1. `SELECT ... FOR UPDATE` no agregado;
   2. verificar dono (paciente) ou papel e escopo (equipe);
   3. verificar o estado de origem e o prazo com `Relogio`;
   4. aplicar a transição;
   5. gravar a auditoria;
   6. gravar o evento na `outbox`;
   7. commit.

   Estado de origem inválido → erro de domínio → `409`.
3. **Ocupação de vaga não é coluna.** Só existe o índice único parcial em `agendamento(vaga_id) WHERE status IN ('PROPOSTO','CONFIRMADO')`. Não adicione "ocupada" à tabela `vaga`.
4. **A API nunca envia e-mail nem roda job.** Isso é papel do Worker.
5. **Jobs do Worker são idempotentes** e pegam trabalho com `FOR UPDATE SKIP LOCKED`.
6. **Tempo:** `timestamptz` no banco; ISO 8601 com fuso na API; exibição em `America/Recife`. Nada de `datetime.now()` solto: use `Relogio` (fixável nos testes).
7. **Integrações externas** ficam atrás de interfaces (`CanalNotificacao`, `ReguladorGateway`).
8. **Restrições do banco** (índices parciais, `CHECK`, `UNIQUE`) ficam na migração, não só no Python. Nunca edite uma migração que já esteja na `main`.

## Segurança

- Rotas do paciente filtram por `paciente_id` da sessão **dentro da query**. Recurso de outro paciente responde `404`.
- O papel do usuário vem da sessão, nunca do corpo da requisição. Schemas de entrada não aceitam `papel`, `status`, `classificacao_risco`, `nota` nem `pontos` vindos do paciente.
- **Respostas para o paciente nunca trazem posição na fila nem tamanho da fila** (ADR-007).
- Escrita exige header `X-CSRF-Token`; refresh token só em cookie `httpOnly`.
- Logs sem nome, CPF ou corpo de requisição; use IDs.
- Matriz de permissões: `docs/security/access-control.md`. Ameaças: `docs/security/threat-model.md`.

## Convenções

- **Nomes de domínio em português** (`Solicitacao`, `Agendamento`, `confirmar()`). Termos técnicos (`repository`, `schema`) podem ficar em inglês.
- **Erros da API** em Problem Details (RFC 9457).
- **Testes** citam o ID que cobrem: `test_uc004_proposta_expirada_retorna_409`. Os critérios de aceite dos casos de uso (`docs/requirements/use-cases/`) são a lista mínima de testes.
- Toda rota nova com ID ganha teste de acesso negado (paciente A acessando recurso de B → `404`).

## Documentação — onde está a verdade

| Assunto | Arquivo |
| --- | --- |
| Termos e escopo | `docs/product/PRD.md` |
| Estados e regras RN-001…RN-011 | `docs/requirements/business-rules.md` |
| Fluxos e critérios de aceite | `docs/requirements/use-cases/UC-*.md` |
| Esquema e índices | `docs/architecture/data-model.md` |
| Endpoints e convenções | `docs/architecture/api-design.md` |
| Desenho geral | `docs/architecture/SDD.md` |
| Decisões | `docs/decisions/ADR-*.md` |

Se o código precisar contrariar um desses documentos, não contrarie em silêncio: aponte a divergência e proponha a atualização do documento (ou um ADR novo).

## Agentes

Os 6 agentes abaixo existem nas duas ferramentas, com o mesmo conteúdo:

- **Claude Code:** `.claude/agents/<nome>.md`.
- **Codex:** `.codex/agents/<nome>.toml` (o `name` usa `_` no lugar de `-`, ex.: `revisor_seguranca`); chame pelo nome no prompt.

| Agente | Usar para |
| --- | --- |
| `implementador-backend` | Implementar uma tarefa pequena já especificada (um caso de uso, uma rota, um job) |
| `escritor-testes` | Transformar critérios de aceite em testes Pytest e rodá-los |
| `especialista-migracoes` | Criar ou revisar migrações Alembic contra o `data-model.md` |
| `revisor-codigo` | Revisar um diff quanto a camadas, transições, outbox e auditoria (somente leitura) |
| `revisor-seguranca` | Revisar um diff contra a matriz de acesso e o modelo de ameaças (somente leitura) |
| `guardiao-docs` | Atualizar a documentação afetada e verificar IDs e links |

**Revisores (`revisor-codigo`, `revisor-seguranca`):** no Claude Code não têm Write nem Edit. O Codex não permite sandbox só de leitura por agente (herda as permissões da sessão), então a regra "somente leitura" vai escrita no prompt do agente. Respeite-a nas duas ferramentas.

Ao mudar um agente, altere o `.md` e o `.toml` juntos; `apps/backend/tests/test_agentes.py` confere que os dois não divergem.
