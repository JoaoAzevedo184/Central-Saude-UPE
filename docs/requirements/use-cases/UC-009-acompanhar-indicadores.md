# UC-009 — Acompanhar indicadores

| | |
| --- | --- |
| **Ator principal** | Gestor (o Admin também consulta) |
| **Objetivo** | Acompanhar, por período e por semana, como as propostas, as vagas e a fila estão se comportando |
| **Requisitos** | RF-021, RF-037 |
| **Regras** | RN-021, RN-014, RN-005 |

## Pré-condições

- Gestor ou Admin autenticado, ativo ([ADR-028](../../decisions/ADR-028-suspensao-de-acesso.md)) e **sem senha temporária pendente** (RN-022).
- O escopo vem de `escopo_da_equipe()` ([ADR-025](../../decisions/ADR-025-escopo-por-fila.md)): o gestor vê as filas das suas unidades; gestor sem unidade e Admin veem a central inteira.

## Fluxo principal

1. O gestor informa o período, de `de` a `ate`, em dias de `America/Recife`, inclusivos, de 1 a 366 dias (`GET /api/v1/equipe/indicadores?de=AAAA-MM-DD&ate=AAAA-MM-DD`). Opcionalmente restringe a uma unidade (`unidade_id`) ou a uma fila (`fila_id`); o filtro só encolhe o escopo.
2. O sistema calcula, no banco e num número fixo de consultas, as contagens de cada família com a sua âncora de tempo e as agrupa pela semana de Recife (segunda-feira) (RN-021):
   - propostas: `confirmadas`, `recusadas`, `expiradas`, `propostas_canceladas_sem_resposta` e as taxas de confirmação, recusa e expiração;
   - atendimento: `realizadas`, `faltas` e `taxa_faltas`;
   - solicitações: `solicitacoes_criadas`, `desistencias` e `taxa_desistencia`;
   - vagas: `vagas_ofertadas`, `vagas_ocupadas`, `vagas_reaproveitadas` e `vagas_perdidas`;
   - `tempo_de_espera` (quantidade, mediana e p90, em dias) e `fila_atual` por cor de risco.
3. O sistema grava a auditoria `CONSULTAR_INDICADORES` com o período e os filtros, e responde `totais`, `semanas` (todas as semanas que tocam o período, mesmo sem dado), `tempo_de_espera` e `fila_atual`.

## Fluxos alternativos

- **A1 — Período sem dado:** as contagens vêm `0` e as razões, `null` (nunca `0`). O tempo de espera vem `null`.
- **A2 — Filtro por unidade ou fila:** só as filas do escopo que casam com o filtro entram nas contas.

## Exceções

- **E1 — Período inválido** (`ate` antes de `de`, mais de 366 dias, data fora de 2000-01-01 a 2100-12-31, parâmetro ausente): `422`.
- **E2 — Unidade ou fila fora do escopo, inexistente ou sem nenhuma fila no escopo:** `404`, sem auditoria.
- **E3 — Atendente ou paciente:** `403`. Sem sessão, `401`. Senha temporária pendente, `403` `troca-de-senha-obrigatoria`.
- **E4 — Consulta acima do tempo máximo** (`INDICADORES_TIMEOUT_S`, padrão 5 s): `503` `/problemas/consulta-demorada` com `Retry-After: 30` e mensagem neutra; nunca `500`.

## Pós-condições

- Nada é alterado, exceto a linha de auditoria da leitura.
- A resposta não traz dado de paciente (nome, CPF, nota, risco individual), nem posição, nem tamanho de fila visível ao paciente (ADR-007: o `fila_atual` é só da equipe).

## Critérios de aceite


