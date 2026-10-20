# UC-005 — Pedir outra data ou cancelar

| | |
| --- | --- |
| **Ator principal** | Paciente |
| **Objetivo** | Recusar a data proposta ou desistir do atendimento, liberando a vaga |
| **Requisitos** | RF-013, RF-014, RF-016, RF-018 |
| **Regras** | RN-004, RN-005, RN-010, RN-011 |

## Pré-condições

- Paciente autenticado.
- Existe um agendamento `PROPOSTO` ou `CONFIRMADO` de uma solicitação do próprio paciente.

## Fluxo principal — pedir outra data

1. Na proposta ou no agendamento confirmado, o paciente escolhe "Pedir outra data".
2. O sistema explica que ele continua na fila e receberá a próxima vaga disponível.
3. Numa única transação, o sistema muda o agendamento para `CANCELADO` (motivo: outra data), devolve a solicitação para `NA_FILA`, registra a auditoria e grava o evento na outbox.
4. A vaga fica livre e volta a ser oferecida ([UC-003](UC-003-propor-vaga.md)).

## Fluxo alternativo — A1: cancelar ("não vou precisar")

1. O paciente escolhe "Não vou precisar".
2. O sistema pede confirmação, explicando que o pedido será encerrado.
3. O paciente confirma.
4. Numa única transação, o sistema muda o agendamento para `CANCELADO` (motivo: desistência), muda a solicitação para `CANCELADA`, registra a auditoria e grava o evento na outbox.
5. A vaga fica livre e volta a ser oferecida.

> O cancelamento da solicitação antes de existir proposta (`EM_ANALISE` e `NA_FILA`, com `motivo_codigo`) já está em [UC-002](UC-002-solicitar-atendimento.md). Este caso de uso cobre o cancelamento com proposta ou agendamento ativo, ainda não implementado (hoje a API responde `409`).

## Exceções

- **E1 — Agendamento já em estado final** (expirado, cancelado, realizado): `409`, mostrando o estado atual.
- **E2 — Recurso de outro paciente:** `404`.
- **E3 — Cancelamento em cima da hora:** se houver prazo mínimo de antecedência para cancelar pelo site, o sistema orienta a ligar para a central *(regra a definir; o protótipo usa 24 horas como exemplo)*.

## Pós-condições

- Agendamento `CANCELADO`; solicitação `NA_FILA` (outra data) ou `CANCELADA` (desistência); vaga livre.

## Critérios de aceite

- **Dado** um agendamento `CONFIRMADO`, **quando** o paciente pede outra data, **então** o agendamento fica `CANCELADO`, a solicitação volta para `NA_FILA` e a vaga fica livre.
- **Dado** uma proposta, **quando** o paciente cancela e confirma a desistência, **então** a solicitação fica `CANCELADA`.
- **Dado** a vaga liberada, **quando** se consulta a ocupação, **então** ela pode receber nova proposta imediatamente, sem atualizar a tabela de vagas.
