# UC-006 — Expirar proposta

| | |
| --- | --- |
| **Ator principal** | Sistema (Worker) |
| **Objetivo** | Devolver à fila as vagas cujas propostas não foram respondidas no prazo |
| **Requisitos** | RF-015, RF-016, RF-018 |
| **Regras** | RN-003, RN-005, RN-010, RN-011 |

## Gatilho

- Execução periódica do job de expiração no Worker.

## Fluxo principal

1. O Worker seleciona um lote de agendamentos `PROPOSTO` com `expira_em` no passado, usando `FOR UPDATE SKIP LOCKED`.
2. Para cada agendamento, numa transação, o Worker:
   - confirma que ainda está `PROPOSTO`;
   - muda para `EXPIRADO`;
   - devolve a solicitação para `NA_FILA`;
   - registra a auditoria com ator "sistema";
   - grava o evento na outbox.
3. A vaga fica livre e volta a ser oferecida ([UC-003](UC-003-propor-vaga.md)).
4. O paciente recebe o aviso de que a proposta expirou e de que continua na fila.

## Exceções

- **E1 — Paciente confirmou no mesmo instante:** o lock garante que só uma das operações vence. Se a confirmação vencer, o Worker encontra o agendamento `CONFIRMADO` e não faz nada.
- **E2 — Falha no meio do lote:** cada agendamento é uma transação própria; os já processados ficam gravados e os demais são pegos na próxima execução.

## Pós-condições

- Agendamentos vencidos em `EXPIRADO`, solicitações em `NA_FILA`, vagas livres.

## Critérios de aceite

- **Dado** uma proposta vencida, **quando** o job roda, **então** ela fica `EXPIRADO` e a solicitação volta para `NA_FILA`.
- **Dado** o job executado duas vezes seguidas, **quando** se compara o banco, **então** o resultado é o mesmo e nenhum aviso é duplicado (idempotência).
- **Dado** dois Workers rodando ao mesmo tempo, **quando** processam o mesmo lote, **então** nenhuma proposta é processada duas vezes.
- **Dado** o relógio fixado nos testes, **quando** o prazo ainda não venceu por um segundo, **então** a proposta não é expirada.
