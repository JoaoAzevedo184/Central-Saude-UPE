# 024 — Cada fila tem seu protocolo: critérios com peso

- **Status:** Aceito
- **Data:** 2026-10-15
- **Substitui:** [ADR-022](ADR-022-ordem-da-fila-sem-aging.md)

## Contexto

O [ADR-022](ADR-022-ordem-da-fila-sem-aging.md) fixou provisoriamente uma ordem única para todas as filas (risco → prioridade legal → data do pedido), à espera da resposta da UPE (**ABERTO-2**). Na reunião de 15/10/2026, a diretora do Complexo Hospitalar da UPE que propôs o desafio explicou que cada serviço prioriza de um jeito. Na laqueadura tubária pesam o número de filhos, a idade e ter um filho com doença neurodegenerativa. Na mamografia pesa o histórico familiar. Na anticoagulação pesa o uso do medicamento. Uma lista fixa de critérios para todo o hospital não representa isso.

## Decisão

- Cada fila ([ADR-027](ADR-027-fila-como-entidade.md)) tem o seu **protocolo**: uma lista de critérios em `criterio_fila`, cada um com tipo (`SIM_NAO`, `NUMERO`, `OPCAO`), **peso** e origem da resposta (`PACIENTE`, `REGULACAO`, `EQUIPE`).
- A resposta de cada critério vira **pontos** (`resposta_criterio.pontos`). A **nota** da solicitação é a soma dos pontos (`solicitacao.nota`), recalculada pelo domínio sempre que uma resposta é gravada.
  - `SIM_NAO`: "sim" vale o peso; "não" vale 0.
  - `NUMERO`: vale peso × fator da faixa em que o valor cai (`parametros.faixas`); fora de todas as faixas vale 0.
  - `OPCAO`: vale peso × fator da opção escolhida (`parametros.opcoes`).
- A classificação de risco da regulação tem **três** níveis: `VERMELHO`, `AMARELO` e `VERDE`. `AZUL` deixa de existir.
- A fila é ordenada por:
  1. risco: `VERMELHO`, depois `AMARELO`, depois `VERDE`;
  2. nota, da maior para a menor;
  3. hora de chegada na fila (`data_entrada_fila`), da mais antiga para a mais nova.
- **Prioridade legal** (por exemplo, 60 anos ou mais) deixa de ser coluna da solicitação: vira um critério com peso no protocolo da fila que a usa.
- Os critérios e os pesos do protótipo continuam simulados (`criterio_fila.simulado = true`, [ADR-011](ADR-011-regras-de-prioridade.md)).

## Ponto único de troca

- `ordenar_fila()` em `app/dominio/fila/ordenacao.py`. Nenhum outro lugar ordena a fila.
- `calcular_pontos()` e `calcular_nota()` em `app/dominio/fila/criterios.py`.
- A posição resultante é calculada na consulta e nunca gravada ([ADR-007](ADR-007-paciente-ve-status.md)).

## Alternativas consideradas

- **Manter a ordem fixa do ADR-022:** não representa os protocolos de cada serviço, que a UPE descreveu.
- **Regras como expressões livres (fórmulas):** mais flexível, mas difícil de validar, de testar e de explicar na tela de administração.
- **Critérios como colunas da solicitação:** cada fila nova exigiria migração.
- **Aging (envelhecimento na fila):** a UPE não pediu. Fica fora; a hora de chegada só desempata.

## Consequências

- Cada fila pode ter um protocolo diferente sem migração nem deploy: basta cadastrar critérios.
- A nota é gravada para a ordenação usar índice. Ela precisa ser recalculada em toda gravação de resposta, sempre pelo domínio.
- `resposta_criterio` usa FK composta com `fila_id`, para o banco recusar uma resposta a critério de outra fila ([modelo de dados](../architecture/data-model.md)).
- A tela de administração precisa editar critérios, pesos e faixas, e mostrar que são simulados.
