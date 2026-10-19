# UC-008 — Registrar comparecimento ou falta

| | |
| --- | --- |
| **Ator principal** | Atendente |
| **Objetivo** | Encerrar o agendamento confirmado conforme o paciente compareceu ou faltou |
| **Requisitos** | RF-017, RF-018, RF-029, RF-030 |
| **Regras** | RN-010, RN-011, RN-013, RN-014 |

## Pré-condições

- Atendente autenticado e ativo ([ADR-028](../../decisions/ADR-028-suspensao-de-acesso.md)).
- Agendamento `CONFIRMADO` numa fila do escopo do atendente ([ADR-025](../../decisions/ADR-025-escopo-por-fila.md)).

## Fluxo principal — comparecimento

1. O atendente abre a agenda do dia de uma fila do seu escopo.
2. O atendente marca o paciente como presente.
3. Numa única transação, o sistema:
   - trava o agendamento e verifica que ele está `CONFIRMADO`;
   - muda o agendamento para `REALIZADO` e a solicitação para `ATENDIDA`;
   - registra o evento `ATENDIDA` na linha do tempo, a auditoria e o evento na outbox.

## Fluxo alternativo A1 — falta

1. O horário da vaga passou e o paciente não chegou.
2. O atendente marca a falta.
3. O sistema verifica com `pode_marcar_falta()` que já passou `início da vaga + tolerância da fila` (padrão 1 hora, RN-013).
4. Numa única transação, o sistema:
   - muda o agendamento para `FALTOU`;
   - devolve a solicitação para `NA_FILA` no **fim da fila**, com `reentrar_no_fim_da_fila()`: `data_entrada_fila` recebe o horário atual (RN-014);
   - registra na linha do tempo os eventos `FALTOU` e `REENTROU_NA_FILA`, este com o motivo "Você não compareceu à consulta" e visível ao paciente;
   - registra a auditoria e o evento na outbox.
5. O paciente recebe o aviso com o motivo, sem posição na fila.

## Exceções

- **E1 — Falta antes do fim da tolerância:** o sistema responde `409` e não altera nada. Exatamente no limite ainda não é falta.
- **E2 — Agendamento não está `CONFIRMADO`** (já registrado, cancelado ou expirado): o sistema responde `409`.
- **E3 — Agendamento de fila fora do escopo do atendente:** o sistema responde `404`, sem revelar que o recurso existe.

## Pós-condições

- Comparecimento: agendamento `REALIZADO`, solicitação `ATENDIDA`.
- Falta: agendamento `FALTOU`, solicitação `NA_FILA` com nova `data_entrada_fila`.
- Nos dois casos: linha do tempo, auditoria e evento na outbox.

## Critérios de aceite

- **Dado** um agendamento `CONFIRMADO` às 8h numa fila com tolerância de 60 minutos, **quando** o atendente marca falta às 9h, **então** a resposta é `409` e nada muda.
- **Dado** o mesmo agendamento, **quando** o atendente marca falta às 9h00min01s, **então** o agendamento fica `FALTOU` e a solicitação volta para `NA_FILA` com `data_entrada_fila` igual ao horário do registro.
- **Dado** uma solicitação que voltou ao fim da fila, **quando** a fila é ordenada, **então** ela fica atrás das solicitações de mesmo risco e mesma nota que já estavam na fila.
- **Dado** uma falta registrada, **quando** o paciente consulta a linha do tempo, **então** vê o motivo "você não compareceu à consulta" e não vê posição nem tamanho da fila.
- **Dado** um atendente sem a fila do agendamento no seu escopo, **quando** tenta registrar comparecimento ou falta, **então** a resposta é `404`.
- **Dado** o relógio fixado nos testes, **quando** a falta é avaliada, **então** o resultado depende só do `Relogio`.

## Segurança

- Só ATENDENTE ativo, nas filas do seu escopo ([controle de acesso](../../security/access-control.md)).
- O registro de falta é auditado com o ator: uma falta indevida empurra o paciente para o fim da fila (AM-016 no [modelo de ameaças](../../security/threat-model.md)).
