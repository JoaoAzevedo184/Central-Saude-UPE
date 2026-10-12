# Decisões em aberto

Pontos que dependem do grupo ou da UPE. ABERTO-1 a 3 têm decisão provisória para o MVP; ABERTO-4 não foi assumido no design. Cada tabela mostra onde a resposta muda o modelo, os containers ou a autorização. Quando um ponto for resolvido, registre a resposta aqui e crie ou atualize o ADR correspondente.

| ID | Pergunta | Depende de | Situação |
| --- | --- | --- | --- |
| ABERTO-1 | Quem propõe a vaga: matching automático ou atendente? | Grupo e UPE | Provisório — [ADR-021](../decisions/ADR-021-matching-automatico.md) |
| ABERTO-2 | Existe regra oficial de prioridade? Cabe envelhecimento (aging)? | UPE | Provisório — [ADR-022](../decisions/ADR-022-ordem-da-fila-sem-aging.md) |
| ABERTO-3 | Atendentes e gestores veem só a própria unidade ou todas? | UPE | Provisório — [ADR-023](../decisions/ADR-023-escopo-todas-as-unidades.md) |
| ABERTO-4 | O que acontece com a solicitação quando o paciente falta? | Grupo e UPE | Aberto |

## ABERTO-1 — Quem propõe a vaga

**Decisão provisória do MVP:** matching automático pelo Worker; proposta manual pelo atendente fica para depois. Ponto único de troca: `propor_vaga()` e a flag `MATCHING_AUTOMATICO` ([ADR-021](../decisions/ADR-021-matching-automatico.md)). A tabela abaixo mostra o que muda se a resposta for outra.

| Onde | Se **automático** | Se **manual** |
| --- | --- | --- |
| Modelo | `agendamento.proposto_por_usuario_id` fica nulo | `proposto_por_usuario_id` preenchido pelo atendente; continua anulável (ADR-021) |
| Containers | Job de matching no **Worker**, disparado quando uma vaga é criada ou liberada | Endpoint `POST /api/v1/agendamentos` na **API** |
| Regra de negócio | Não propor se `expira_em` ultrapassar o horário da vaga, menos uma antecedência mínima (RN-008) | A mesma regra, como validação do endpoint |
| Autorização | Nenhuma permissão nova | Permissão "propor vaga" para ATENDENTE, sujeita ao escopo de ABERTO-3 |
| Protótipo | Sem mudança | A tela 06 ganha a ação "Propor vaga" |

## ABERTO-2 — Regra de prioridade e aging

**Decisão provisória do MVP:** ordem fixa (classificação de risco → prioridade legal → data do pedido), regras simuladas, sem aging. Ponto único de troca: `ordenar_fila()` e o CHECK de `regra_prioridade.criterio` ([ADR-022](../decisions/ADR-022-ordem-da-fila-sem-aging.md)). A tabela abaixo mostra o que muda se a resposta for outra.

| Onde | Impacto |
| --- | --- |
| Modelo | Com aging, o CHECK de `regra_prioridade.criterio` ganha o valor `AGING` e `parametros` (dias para subir um degrau e teto). O aging nunca passa por cima de critério clínico ou legal |
| Consulta da fila | Com aging, a ordem depende do tempo e passa a ser calculada na consulta, não gravada |
| Autorização | Nenhum impacto |
| Protótipo | O painel "Ordem da fila" (tela 11) mostra a regra de aging, se aprovada |
| Se houver regra oficial | As regras correspondentes passam a `simulada = false`, com referência ao documento da UPE |

## ABERTO-3 — Escopo de acesso por unidade

**Decisão provisória do MVP:** a equipe vê todas as unidades, mas toda rota da equipe já passa por `escopo_da_equipe()`. Ponto único de troca: `escopo_da_equipe()` e a flag `ESCOPO_POR_UNIDADE` ([ADR-023](../decisions/ADR-023-escopo-todas-as-unidades.md)). A tabela abaixo mostra o que muda se a resposta for outra.

| Onde | Se **por unidade** | Se **todas** |
| --- | --- | --- |
| Modelo | Tabela `usuario_unidade` (lotação) | A tabela não existe |
| Autorização | Filtro por unidade em toda consulta de fila, agendas e indicadores, aplicado por uma dependência do FastAPI que injeta o escopo do usuário | Só o papel decide |
| Solicitação sem unidade preferida | Precisa de uma regra que defina em qual fila ela aparece | Aparece em todas as filas da especialidade |
| Protótipo | Seletor de unidade nas telas 06 e 07 só para admin ou gestor geral | Seletor de unidade para todos da equipe |

## ABERTO-4 — Falta do paciente

Quando um agendamento termina em `FALTOU`, a solicitação pode:

- voltar para `NA_FILA` (o paciente continua esperando);
- ser encerrada (o paciente precisa de um novo encaminhamento);
- seguir uma regra intermediária, como voltar à fila só na primeira falta.

| Onde | Impacto |
| --- | --- |
| Domínio | Nova transição no ciclo de vida da solicitação ([regras de negócio](business-rules.md)) |
| Modelo | Se houver limite de faltas, um contador ou consulta ao histórico de agendamentos da solicitação |
| Indicadores | Define se a falta conta como desistência no painel |