- **Dado** um atendente, um gestor e um admin, **quando** cada um consulta os indicadores, **então** gestor e admin recebem `200` e o atendente, `403`; sem sessão, `401` (`test_rf037_so_gestor_e_admin_leem`).
- **Dado** um período com `ate` antes de `de`, com mais de 366 dias ou sem um dos dois parâmetros, **quando** o gestor consulta, **então** a resposta é `422`; um período de exatamente 366 dias vale (`test_rf037_periodo_invalido_responde_422`, `test_rf037_periodo_de_366_dias_vale`).
- **Dado** um gestor com unidades atribuídas, **quando** consulta, **então** só as filas dessas unidades entram nas contas; admin e gestor sem unidade veem a central e podem filtrar (`test_adr025_gestor_so_conta_as_unidades_atribuidas`, `test_adr025_admin_e_gestor_sem_unidade_veem_a_central_e_filtram`).
- **Dado** propostas confirmadas, recusadas e expiradas, **quando** o gestor consulta, **então** as três taxas usam `confirmadas + recusadas + expiradas` como denominador, e a proposta cancelada sem resposta fica à parte (`test_rn021_taxas_de_proposta_usam_as_encerradas_como_denominador`).
- **Dado** uma proposta feita fora do período, **quando** o gestor consulta, **então** ela não conta (`test_rn021_proposta_fora_do_periodo_nao_conta`).
- **Dado** faltas, **quando** o gestor consulta, **então** elas se ancoram no início da vaga e a taxa é `faltas ÷ (realizadas + faltas)` (`test_rn021_faltas_ancoram_na_vaga_e_dividem_pelos_registrados`).
- **Dado** vagas ofertadas, ocupadas (inclusive confirmadas de vaga futura), reaproveitadas e perdidas, **quando** o gestor consulta, **então** as contas seguem RN-021; uma confirmação que a mesma solicitação refez não reaproveita a vaga (`test_rn021_vagas_ofertadas_ocupadas_reaproveitadas_e_perdidas`, `test_rn021_mesma_solicitacao_confirmando_depois_nao_reaproveita`, `test_rn021_confirmada_que_depois_cancelou_nao_reaproveita`).
- **Dado** solicitações com entrada na fila e confirmação, **quando** o gestor consulta, **então** a espera vai da entrada na fila até a primeira confirmação; sem confirmação no período, é `null` (`test_rn021_espera_vai_da_entrada_na_fila_a_primeira_confirmacao`, `test_rn021_espera_sem_confirmacao_e_nula`).
- **Dado** solicitações `NA_FILA`, **quando** o gestor consulta, **então** `fila_atual` conta por cor só as filas do escopo (`test_rf037_fila_atual_por_cor_so_do_escopo`).
- **Dado** um período, **quando** o gestor consulta, **então** a série semanal começa na segunda-feira, traz as semanas sem dado com zeros, e o dia termina à meia-noite de Recife (`test_rf037_serie_semanal_comeca_na_segunda_e_tem_zeros`, `test_rn021_periodo_fecha_a_meia_noite_de_recife`).
- **Dado** uma consulta sem dados, **quando** o gestor consulta, **então** as razões são `null` e as contagens, `0` (`test_rf037_sem_dados_as_razoes_sao_nulas_e_as_contagens_zero`).
- **Dado** uma leitura bem-sucedida, **quando** ela termina, **então** a auditoria guarda só o período e os filtros; uma leitura negada não audita (`test_am007_leitura_e_auditada_so_com_periodo_e_filtros`, `test_rf037_negada_nao_audita`).
- **Dado** a resposta, **quando** ela é inspecionada, **então** não há dado de paciente (`test_adr007_resposta_sem_dado_de_paciente`).
- **Dado** mais dados no banco, **quando** o gestor consulta, **então** o número de consultas não cresce com o volume e o JIT fica desligado (`test_rn021_numero_de_consultas_nao_depende_do_volume`, `test_rn021_consultas_rodam_com_jit_desligado`).
- **Dado** uma consulta que passa do limite de tempo, **quando** o gestor consulta, **então** a resposta é `503` neutro com `Retry-After` (`test_rn021_consulta_que_passa_do_limite_responde_503_neutro`).

## Segurança

- Só GESTOR e ADMIN, com o escopo aplicado dentro da query; recurso fora do escopo responde `404` ([controle de acesso](../../security/access-control.md)).
- A leitura é auditada (AM-007) e a consulta pesada tem timeout e limite (AM-025 no [modelo de ameaças](../../security/threat-model.md)).
