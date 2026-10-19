# UC-002 — Solicitar atendimento

| | |
| --- | --- |
| **Ator principal** | Paciente |
| **Objetivo** | Registrar o pedido de atendimento numa fila para a qual o paciente é elegível |
| **Requisitos** | RF-008, RF-018, RF-020, RF-028, RF-029 |
| **Regras** | RN-006, RN-007, RN-009, RN-010, RN-011, RN-017 |

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
- **E2 — Já existe solicitação ativa na mesma fila:** o sistema informa e mostra a solicitação existente *(regra proposta; validar com o grupo)*.
- **E3 — Paciente inelegível para a fila escolhida** (por exemplo, sexo ou idade fora da regra, ou cadastro sem esses dados): a resposta é `409` com o motivo, e nada é criado.

## Pós-condições

- Solicitação `EM_ANALISE` na fila escolhida, respostas e nota gravadas, linha do tempo, auditoria e evento na outbox.
- A solicitação entra na ordenação só em `NA_FILA`, depois de validada e classificada pela equipe (UC-007).

## Critérios de aceite

- **Dado** um paciente elegível com consentimento vigente, **quando** confirma a solicitação, **então** ela é criada como `EM_ANALISE` na fila escolhida, com a nota igual à soma dos pontos das respostas.
- **Dado** um paciente sem consentimento `AGENDAMENTO` vigente, **quando** tenta solicitar, **então** a resposta é `403` e nada é criado.
- **Dado** um paciente do sexo masculino, **quando** tenta entrar na fila de laqueadura, **então** a resposta é `409` e nada é criado.
- **Dado** um paciente sem data de nascimento, **quando** tenta entrar numa fila com idade mínima, **então** a resposta é `409` (falha fechada).
- **Dado** uma resposta a critério de outra fila, **quando** o sistema tenta gravá-la, **então** o banco recusa.
- **Dado** uma solicitação criada, **quando** o paciente consulta suas solicitações, **então** a resposta traz o status e a linha do tempo, e não traz posição nem tamanho da fila.

## Segurança

- A classificação de risco, a nota e os pontos nunca vêm do corpo da requisição do paciente. O paciente envia só as respostas dos critérios com origem `PACIENTE`; o servidor calcula os pontos (AM-013 no [modelo de ameaças](../../security/threat-model.md)).
- A elegibilidade é verificada no servidor, não só na tela.
