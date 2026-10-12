# UC-003 — Propor vaga

| | |
| --- | --- |
| **Ator principal** | Sistema (matching automático) ou Atendente (proposta manual) — **ABERTO-1** |
| **Objetivo** | Oferecer uma vaga livre ao próximo paciente elegível da fila |
| **Requisitos** | RF-010, RF-011, RF-016, RF-018 |
| **Regras** | RN-001, RN-002, RN-003, RN-005, RN-006, RN-008, RN-010, RN-011 |

Este caso de uso está escrito para funcionar nas duas respostas de ABERTO-1. Os passos que mudam estão marcados.

## Gatilho

- Uma vaga é criada, desbloqueada ou liberada por cancelamento ou expiração.
- *(Manual)* O atendente decide propor uma vaga a partir da fila.

## Pré-condições

- Existe pelo menos uma vaga `ATIVA` sem agendamento ativo.
- Existe pelo menos uma solicitação `NA_FILA` compatível com a especialidade e a unidade da vaga.

## Fluxo principal

1. *(Automático)* O Worker identifica a vaga livre. *(Manual)* O atendente abre a fila da especialidade e escolhe a vaga.
2. O sistema ordena as solicitações compatíveis pelas regras de prioridade ativas.
3. *(Automático)* O sistema escolhe a primeira. *(Manual)* O atendente escolhe uma solicitação; o sistema mostra a posição dela na ordem calculada.
4. O sistema calcula `expira_em` = agora + prazo de resposta da especialidade naquela unidade.
5. O sistema verifica que `expira_em` não ultrapassa o horário da vaga menos a antecedência mínima.
6. Numa única transação, o sistema cria o agendamento `PROPOSTO`, muda a solicitação para `EM_PROPOSTA`, registra a auditoria e grava o evento na outbox.
7. O Worker processa o evento e avisa o paciente no site e por e-mail.

## Fluxos alternativos

- **A1 — Prazo não cabe antes da vaga (RN-008):** no passo 5, o sistema não propõe aquela vaga para ninguém da fila. A vaga continua livre, e o caso é registrado para o painel.
- **A2 — Nenhuma solicitação compatível:** a vaga continua livre.
- **A3 — Preferência de turno:** se a vaga não bate com o turno preferido do paciente, o sistema passa para a próxima solicitação *(regra proposta; validar com o grupo e a UPE)*.

## Exceções

- **E1 — Vaga ocupada por outra transação ao mesmo tempo:** o índice único rejeita a inserção. O sistema descarta a tentativa (automático) ou responde `409` (manual) e nada é gravado.
- **E2 — Solicitação já tem agendamento ativo:** o índice único de RN-002 rejeita a inserção, com o mesmo tratamento de E1.

## Pós-condições

- Agendamento `PROPOSTO` com `expira_em`, solicitação `EM_PROPOSTA`, auditoria e evento de aviso gravados.

## Critérios de aceite

- **Dado** uma vaga livre e duas solicitações compatíveis, **quando** a vaga é proposta, **então** vai para a de maior prioridade segundo as regras ativas.
- **Dado** duas propostas simultâneas para a mesma vaga, **quando** ambas tentam gravar, **então** exatamente uma é criada (teste de concorrência).
- **Dado** uma vaga cujo horário é menor que agora + prazo de resposta + antecedência mínima, **quando** se tenta propor, **então** nenhuma proposta é criada.
- **Dado** uma proposta criada, **quando** o Worker processa a outbox, **então** o paciente tem um aviso no site e um e-mail na fila de envio.

## Segurança

- *(Manual)* Só Atendente, e dentro do escopo de unidade de **ABERTO-3** ([controle de acesso](../../security/access-control.md)).
- A posição na fila é mostrada ao atendente, nunca ao paciente (RN-007).

Diagrama: [atividades da fila](../../architecture/diagrams/activity-queue.md).
