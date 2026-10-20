# UC-002 — Solicitar atendimento

| | |
| --- | --- |
| **Ator principal** | Paciente |
| **Objetivo** | Registrar o pedido de atendimento numa fila para a qual o paciente é elegível |
| **Requisitos** | RF-008, RF-018, RF-020, RF-028, RF-029 |
| **Regras** | RN-006, RN-007, RN-009, RN-010, RN-011, RN-017, RN-018 |

## Pré-condições

- Paciente autenticado, com consentimento `AGENDAMENTO` vigente.
- Encaminhamento disponível (no protótipo, vindo do `ReguladorGateway` simulado).

## Fluxo principal

1. O paciente abre "Nova solicitação".
2. O sistema mostra o encaminhamento (especialidade, origem e data do pedido) e as filas daquela especialidade para as quais o paciente é elegível (RN-017), cada uma com a sua descrição para o paciente. A classificação de risco não é editável pelo paciente.
3. O paciente escolhe a fila, o turno preferido (manhã, tarde ou tanto faz) e os canais de aviso.
4. O sistema mostra as perguntas do protocolo da fila com origem `PACIENTE` (por exemplo, "Sua mãe ou irmã teve câncer de mama?") e o paciente responde.
5. O sistema mostra a revisão e uma explicação de como a fila funciona: risco, critérios da fila e hora de chegada, sem posição.
6. O paciente confirma.
7. Numa única transação, o sistema:
   - confere de novo a elegibilidade no servidor;
   - cria a solicitação com status `EM_ANALISE`;
   - grava as respostas com os pontos e a nota (RN-006);
   - registra o evento `CRIADA` na linha do tempo, a auditoria e o evento na outbox.
8. O paciente vê a solicitação em "Minhas solicitações" com o status "Em análise" e recebe o aviso de recebimento.

## Exceções

- **E1 — Sem consentimento vigente:** o sistema bloqueia a solicitação e oferece conceder o consentimento.
- **E2 — Já existe solicitação ativa na mesma fila (RN-018):** a resposta é `409` (`/problemas/solicitacao-duplicada`) com o `solicitacao_id` da existente, e nada é criado.
- **E3 — Paciente inelegível para a fila escolhida** (por exemplo, sexo ou idade fora da regra, ou cadastro sem esses dados): a resposta é `409` (`/problemas/nao-elegivel`) com o motivo, e nada é criado.
- **E4 — Resposta inválida** (critério de outra fila ou de outra origem, repetido, valor inválido, ou fila inexistente ou inativa): `422`, e nada é criado.

## Fluxo alternativo — A1: cancelar a solicitação

Antes da proposta de vaga, o paciente pode desistir. `POST /solicitacoes/{id}/cancelar` exige `motivo_codigo` de lista fechada (sem texto livre) e só vale em `EM_ANALISE` e `NA_FILA`; em outro estado, `409`. Numa única transação, o sistema muda a solicitação para `CANCELADA`, grava o evento `CANCELADA` (com o rótulo amigável do motivo, visível ao paciente), a auditoria e a outbox `SOLICITACAO_CANCELADA`. O cancelamento com proposta ou agendamento ativo fica no [UC-005](UC-005-pedir-outra-data-ou-cancelar.md).

## Divergências aceitas em relação ao fluxo

- Os "canais de aviso" (passo 3) não estão implementados.
- `origem_encaminhamento` é um texto informado pelo paciente (2 a 200 caracteres), em vez do `ReguladorGateway` simulado.
- O paciente não precisa responder todos os critérios: critério sem resposta vale 0 ponto.
- Sem data de nascimento o domínio responde inelegível, mas isso só é testado no domínio, porque `data_nascimento` é `NOT NULL` desde a migração 0002.

## Pós-condições

- Solicitação `EM_ANALISE` na fila escolhida, respostas e nota gravadas, linha do tempo, auditoria e evento na outbox.
- A solicitação entra na ordenação só em `NA_FILA`, depois de validada e classificada pela equipe (UC-007).

## Critérios de aceite

- **Dado** um paciente elegível com consentimento vigente, **quando** confirma a solicitação, **então** ela é criada como `EM_ANALISE` na fila escolhida, com a nota igual à soma dos pontos das respostas (`test_uc002_cria_solicitacao_em_analise_com_nota`).
- **Dado** um paciente sem consentimento `AGENDAMENTO` vigente, **quando** tenta solicitar, **então** a resposta é `403` e nada é criado (`test_rn009_sem_consentimento_retorna_403_e_nada_e_criado`).
- **Dado** um paciente inelegível por sexo, por idade ou por falta do sexo no cadastro, **quando** tenta entrar na fila, **então** a resposta é `409` e nada é criado (`test_rn017_inelegivel_retorna_409_e_nada_e_criado`).
- **Dado** uma resposta a critério de outra fila ou de outra origem, repetida ou com valor inválido, **quando** o paciente envia, **então** a resposta é `422` e nada é criado (`test_uc002_resposta_invalida_retorna_422_e_nada_e_criado`).
- **Dado** uma solicitação ativa na fila, **quando** o paciente cria outra na mesma fila, **então** a resposta é `409` com o `solicitacao_id` da existente; depois de cancelar a primeira, a nova é permitida (`test_rn018_solicitacao_duplicada_retorna_409_e_apos_cancelar_e_permitida`).
- **Dado** a solicitação do paciente A, **quando** o paciente B tenta ler ou cancelar, **então** a resposta é `404` (`test_am001_paciente_b_nao_le_nem_cancela_solicitacao_de_a`).
- **Dado** uma solicitação criada, **quando** o paciente consulta suas respostas, **então** a resposta não traz pontos, nota, risco nem posição (`test_adr007_respostas_do_paciente_sem_chaves_proibidas`).
- **Dado** uma solicitação com eventos internos, **quando** o paciente vê a linha do tempo, **então** vê só os eventos visíveis (`test_adr007_linha_do_tempo_sem_eventos_internos`), e cada `data` é só o dia no fuso de Recife, sem hora (`test_adr007_linha_do_tempo_so_com_a_data_no_fuso_de_recife`).
- **Dado** uma solicitação `EM_ANALISE` ou `NA_FILA`, **quando** o paciente cancela com `motivo_codigo`, **então** ficam gravados o evento, a auditoria e a outbox (`test_uc002_cancelar_grava_evento_auditoria_e_outbox`).
- **Dado** uma solicitação em outro estado, **quando** o paciente tenta cancelar, **então** a resposta é `409` (`test_uc002_cancelar_fora_de_em_analise_ou_na_fila_retorna_409`).

## Segurança

- A classificação de risco, a nota e os pontos nunca vêm do corpo da requisição do paciente. O paciente envia só as respostas dos critérios com origem `PACIENTE`; o servidor calcula os pontos (AM-013 no [modelo de ameaças](../../security/threat-model.md)).
- A elegibilidade é verificada no servidor, não só na tela.
