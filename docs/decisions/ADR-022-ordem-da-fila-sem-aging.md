# 022 — Ordem fixa da fila, sem aging

- **Status:** Substituído por [ADR-024](ADR-024-protocolo-por-fila.md) em 2026-10-15
- **Data:** 2026-10-12

## Contexto

Não há regra oficial de prioridade da UPE, nem definição sobre envelhecimento (aging) na fila (**ABERTO-2** em [decisões em aberto](../requirements/open-questions.md)). O [ADR-011](ADR-011-regras-de-prioridade.md) já guarda as regras em tabela, marcadas como simuladas. Falta fixar quais critérios o MVP implementa.

## Decisão

- A fila é ordenada por: classificação de risco da regulação → prioridade legal → data do pedido.
- As regras continuam marcadas como simuladas (`simulada = true`).
- Não há aging no MVP.

## Ponto único de troca

- Função `ordenar_fila(solicitacoes, regras)` em `dominio/fila`. Nenhum outro lugar ordena a fila.
- `regra_prioridade.criterio` é `text` com `CHECK (criterio IN ('CLASSIFICACAO_RISCO','PRIORIDADE_LEGAL','DATA_PEDIDO'))`, não enum do Postgres.

## Como trocar se a UPE responder diferente

- **Regra oficial diferente:** ajustar as linhas de `regra_prioridade` (ordem, parâmetros, `simulada = false`, referência ao documento da UPE). Sem deploy, se os critérios já existirem.
- **Com aging:** acrescentar `AGING` ao CHECK numa migração nova, implementar o critério em `ordenar_fila()` e inserir a linha na tabela. A ordem passa a depender do tempo e é calculada na consulta, com `Relogio`. O aging nunca passa por cima de critério clínico ou legal.

## Alternativas consideradas

- **Enum do Postgres para `criterio`:** acrescentar valor exige `ALTER TYPE`, mais rígido que trocar um CHECK.
- **Aging já no MVP:** inventaria um critério que a instituição não definiu.

## Consequências

- A ordem da fila é determinística e testável sem banco.
- Acrescentar um critério custa uma migração pequena e código num único lugar.
- Continua sujeita à resposta da UPE.
