# 011 — Regras de prioridade em tabela, marcadas como simuladas

- **Status:** Aceito
- **Data:** 2026-10-12

## Contexto

O próprio desafio avisa que as regras de prioridade devem ser definidas pela instituição, não inventadas pela equipe. Ainda assim, o MVP precisa de uma fila ordenada para funcionar e ser demonstrado.

## Decisão

- As regras ficam na tabela `regra_prioridade`, com `ordem`, `criterio`, `parametros` e a marca `simulada`.
- Regras de exemplo, aplicadas em sequência:
  1. classificação de risco recebida da regulação;
  2. prioridade legal registrada no pedido;
  3. data do pedido.
- A tela de administração mostra que as regras são exemplos e que os critérios oficiais são da instituição.

## Consequências

- Trocar a ordem ou os parâmetros não exige deploy.
- Um critério novo (por exemplo, aging) exige código novo para o critério e uma linha nova na tabela; ver **ABERTO-2** em [decisões em aberto](../requirements/open-questions.md) e a decisão provisória [ADR-022](ADR-022-ordem-da-fila-sem-aging.md).
- Quando houver regra oficial, as linhas correspondentes passam a `simulada = false`, com referência ao documento da UPE.
