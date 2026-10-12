# UC-004 — Confirmar proposta

| | |
| --- | --- |
| **Ator principal** | Paciente |
| **Objetivo** | Garantir a vaga proposta |
| **Requisitos** | RF-012, RF-018 |
| **Regras** | RN-001, RN-003, RN-010, RN-011 |

## Pré-condições

- Paciente autenticado.
- Existe um agendamento `PROPOSTO`, dentro do prazo, ligado a uma solicitação do próprio paciente.

## Fluxo principal

1. O paciente abre a proposta (pelo aviso, pelo e-mail ou por "Meus atendimentos").
2. O sistema mostra data, hora, unidade, endereço, onde ir, profissional, horário de chegada, o que levar e o prazo de resposta.
3. O paciente escolhe "Confirmar presença".
4. Numa única transação, o sistema trava o agendamento, verifica que ainda está `PROPOSTO` e dentro do prazo, muda para `CONFIRMADO`, grava `respondido_em`, muda a solicitação para `AGENDADA`, registra a auditoria e grava o evento na outbox.
5. O sistema mostra a confirmação com o código do agendamento e a opção de adicionar ao calendário do celular.
6. O Worker envia o e-mail de confirmação.

## Exceções

- **E1 — Proposta expirada:** no passo 4, o prazo já passou. O sistema responde `409`, explica que a vaga foi oferecida a outra pessoa e que o paciente continua na fila.
- **E2 — Proposta já respondida** (por exemplo, confirmada em outra aba): o sistema responde `409` e mostra o estado atual. Confirmar duas vezes não gera dois e-mails.
- **E3 — Proposta de outro paciente:** o sistema responde `404`, sem revelar que o recurso existe.

## Pós-condições

- Agendamento `CONFIRMADO`, solicitação `AGENDADA`, auditoria e aviso registrados.

## Critérios de aceite

- **Dado** uma proposta `PROPOSTO` dentro do prazo, **quando** o dono confirma, **então** o agendamento fica `CONFIRMADO` e a solicitação `AGENDADA`.
- **Dado** uma proposta com `expira_em` no passado, ainda não processada pelo Worker, **quando** o paciente confirma, **então** a resposta é `409` e nada muda. A verificação do prazo é feita na confirmação, sem depender do Worker.
- **Dado** uma proposta de outro paciente, **quando** alguém tenta confirmar pelo ID, **então** a resposta é `404`.
- **Dado** a confirmação concorrendo com a expiração pelo Worker, **quando** ambas acontecem no mesmo instante, **então** só uma delas é aplicada.

## Segurança

- Verificação de dono do recurso em toda rota com ID (AM-001 no [modelo de ameaças](../../security/threat-model.md)).
- Header CSRF obrigatório (AM-002).

Diagrama: [sequência da confirmação](../../architecture/diagrams/sequence-confirmation.md).
