# Registro de decisões de arquitetura (ADRs)

Cada decisão relevante vira um arquivo `NNN-titulo.md` com contexto, decisão e consequências; o modelo está em [template.md](template.md). Uma decisão aceita não é editada para dizer outra coisa: ela é marcada como **Substituída** e um ADR novo explica a mudança.

**Status possíveis**
- **Proposto:** em discussão.
- **Provisório:** aceito para o MVP, a confirmar com a instituição.
- **Aceito:** vale para o projeto.
- **Progressivo:** aceito, mas entra depois do MVP.
- **Adiado:** só entra se o gatilho for atingido.
- **Substituído:** trocado por outro ADR.

| ADR | Decisão | Status |
| --- | --- | --- |
| [001](ADR-001-stack.md) | Stack do backend e da infraestrutura; frontend em revisão | Aceito (frontend: Proposto) |
| [002](ADR-002-web-primeiro.md) | Web responsivo primeiro; mobile depois na mesma `/api/v1`, sem BFF | Aceito |
| [003](ADR-003-autenticacao-web.md) | Refresh token em cookie httpOnly + CSRF por header; tokens prontos para Bearer | Aceito |
| [004](ADR-004-ocupacao-da-vaga.md) | Ocupação da vaga derivada do agendamento (índice único parcial) | Aceito |
| [005](ADR-005-worker-separado.md) | Worker separado da API, com jobs idempotentes e `SKIP LOCKED` | Aceito |
| [006](ADR-006-outbox.md) | Outbox transacional para eventos que geram notificação | Aceito |
| [007](ADR-007-paciente-ve-status.md) | Paciente vê o status da solicitação, sem posição na fila (mantido pela UPE em 2026-10-15) | Aceito |
| [008](ADR-008-datas-e-fuso.md) | `timestamptz` no banco, exibição em `America/Recife` | Aceito |
| [009](ADR-009-backup.md) | Backup com `pg_dump` para Object Storage; RPO igual à frequência real; restauração testada | Aceito |
| [010](ADR-010-integracoes-por-interface.md) | Integrações atrás de interfaces com implementação simulada | Aceito |
| [011](ADR-011-regras-de-prioridade.md) | Regras de prioridade em tabela, marcadas como simuladas (formato atual no [024](ADR-024-protocolo-por-fila.md)) | Aceito |
| [012](ADR-012-implantacao.md) | Uma VM Oracle com Docker Compose e Nginx; CI no GitHub Actions | Aceito |
| [021](ADR-021-matching-automatico.md) | Proposta automática da vaga pelo Worker, na ordem da fila (ABERTO-1) | Aceito |
| [022](ADR-022-ordem-da-fila-sem-aging.md) | Ordem fixa da fila (risco, prioridade legal, data), sem aging (ABERTO-2) | Substituído por [024](ADR-024-protocolo-por-fila.md) |
| [023](ADR-023-escopo-todas-as-unidades.md) | Equipe vê todas as unidades (ABERTO-3) | Substituído por [025](ADR-025-escopo-por-fila.md) |
| [024](ADR-024-protocolo-por-fila.md) | Protocolo por fila: critérios com peso, nota; ordem risco → nota → chegada; risco em três níveis (ABERTO-2) | Aceito |
| [025](ADR-025-escopo-por-fila.md) | Escopo por fila: atendente nas filas atribuídas, gestor por hospital ou central, admin tudo (ABERTO-3) | Aceito |
| [026](ADR-026-prazos-e-volta-ao-fim-da-fila.md) | Confirmação em até 2 dias, tolerância de 1 hora; expiração e falta voltam ao fim da fila (ABERTO-4) | Aceito |
| [027](ADR-027-fila-como-entidade.md) | Fila como entidade, com descrição, elegibilidade, prazo e tolerância | Aceito |
| [028](ADR-028-suspensao-de-acesso.md) | Acesso de profissional é suspenso, nunca apagado | Aceito |
| [029](ADR-029-overbooking-por-vagas-extras.md) | Overbooking por fila como vagas extras, sem mudar o ADR-004 | Proposto (depois do MVP) |
| [030](ADR-030-historico-familiar-como-criterio.md) | Histórico familiar como critério respondido pelo paciente | Proposto |

## Depois do MVP

Ainda sem arquivo próprio; cada um ganha o seu quando sair deste estado.

| ADR | Decisão | Status | Gatilho |
| --- | --- | --- | --- |
| 013 | n8n + Telegram como nova implementação de `CanalNotificacao` | Progressivo | Fluxo de e-mail estável |
| 014 | Prometheus, Grafana e Loki | Progressivo | Primeiro deploy do MVP |
| 015 | App mobile React Native + push | Adiado | Início do desenvolvimento mobile |
| 016 | Redis como cache | Adiado | p95 de `GET /vagas` acima de 300 ms no teste de carga |
| 017 | Réplica de leitura do PostgreSQL | Adiado | A definir pelo grupo |
| 018 | CQRS para o painel | Adiado | A definir pelo grupo |
| 019 | Kubernetes | Adiado | A definir pelo grupo |
| 020 | Sharding | Adiado | A definir pelo grupo |

As questões ABERTO-1 a 4 foram respondidas pela UPE em 2026-10-15; o histórico está em [decisões em aberto](../requirements/open-questions.md).
