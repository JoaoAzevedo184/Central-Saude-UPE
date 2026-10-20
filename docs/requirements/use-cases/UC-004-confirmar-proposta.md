# UC-004 — Confirmar proposta

| | |
| --- | --- |
| **Ator principal** | Paciente |
| **Objetivo** | Garantir a vaga proposta |
| **Requisitos** | RF-012, RF-018 |
| **Regras** | RN-001, RN-003, RN-010, RN-011, RN-012 |

## Pré-condições

- Paciente autenticado.
- Existe um agendamento `PROPOSTO`, dentro do prazo (`expira_em`, até 2 dias por padrão, RN-012), ligado a uma solicitação do próprio paciente.

## Fluxo principal

1. O paciente abre a proposta (pelo aviso, pelo e-mail ou por "Meus atendimentos").
2. O sistema mostra data, hora, unidade, endereço, onde ir, profissional, horário de chegada, o que levar e o prazo de resposta.
3. O paciente escolhe "Confirmar presença".
4. Numa única transação, o sistema trava o agendamento, verifica que ainda está `PROPOSTO` e dentro do prazo, muda para `CONFIRMADO`, grava `respondido_em`, muda a solicitação para `AGENDADA`, registra o evento `CONFIRMADA` na linha do tempo, a auditoria e o evento na outbox.
5. O sistema mostra a confirmação com o código do agendamento e a opção de adicionar ao calendário do celular.
6. O Worker envia o e-mail de confirmação.

## Exceções

- **E1 — Proposta expirada:** no passo 4, o prazo já passou. O sistema responde `409` e explica que o prazo para confirmar acabou e que a solicitação volta para o fim da fila (RN-014), sem citar posição.
- **E2 — Proposta já respondida** (por exemplo, confirmada em outra aba): o sistema responde `409` e mostra o estado atual. Confirmar duas vezes não gera dois e-mails.
- **E3 — Proposta de outro paciente:** o sistema responde `404`, sem revelar que o recurso existe.

## Pós-condições

- Agendamento `CONFIRMADO`, solicitação `AGENDADA`, auditoria e aviso registrados.

## Implementação

`POST /api/v1/agendamentos/{id}/confirmar`. O detalhe da solicitação (`GET /api/v1/solicitacoes/{id}`) traz `agendamento_ativo`: id, status, início e fim da vaga no fuso de Recife, profissional, unidade, endereço da unidade e `expira_em` (só na proposta). Prazo vencido responde `409` `/problemas/proposta-expirada`; outro estado, `409` `/problemas/transicao-invalida`. Outbox `AGENDAMENTO_CONFIRMADO`.

## Critérios de aceite

- **Dado** uma proposta `PROPOSTO` dentro do prazo, **quando** o dono confirma, **então** o agendamento fica `CONFIRMADO`, a solicitação `AGENDADA` e a linha do tempo ganha o evento `CONFIRMADA` (`test_uc004_confirmar_dentro_do_prazo`).
- **Dado** uma proposta com `expira_em` no passado, ainda não processada pelo Worker, **quando** o paciente confirma, **então** a resposta é `409` e nada muda. A verificação do prazo é feita na confirmação, sem depender do Worker (`test_uc004_um_segundo_depois_do_prazo_responde_409_sem_o_job`).
- **Dado** uma proposta de outro paciente, **quando** alguém tenta confirmar pelo ID, **então** a resposta é `404` (`test_am001_confirmar_ou_recusar_proposta_de_outro_paciente_responde_404`).
- **Dado** a confirmação concorrendo com a expiração pelo Worker, **quando** ambas acontecem no mesmo instante, **então** só uma delas é aplicada (`test_uc004_uc006_confirmacao_e_expiracao_simultaneas_so_uma_vence`).
- **Dado** uma proposta, **quando** o paciente abre o detalhe, **então** vê data, hora, profissional, unidade, endereço e prazo, sem posição nem tamanho da fila (`test_uc004_detalhe_mostra_a_proposta`).
- **Dado** uma proposta já confirmada, **quando** o paciente confirma de novo, **então** a resposta é `409` (`test_uc004_confirmar_duas_vezes_responde_409`).

## Segurança

- Verificação de dono do recurso em toda rota com ID (AM-001 no [modelo de ameaças](../../security/threat-model.md)).
- Header CSRF obrigatório (AM-002).

Diagrama: [sequência da confirmação](../../architecture/diagrams/sequence-confirmation.md).
