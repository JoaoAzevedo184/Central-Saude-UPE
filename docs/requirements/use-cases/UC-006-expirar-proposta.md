# UC-006 — Expirar proposta

| | |
| --- | --- |
| **Ator principal** | Sistema (Worker) |
| **Objetivo** | Liberar as vagas cujas propostas não foram confirmadas no prazo e devolver as solicitações ao fim da fila |
| **Requisitos** | RF-015, RF-016, RF-018, RF-029 |
| **Regras** | RN-003, RN-005, RN-010, RN-011, RN-012, RN-014 |

## Gatilho

- Execução periódica do job de expiração no Worker.

## Fluxo principal

1. O Worker seleciona um lote de agendamentos `PROPOSTO` com `expira_em` no passado, usando `FOR UPDATE SKIP LOCKED`.
2. Para cada agendamento, numa transação, o Worker:
   - confirma que ainda está `PROPOSTO`;
   - muda para `EXPIRADO`;
   - devolve a solicitação para `NA_FILA` no **fim da fila**, com `reentrar_no_fim_da_fila()`: `data_entrada_fila` recebe o horário atual (RN-014);
   - registra na linha do tempo os eventos `PROPOSTA_EXPIRADA` e `REENTROU_NA_FILA`, este com o motivo "Você não confirmou a vaga no prazo" e visível ao paciente;
   - registra a auditoria com ator "sistema";
   - grava o evento na outbox.
3. A vaga fica livre e volta a ser oferecida ([UC-003](UC-003-propor-vaga.md)).
4. O paciente recebe o aviso de que a proposta expirou e de que a solicitação voltou para a fila, com o motivo e sem posição.

## Exceções

- **E1 — Paciente confirmou no mesmo instante:** o lock garante que só uma das operações vence. Se a confirmação vencer, o Worker encontra o agendamento `CONFIRMADO` e não faz nada.
- **E2 — Falha no meio do lote:** cada agendamento é uma transação própria; os já processados ficam gravados e os demais são pegos na próxima execução.

## Pós-condições

- Agendamentos vencidos em `EXPIRADO`, solicitações em `NA_FILA` com nova `data_entrada_fila`, vagas livres.

## Implementação

Job `expirar_propostas`, a cada `WORKER_INTERVALO_EXPIRACAO_S`. Expira quando `expira_em <= agora`. Trava solicitação e agendamento com `SKIP LOCKED`; item travado fica para a próxima execução. Outbox `PROPOSTA_EXPIRADA`.

## Critérios de aceite

- **Dado** uma proposta vencida, **quando** o job roda, **então** ela fica `EXPIRADO`, a solicitação volta para `NA_FILA` com `data_entrada_fila` igual ao horário do job e fica atrás das solicitações de mesmo risco e mesma nota (`test_uc006_expira_e_volta_para_o_fim_da_fila`).
- **Dado** uma proposta expirada, **quando** o paciente consulta a linha do tempo, **então** vê o motivo "você não confirmou a vaga no prazo" e não vê posição nem tamanho da fila.
- **Dado** o job executado duas vezes seguidas, **quando** se compara o banco, **então** o resultado é o mesmo e nenhum aviso é duplicado (`test_uc006_rodar_duas_vezes_nao_muda_nada`).
- **Dado** dois Workers rodando ao mesmo tempo, **quando** processam o mesmo lote, **então** nenhuma proposta é processada duas vezes (garantido por `FOR UPDATE SKIP LOCKED`; o teste de concorrência cobre a proposta, `test_adr004_rn002_propor_vagas_concorrente_nao_duplica`).
- **Dado** o relógio fixado nos testes, **quando** o prazo ainda não venceu por um segundo, **então** a proposta não é expirada (`test_uc006_um_segundo_antes_do_prazo_nao_expira`).
- **Dado** uma proposta expirada, **quando** o Worker propõe de novo, **então** a vaga vai para a próxima da fila, e o ciclo propor → expirar → propor ao próximo → confirmar funciona de ponta a ponta (`test_uc003_uc006_uc004_ciclo_completo`, `test_uc003_nunca_reoferece_a_mesma_vaga_depois_de_expirar`).
