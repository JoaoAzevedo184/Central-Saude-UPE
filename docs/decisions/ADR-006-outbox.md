# 006 — Outbox transacional para notificações

- **Status:** Aceito
- **Data:** 2026-10-12

## Contexto

Quando uma vaga é proposta, o banco precisa ser atualizado e o paciente precisa ser avisado. Enviar o e-mail dentro da transação deixa a requisição lenta, e se o envio funcionar mas a transação falhar, o paciente recebe aviso de algo que não existe. Fazer o contrário (gravar e depois enviar) perde o aviso se o processo cair no meio.

## Decisão

- A mudança de estado e um registro na tabela `outbox` são gravados **na mesma transação**.
- O Worker consome os eventos pendentes, cria as notificações e faz o envio pelos canais ([ADR-005](ADR-005-worker-separado.md)).
- Falhas incrementam `tentativas` e agendam `proximo_retry_em`; depois de um limite, o evento fica `FALHOU` para análise.

## Consequências

- Nenhum aviso é perdido e nenhum aviso é enviado sobre algo que não foi gravado.
- A entrega é "pelo menos uma vez": o processamento precisa tolerar o mesmo evento chegando duas vezes, sem duplicar notificações.
- Há um pequeno atraso entre a ação e o e-mail, igual ao intervalo de leitura do Worker.

## Detalhes de implementação

Acrescentados em 2026-10-21, sem mudar a decisão.

- **Ligação evento → aviso:** `notificacao.outbox_id` aponta para o evento que a originou. `UNIQUE (outbox_id, usuario_id, canal)` (`uq_notificacao_outbox_usuario_canal`) garante a idempotência: o mesmo evento processado duas vezes usa `ON CONFLICT DO NOTHING` e não duplica aviso.
- **Consumo:** `processar_outbox` trava cada evento com `FOR UPDATE SKIP LOCKED`. Evento novo (`tentativas = 0`) está sempre vencido; a espera de `proximo_retry_em` vale só para novas tentativas (1, 5, 15 e 60 min, até `OUTBOX_MAX_TENTATIVAS`, depois `FALHOU`).
- **Aviso no site e e-mail:** o aviso no site nasce `ENVIADA`. O e-mail nasce `PENDENTE` e o job `enviar_emails` o envia pelo `CanalNotificacao`, com as mesmas esperas.
- **`CANCELADA`:** e-mail que deixou de valer no envio (sem e-mail cadastrado; lembrete com agendamento não mais `CONFIRMADO` ou consentimento `LEMBRETE_EMAIL` revogado) vira `CANCELADA` e não sai.
- **Lembrete:** não vem da outbox. O job `enviar_lembretes` cria o aviso das consultas `CONFIRMADO` nas próximas `LEMBRETE_ANTECEDENCIA_HORAS` (índice único parcial em `agendamento_id, tipo, canal` para `tipo = 'LEMBRETE'`).
- **Pelo menos uma vez:** se o Worker cair depois de enviar e antes do commit, o e-mail sai de novo na rodada seguinte. O lembrete é reconferido no envio, sem trava.
- **Lote máximo:** cada rodada de job processa no máximo `WORKER_LOTE_MAXIMO` itens (padrão 100); o resto fica para a rodada seguinte.
