# UC-002 — Solicitar atendimento

| | |
| --- | --- |
| **Ator principal** | Paciente |
| **Objetivo** | Registrar o pedido de atendimento para entrar na fila |
| **Requisitos** | RF-008, RF-018, RF-020 |
| **Regras** | RN-007, RN-009, RN-010, RN-011 |

## Pré-condições

- Paciente autenticado, com consentimento `AGENDAMENTO` vigente.
- Encaminhamento disponível (no protótipo, vindo do `ReguladorGateway` simulado).

## Fluxo principal

1. O paciente abre "Nova solicitação".
2. O sistema mostra o encaminhamento: especialidade, origem e data do pedido. A classificação de risco não é editável pelo paciente.
3. O paciente escolhe o turno preferido (manhã, tarde ou tanto faz), a unidade preferida (opcional) e os canais de aviso.
4. O sistema mostra a revisão e uma explicação de como a fila funciona.
5. O paciente confirma.
6. O sistema cria a solicitação com status `EM_ANALISE`, grava a prioridade legal do momento do pedido, registra a auditoria e grava um evento na outbox.
7. O paciente vê a solicitação em "Minhas solicitações" com o status "Em análise" e recebe o aviso de recebimento.

## Fluxos alternativos

- **A1 — Unidade indiferente:** no passo 3, o paciente não escolhe unidade; `unidade_preferida_id` fica nulo. Em qual fila a solicitação aparece depende de **ABERTO-3**.

## Exceções

- **E1 — Sem consentimento vigente:** o sistema bloqueia a solicitação e oferece conceder o consentimento.
- **E2 — Já existe solicitação ativa para a mesma especialidade:** o sistema informa e mostra a solicitação existente *(regra proposta; validar com o grupo)*.

## Pós-condições

- Solicitação `EM_ANALISE`, auditoria registrada, evento na outbox.

## Critérios de aceite

- **Dado** um paciente com consentimento vigente, **quando** confirma a solicitação, **então** ela é criada como `EM_ANALISE`, com a prioridade legal gravada.
- **Dado** um paciente sem consentimento `AGENDAMENTO` vigente, **quando** tenta solicitar, **então** a resposta é `403` e nada é criado.
- **Dado** uma solicitação criada, **quando** o paciente consulta suas solicitações, **então** a resposta traz o status e não traz posição nem tamanho da fila.

## Segurança

- A classificação de risco e a prioridade legal nunca vêm do corpo da requisição do paciente (AM-013 no [modelo de ameaças](../../security/threat-model.md)).
