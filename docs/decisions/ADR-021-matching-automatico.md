# 021 — Proposta automática da vaga, na ordem da fila

- **Status:** Aceito (provisório em 2026-10-12; confirmado pela UPE em 2026-10-15)
- **Data:** 2026-10-12

## Contexto

Não está definido quem propõe a vaga ao paciente: o sistema, por matching automático, ou o atendente, por escolha manual (**ABERTO-1** em [decisões em aberto](../requirements/open-questions.md)). O MVP precisava de um caminho para funcionar e ser demonstrado, então esta decisão nasceu provisória. Na reunião de 15/10/2026, a UPE confirmou: a proposta é automática e segue a ordem da fila ([ADR-024](ADR-024-protocolo-por-fila.md)).

## Decisão

- O Worker propõe a vaga ao primeiro da fila daquela vaga, na ordem de `ordenar_fila()`, assim que a vaga é criada, desbloqueada ou liberada.
- O prazo para confirmar (`expira_em`) é o menor entre o prazo da fila ([ADR-026](ADR-026-prazos-e-volta-ao-fim-da-fila.md)) e o horário da vaga menos a antecedência mínima (RN-008, `PROPOSTA_ANTECEDENCIA_MINIMA_HORAS`).
- Se sobrar menos que a janela mínima (`PROPOSTA_JANELA_MINIMA_HORAS`, padrão 12 horas) para o paciente responder, a vaga **não** é proposta. Ela fica livre e aparece no painel como "vaga sem proposta".
- A proposta manual pelo atendente fica para depois.

## Ponto único de troca

- Função de domínio `propor_vaga(solicitacao, vaga, proposto_por)`. Toda proposta passa por ela.
- O prazo vem de `calcular_expira_em()`; `None` significa "não propor".
- Flag `MATCHING_AUTOMATICO` (no MVP, `true`).
- `agendamento.proposto_por_usuario_id` continua anulável: nulo = automático. Os dois modos convivem sem migração.

## Se a proposta manual voltar a ser pedida

- Criar o endpoint `POST /api/v1/agendamentos`, que chama a mesma `propor_vaga()` passando o atendente em `proposto_por`.
- Desligar o job de matching com `MATCHING_AUTOMATICO=false`, se a proposta passar a ser só manual.
- Dar a permissão "propor vaga" ao ATENDENTE, dentro do escopo de `escopo_da_equipe()` ([ADR-025](ADR-025-escopo-por-fila.md)).
- Na tela 06, acrescentar a ação "Propor vaga".

## Alternativas consideradas

- **Proposta manual no MVP:** exige tela, endpoint e permissão a mais, e depende do atendente para a fila andar na demonstração.
- **Esperar a resposta da UPE:** bloqueia UC-003 e tudo que depende dele (UC-004, UC-005, UC-006).

## Consequências

- A fila anda sem intervenção da equipe; o índice único parcial decide a corrida entre propostas ([ADR-004](ADR-004-ocupacao-da-vaga.md)).
- Vagas que não deixam a janela mínima para o paciente responder ficam livres e visíveis no painel, sem proposta automática.
- O código não pode propor vaga por outro caminho que não seja `propor_vaga()`.
