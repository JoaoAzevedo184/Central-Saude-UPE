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
