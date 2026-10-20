# UC-007 — Validar solicitação

| | |
| --- | --- |
| **Ator principal** | Atendente |
| **Objetivo** | Acompanhar a fila, classificar o risco de uma solicitação nova e completar os critérios que cabem à equipe |
| **Requisitos** | RF-009, RF-010, RF-031, RF-032 |
| **Regras** | RN-006, RN-007, RN-010, RN-011, RN-015 |

> A classificação aqui é uma **simulação da regulação**: pelo [PRD](../../product/PRD.md), o risco vem da regulação.

## Pré-condições

- Atendente autenticado e ativo ([ADR-028](../../decisions/ADR-028-suspensao-de-acesso.md)), com a fila no escopo ([ADR-025](../../decisions/ADR-025-escopo-por-fila.md)).
- Solicitação `EM_ANALISE` ou `NA_FILA`.

## Fluxo principal — classificar

1. O atendente abre o painel de uma fila do seu escopo (`GET /equipe/filas/{fila_id}/solicitacoes`) e vê as solicitações com posição, risco, nota, nome abreviado e CPF mascarado.
2. Abre o detalhe de uma solicitação `EM_ANALISE` e informa a classificação de risco.
3. Numa única transação, o sistema:
   - trava a solicitação e confere escopo e estado;
   - muda para `NA_FILA`, com `data_entrada_fila` igual ao horário atual;
   - grava os eventos `CLASSIFICADA` (interno) e `ENTROU_NA_FILA` (visível ao paciente: "Seu pedido entrou na fila.");
   - grava a auditoria e a outbox `SOLICITACAO_NA_FILA`.

## Fluxo alternativo — A1: reclassificar

Em `NA_FILA`, o atendente muda o risco e informa o motivo (obrigatório, 3 a 500 caracteres). O sistema grava `RECLASSIFICADA` (interno) e a auditoria. O paciente não é avisado: não há outbox.

## Fluxo alternativo — A2: responder critérios da equipe

O atendente grava as respostas dos critérios de origem `REGULACAO` ou `EQUIPE` (`PUT /equipe/solicitacoes/{id}/respostas`). O sistema recalcula a nota com `calcular_nota`. Em `NA_FILA`, se a nota mudou, grava `RECLASSIFICADA` ("nota recalculada", interno). A auditoria guarda as respostas antes e depois.

## Exceções

- **E1 — Classificar em estado diferente de `EM_ANALISE` e `NA_FILA`:** `409`.
- **E2 — Responder critérios fora de `EM_ANALISE` e `NA_FILA`:** `409`; o estado é conferido antes da validação da entrada.
- **E3 — Critério de origem `PACIENTE` ou de outra fila:** `422`.
- **E4 — Fila fora do escopo:** `404`.
- **E5 — Reclassificar sem motivo:** `422`.

## Pós-condições

- `EM_ANALISE` → `NA_FILA` com risco, nota e `data_entrada_fila`; ou risco e nota atualizados, com histórico e auditoria.

## Critérios de aceite

- **Dado** uma solicitação `EM_ANALISE`, **quando** o atendente classifica, **então** ela vai para `NA_FILA` com `data_entrada_fila` igual a agora, e ficam gravados os eventos e a outbox (`test_uc007_classificar_em_analise_entra_na_fila`).
- **Dado** uma solicitação `NA_FILA`, **quando** o atendente reclassifica, **então** o motivo é obrigatório e o paciente não é avisado (`test_uc007_reclassificar_exige_motivo_e_nao_avisa_o_paciente`).
- **Dado** uma solicitação em outro estado, **quando** o atendente classifica, **então** a resposta é `409` (`test_uc007_classificar_em_outro_estado_retorna_409`).
- **Dado** respostas de critérios da equipe, **quando** são gravadas, **então** a nota é recalculada (`test_adr024_responder_criterios_recalcula_a_nota`).
- **Dado** uma solicitação `NA_FILA`, **quando** a nota muda, **então** grava-se `RECLASSIFICADA` (`test_adr024_nota_nova_na_fila_grava_reclassificada`).
- **Dado** um critério do paciente ou de outra fila, **quando** a equipe tenta responder, **então** a resposta é `422` (`test_adr024_equipe_nao_responde_criterio_do_paciente_nem_de_outra_fila`).
- **Dado** uma solicitação cancelada, **quando** a equipe tenta responder, **então** a resposta é `409` (`test_adr024_responder_em_solicitacao_cancelada_retorna_409`).
- **Dado** um atendente sem a fila no escopo, **quando** acessa, **então** a resposta é `404` (`test_adr025_atendente_fora_do_escopo_recebe_404`).
- **Dado** gestor ou admin, **quando** tenta escrever, **então** a resposta é `403`; só o atendente escreve (`test_rbac_so_atendente_escreve`).

### Painel (RF-031 e RF-032)

- A ordem do painel é a de `ordenar_fila()`: risco, nota decrescente, chegada, id (`test_rn015_empate_resolvido_pela_chegada`, `test_rn015_reclassificar_para_vermelho_muda_a_posicao`, `test_rn015_ordem_da_sql_igual_a_ordenar_fila`).
- A posição é a real, mesmo na segunda página, e só existe para `NA_FILA` (`test_rf031_posicao_real_na_segunda_pagina`, `test_rf031_posicao_so_para_na_fila_e_ordenacao_por_chegada`).
- A lista traz nome abreviado e CPF mascarado (`test_lgpd_painel_com_nome_abreviado_e_cpf_mascarado`).
- As leituras da equipe são auditadas (`test_am007_leituras_da_equipe_sao_auditadas`).

## Segurança

- Só ATENDENTE escreve; GESTOR e ADMIN só leem ([controle de acesso](../../security/access-control.md)).
- Risco e nota nunca vêm do paciente; reclassificar exige motivo e fica na auditoria (AM-016 no [modelo de ameaças](../../security/threat-model.md)).
- O motivo livre da reclassificação não aparece no painel, só no detalhe ([proteção de dados](../../security/data-protection.md)).
