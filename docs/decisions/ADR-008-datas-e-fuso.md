# 008 — Datas com fuso no banco, exibição em America/Recife

- **Status:** Aceito
- **Data:** 2026-10-12

## Contexto

Prazos de resposta e horários de consulta são comparados o tempo todo (uma proposta venceu? o prazo passa do horário da vaga?). Datas sem fuso geram erros silenciosos quando o servidor, o container ou o navegador estão em fusos diferentes.

## Decisão

- Todo instante é gravado como `timestamptz`.
- A API recebe e devolve datas em ISO 8601 com deslocamento de fuso.
- As interfaces exibem no fuso `America/Recife`.
- Campos que representam só um dia, sem hora (como a data do pedido e a data de nascimento), usam `date`.

## Consequências

- Nenhuma comparação de horário é feita com datas "ingênuas" (sem fuso) no código Python.
- Testes que envolvem prazos devem fixar o relógio, em vez de depender da hora real.
