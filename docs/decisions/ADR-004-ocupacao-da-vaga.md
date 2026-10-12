# 004 — Ocupação da vaga derivada do agendamento

- **Status:** Aceito
- **Data:** 2026-10-12

## Contexto

O risco central do sistema é entregar a mesma vaga a dois pacientes, por exemplo quando uma vaga cancelada é reaproveitada ao mesmo tempo em que um atendente faz uma proposta. Guardar "ocupada" na tabela `vaga` e no `agendamento` cria dois estados que podem divergir.

## Decisão

A única fonte de verdade sobre a ocupação é este índice:

```sql
CREATE UNIQUE INDEX ux_agendamento_vaga_ativa
  ON agendamento (vaga_id)
  WHERE status IN ('PROPOSTO', 'CONFIRMADO');
```

A tabela `vaga` guarda apenas estados administrativos (`ATIVA` ou `BLOQUEADA`). "Vaga livre" é uma vaga ativa sem agendamento ativo.

## Alternativas consideradas

- **Coluna `ocupada` na vaga, protegida por lock na aplicação:** funciona se todo código lembrar de travar a linha; um único caminho esquecido gera overbooking.

## Consequências

- Duas propostas concorrentes para a mesma vaga: uma grava, a outra recebe violação de unicidade, que a API traduz em `409 Conflict`.
- Cancelar ou expirar um agendamento libera a vaga automaticamente, sem atualizar outra tabela.
- Precisa de teste de concorrência: duas transações simultâneas tentando propor a mesma vaga, e só uma pode vencer.
