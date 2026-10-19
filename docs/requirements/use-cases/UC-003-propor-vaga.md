# UC-003 — Propor vaga

| | |
| --- | --- |
| **Ator principal** | Sistema (Worker) ([ADR-021](../../decisions/ADR-021-matching-automatico.md)); Atendente em fase futura |
| **Objetivo** | Oferecer uma vaga livre ao próximo paciente elegível da fila |
| **Requisitos** | RF-010, RF-011, RF-016, RF-018, RF-031, RF-032 |
| **Regras** | RN-001, RN-002, RN-003, RN-005, RN-008, RN-010, RN-011, RN-012, RN-015, RN-016 |

A proposta é automática e segue a ordem da fila (ADR-021, confirmado pela UPE em 15/10/2026). Os passos da proposta manual pelo atendente ficam marcados como futuros.

## Gatilho

- Uma vaga é criada, desbloqueada ou liberada por cancelamento ou expiração.
- *(Futuro — proposta manual)* O atendente decide propor uma vaga a partir da fila.

## Pré-condições

- Existe pelo menos uma vaga `ATIVA` sem agendamento ativo.
- Existe pelo menos uma solicitação `NA_FILA` na fila da agenda da vaga.

## Fluxo principal

1. *(Automático)* O Worker identifica a vaga livre. *(Futuro — proposta manual)* O atendente abre uma fila do seu escopo e escolhe a vaga.
2. O sistema ordena as solicitações `NA_FILA` da fila da vaga com `ordenar_fila()`: risco, nota e hora de chegada (RN-015).
3. *(Automático)* O sistema escolhe a primeira. *(Futuro — proposta manual)* O atendente escolhe uma solicitação; o sistema mostra a posição dela na ordem calculada.
4. O sistema calcula `expira_em` com `calcular_expira_em()`: o menor entre agora + prazo de confirmação da fila (RN-012) e o horário da vaga menos a antecedência mínima (RN-008).
5. O sistema verifica que sobra pelo menos a janela mínima para o paciente responder (RN-016).
6. Numa única transação, o sistema cria o agendamento `PROPOSTO`, muda a solicitação para `EM_PROPOSTA`, registra o evento `PROPOSTA_ENVIADA` na linha do tempo, a auditoria e o evento na outbox.
7. O Worker processa o evento e avisa o paciente no site e por e-mail.

## Fluxos alternativos

- **A1 — Janela menor que a mínima (RN-016):** no passo 5, `calcular_expira_em()` devolve "não propor", e o sistema não propõe aquela vaga para ninguém da fila. A vaga fica livre e aparece no painel como "vaga sem proposta".
- **A2 — Nenhuma solicitação compatível:** a vaga continua livre.
- **A3 — Preferência de turno:** se a vaga não bate com o turno preferido do paciente, o sistema passa para a próxima solicitação *(regra proposta; validar com o grupo e a UPE)*.

## Exceções

- **E1 — Vaga ocupada por outra transação ao mesmo tempo:** o índice único rejeita a inserção. O sistema descarta a tentativa (automático) ou, na proposta manual futura, responde `409` e nada é gravado.
- **E2 — Solicitação já tem agendamento ativo:** o índice único de RN-002 rejeita a inserção, com o mesmo tratamento de E1.

## Pós-condições

- Agendamento `PROPOSTO` com `expira_em`, solicitação `EM_PROPOSTA`, auditoria e evento de aviso gravados.

## Critérios de aceite

- **Dado** uma vaga livre e duas solicitações na fila da vaga, **quando** a vaga é proposta, **então** vai para a primeira na ordem risco → nota → hora de chegada.
- **Dado** duas solicitações com o mesmo risco e a mesma nota, **quando** a vaga é proposta, **então** vai para a que chegou antes à fila.
- **Dado** duas propostas simultâneas para a mesma vaga, **quando** ambas tentam gravar, **então** exatamente uma é criada (teste de concorrência).
- **Dado** uma vaga para a qual o prazo calculado deixa menos de `PROPOSTA_JANELA_MINIMA_HORAS` para o paciente responder, **quando** se tenta propor, **então** nenhuma proposta é criada e a vaga aparece como "vaga sem proposta".
- **Dado** uma vaga distante, **quando** é proposta, **então** `expira_em` = agora + `prazo_confirmacao_horas` da fila (padrão 48 horas).
- **Dado** uma proposta criada, **quando** o Worker processa a outbox, **então** o paciente tem um aviso no site e um e-mail na fila de envio.

## Segurança

- *(Futuro — proposta manual)* Só Atendente, nas filas do seu escopo (`escopo_da_equipe()`, [ADR-025](../../decisions/ADR-025-escopo-por-fila.md), [controle de acesso](../../security/access-control.md)).
- A posição na fila e o motivo da última mudança de posição são mostrados à equipe, nunca ao paciente (RN-007).

Diagrama: [atividades da fila](../../architecture/diagrams/activity-queue.md).
