# Decisões em aberto

Pontos que dependiam do grupo ou da UPE. Quando um ponto é resolvido, a resposta fica registrada aqui e o ADR correspondente é criado ou atualizado. As análises de cada ponto continuam abaixo como histórico.

**Em 15/10/2026, as quatro questões foram respondidas** em reunião com a diretora do Complexo Hospitalar da UPE que propôs o desafio. Não há questões abertas no momento.

| ID | Pergunta | Situação | Resposta |
| --- | --- | --- | --- |
| ABERTO-1 | Quem propõe a vaga: matching automático ou atendente? | **Respondida** em 15/10/2026 | Automática, na ordem da fila — [ADR-021](../decisions/ADR-021-matching-automatico.md) |
| ABERTO-2 | Existe regra oficial de prioridade? Cabe envelhecimento (aging)? | **Respondida** em 15/10/2026 | Cada fila tem seu protocolo de critérios com peso; sem aging — [ADR-024](../decisions/ADR-024-protocolo-por-fila.md) |
| ABERTO-3 | Atendentes e gestores veem só a própria unidade ou todas? | **Respondida** em 15/10/2026 | Escopo por fila: atendente nas suas filas, gestor por hospital ou central — [ADR-025](../decisions/ADR-025-escopo-por-fila.md) |
| ABERTO-4 | O que acontece com a solicitação quando o paciente falta? | **Respondida** em 15/10/2026 | Depois de 1 hora de tolerância, `FALTOU` e a solicitação volta para o fim da fila — [ADR-026](../decisions/ADR-026-prazos-e-volta-ao-fim-da-fila.md) |

A reunião também gerou o [ADR-027](../decisions/ADR-027-fila-como-entidade.md) (fila como entidade), o [ADR-028](../decisions/ADR-028-suspensao-de-acesso.md) (suspensão de acesso) e as propostas [ADR-029](../decisions/ADR-029-overbooking-por-vagas-extras.md) (overbooking) e [ADR-030](../decisions/ADR-030-historico-familiar-como-criterio.md) (histórico familiar), e manteve o [ADR-007](../decisions/ADR-007-paciente-ve-status.md) (o paciente vê o status, sem posição).

## ABERTO-1 — Quem propõe a vaga

**Resposta (15/10/2026, reunião com a diretora que propôs o desafio):** a proposta é automática e segue a ordem da fila. O ADR-021 passa a Aceito ([ADR-021](../decisions/ADR-021-matching-automatico.md)).

*Análise feita antes da resposta, mantida como histórico:*

**Decisão provisória do MVP:** matching automático pelo Worker; proposta manual pelo atendente fica para depois. Ponto único de troca: `propor_vaga()` e a flag `MATCHING_AUTOMATICO` ([ADR-021](../decisions/ADR-021-matching-automatico.md)). A tabela abaixo mostra o que muda se a resposta for outra.

| Onde | Se **automático** | Se **manual** |
| --- | --- | --- |
| Modelo | `agendamento.proposto_por_usuario_id` fica nulo | `proposto_por_usuario_id` preenchido pelo atendente; continua anulável (ADR-021) |
| Containers | Job de matching no **Worker**, disparado quando uma vaga é criada ou liberada | Endpoint `POST /api/v1/agendamentos` na **API** |
| Regra de negócio | Não propor se `expira_em` ultrapassar o horário da vaga, menos uma antecedência mínima (RN-008) | A mesma regra, como validação do endpoint |
| Autorização | Nenhuma permissão nova | Permissão "propor vaga" para ATENDENTE, sujeita ao escopo de ABERTO-3 |
| Protótipo | Sem mudança | A tela 06 ganha a ação "Propor vaga" |

## ABERTO-2 — Regra de prioridade e aging

**Resposta (15/10/2026, reunião com a diretora que propôs o desafio):** não há uma ordem única. Cada fila tem um protocolo de critérios com peso; a nota é a soma dos pontos, o risco tem três níveis e o empate é resolvido pela hora de chegada. Sem aging. O ADR-022 foi substituído pelo [ADR-024](../decisions/ADR-024-protocolo-por-fila.md).

*Análise feita antes da resposta, mantida como histórico:*

**Decisão provisória do MVP:** ordem fixa (classificação de risco → prioridade legal → data do pedido), regras simuladas, sem aging. Ponto único de troca: `ordenar_fila()` e o CHECK de `regra_prioridade.criterio` ([ADR-022](../decisions/ADR-022-ordem-da-fila-sem-aging.md)). A tabela abaixo mostra o que muda se a resposta for outra.

| Onde | Impacto |
| --- | --- |
| Modelo | Com aging, o CHECK de `regra_prioridade.criterio` ganha o valor `AGING` e `parametros` (dias para subir um degrau e teto). O aging nunca passa por cima de critério clínico ou legal |
| Consulta da fila | Com aging, a ordem depende do tempo e passa a ser calculada na consulta, não gravada |
| Autorização | Nenhum impacto |
| Protótipo | O painel "Ordem da fila" (tela 11) mostra a regra de aging, se aprovada |
| Se houver regra oficial | As regras correspondentes passam a `simulada = false`, com referência ao documento da UPE |

## ABERTO-3 — Escopo de acesso por unidade

**Resposta (15/10/2026, reunião com a diretora que propôs o desafio):** escopo por fila. O atendente vê só as filas atribuídas; o gestor vê um hospital ou a central inteira; o admin vê tudo. O ADR-023 foi substituído pelo [ADR-025](../decisions/ADR-025-escopo-por-fila.md).

*Análise feita antes da resposta, mantida como histórico:*

**Decisão provisória do MVP:** a equipe vê todas as unidades, mas toda rota da equipe já passa por `escopo_da_equipe()`. Ponto único de troca: `escopo_da_equipe()` e a flag `ESCOPO_POR_UNIDADE` ([ADR-023](../decisions/ADR-023-escopo-todas-as-unidades.md)). A tabela abaixo mostra o que muda se a resposta for outra.

| Onde | Se **por unidade** | Se **todas** |
| --- | --- | --- |
| Modelo | Tabela `usuario_unidade` (lotação) | A tabela não existe |
| Autorização | Filtro por unidade em toda consulta de fila, agendas e indicadores, aplicado por uma dependência do FastAPI que injeta o escopo do usuário | Só o papel decide |
| Solicitação sem unidade preferida | Precisa de uma regra que defina em qual fila ela aparece | Aparece em todas as filas da especialidade |
| Protótipo | Seletor de unidade nas telas 06 e 07 só para admin ou gestor geral | Seletor de unidade para todos da equipe |

## ABERTO-4 — Falta do paciente

**Resposta (15/10/2026, reunião com a diretora que propôs o desafio):** no dia da consulta há tolerância de 1 hora; depois disso, o agendamento vira `FALTOU` e a solicitação volta para o fim da fila, com o motivo informado ao paciente. Sem limite de faltas ([ADR-026](../decisions/ADR-026-prazos-e-volta-ao-fim-da-fila.md)).

*Análise feita antes da resposta, mantida como histórico:*

Quando um agendamento termina em `FALTOU`, a solicitação pode:

- voltar para `NA_FILA` (o paciente continua esperando);
- ser encerrada (o paciente precisa de um novo encaminhamento);
- seguir uma regra intermediária, como voltar à fila só na primeira falta.

| Onde | Impacto |
| --- | --- |
| Domínio | Nova transição no ciclo de vida da solicitação ([regras de negócio](business-rules.md)) |
| Modelo | Se houver limite de faltas, um contador ou consulta ao histórico de agendamentos da solicitação |
| Indicadores | Define se a falta conta como desistência no painel |
