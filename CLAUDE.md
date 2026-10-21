@AGENTS.md

## Subagentes

Definidos em `.claude/agents/` (equivalentes do Codex em `.codex/agents/`, veja "Agentes" no AGENTS.md; rodam com Sonnet, conforme o `model:` de cada arquivo). A sessão principal planeja e integra; os subagentes executam tarefas pequenas e bem delimitadas.

| Subagente | Usar para |
| --- | --- |
| `implementador-backend` | Implementar uma tarefa pequena já especificada (um caso de uso, uma rota, um job) |
| `escritor-testes` | Transformar critérios de aceite em testes Pytest e rodá-los |
| `especialista-migracoes` | Criar ou revisar migrações Alembic contra o `data-model.md` |
| `revisor-codigo` | Revisar um diff quanto a camadas, transições, outbox e auditoria (somente leitura) |
| `revisor-seguranca` | Revisar um diff contra a matriz de acesso e o modelo de ameaças (somente leitura) |
| `guardiao-docs` | Atualizar a documentação afetada e verificar IDs e links |

Fluxo sugerido para uma tarefa:
1. A sessão principal lê o caso de uso e quebra a tarefa.
2. `especialista-migracoes`, se houver mudança de esquema.
3. `implementador-backend`.
4. `escritor-testes`.
5. `revisor-codigo` e `revisor-seguranca` em paralelo.
6. `guardiao-docs`.
7. A sessão principal consolida e apresenta o diff, **sem commit**.

Mantenha na sessão principal (não delegue aos subagentes) o desenho de lógica concorrente nova, mudanças no modelo de dados que não estejam no `data-model.md` e qualquer decisão que vire ADR.
