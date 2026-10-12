# 021 — Matching automático da vaga no MVP

- **Status:** Provisório
- **Data:** 2026-10-12

## Contexto

Não está definido quem propõe a vaga ao paciente: o sistema, por matching automático, ou o atendente, por escolha manual (**ABERTO-1** em [decisões em aberto](../requirements/open-questions.md)). A pergunta foi enviada à UPE e ainda não tem resposta. O MVP precisa de um caminho para funcionar e ser demonstrado.

## Decisão

- No MVP, o Worker propõe a vaga ao primeiro elegível da fila assim que uma vaga é criada, desbloqueada ou liberada.
- Se o prazo de resposta não couber antes do horário da vaga menos a antecedência mínima (RN-008, `PROPOSTA_ANTECEDENCIA_MINIMA_HORAS`), a vaga **não** é proposta. Ela fica livre e aparece no painel como "vaga sem proposta".
- A proposta manual pelo atendente fica para depois.

## Ponto único de troca

- Função de domínio `propor_vaga(solicitacao, vaga, proposto_por)`. Toda proposta passa por ela.
- Flag `MATCHING_AUTOMATICO` (no MVP, `true`).
- `agendamento.proposto_por_usuario_id` continua anulável: nulo = automático. Os dois modos convivem sem migração.

## Como trocar se a UPE responder diferente

- Criar o endpoint `POST /api/v1/agendamentos`, que chama a mesma `propor_vaga()` passando o atendente em `proposto_por`.
- Desligar o job de matching com `MATCHING_AUTOMATICO=false`, se a proposta passar a ser só manual.
- Dar a permissão "propor vaga" ao ATENDENTE, dentro do escopo de `escopo_da_equipe()` ([ADR-023](ADR-023-escopo-todas-as-unidades.md)).
- Na tela 06, acrescentar a ação "Propor vaga".

## Alternativas consideradas

- **Proposta manual no MVP:** exige tela, endpoint e permissão a mais, e depende do atendente para a fila andar na demonstração.
- **Esperar a resposta da UPE:** bloqueia UC-003 e tudo que depende dele (UC-004, UC-005, UC-006).

## Consequências

- A fila anda sem intervenção da equipe; o índice único parcial decide a corrida entre propostas ([ADR-004](ADR-004-ocupacao-da-vaga.md)).
- Vagas que não cabem na antecedência mínima ficam livres e visíveis no painel, sem proposta automática.
- O código não pode propor vaga por outro caminho que não seja `propor_vaga()`.
- Continua sujeita à resposta da UPE.
