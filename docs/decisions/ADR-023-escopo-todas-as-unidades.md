# 023 — Equipe vê todas as unidades no MVP

- **Status:** Provisório
- **Data:** 2026-10-12

## Contexto

Não está definido se atendentes e gestores veem só a própria unidade ou todas (**ABERTO-3** em [decisões em aberto](../requirements/open-questions.md)). A pergunta foi enviada à UPE. Filtro por unidade exige tabela de lotação e regra para solicitações sem unidade preferida.

## Decisão

- No MVP, atendentes e gestores veem todas as unidades.
- Mesmo assim, desde o primeiro endpoint, toda rota da equipe recebe a dependência `escopo = Depends(escopo_da_equipe)`, e as consultas recebem o escopo como parâmetro.
- Hoje o escopo devolvido é "todas as unidades".
- Solicitação sem unidade preferida aparece em todas as filas da especialidade.

## Ponto único de troca

- Dependência `escopo_da_equipe()`.
- Flag `ESCOPO_POR_UNIDADE` (no MVP, `false`).
- A tabela `usuario_unidade` só será criada se a decisão mudar.

## Como trocar se a UPE responder diferente

- Criar a tabela `usuario_unidade` (lotação) numa migração nova.
- Fazer `escopo_da_equipe()` devolver as unidades do usuário quando `ESCOPO_POR_UNIDADE=true`.
- Definir em qual fila aparece a solicitação sem unidade preferida.
- As rotas e consultas não mudam: já recebem o escopo.

## Alternativas consideradas

- **Escopo por unidade no MVP:** exige lotação, cadastro e regra extra sem resposta da instituição.
- **Sem dependência de escopo até a resposta:** obrigaria revisar todas as rotas da equipe depois.

## Consequências

- A visão ampla é mitigada pela auditoria das consultas da equipe (AM-007 em [modelo de ameaças](../security/threat-model.md)).
- Trocar o escopo não exige mexer nas rotas.
- Toda rota da equipe sem `escopo_da_equipe()` é defeito de revisão.
- Continua sujeita à resposta da UPE.
