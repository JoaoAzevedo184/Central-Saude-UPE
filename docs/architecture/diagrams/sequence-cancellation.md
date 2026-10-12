# Sequência — pedir outra data e liberar a vaga

Cenário de [UC-005](../../requirements/use-cases/UC-005-pedir-outra-data-ou-cancelar.md). O trecho final depende de **ABERTO-1**; aqui está a variante automática.

```mermaid
sequenceDiagram
  autonumber
  actor P as Paciente
  participant A as API
  participant D as PostgreSQL
  participant W as Worker
  actor P2 as Próximo paciente

  P->>A: POST /agendamentos/{id}/pedir-outra-data
  A->>D: BEGIN · SELECT ... FOR UPDATE
  A->>D: UPDATE agendamento → CANCELADO (motivo: outra data)
  A->>D: UPDATE solicitação → NA_FILA
  A->>D: INSERT auditoria
  A->>D: INSERT outbox (AGENDAMENTO_CANCELADO)
  A->>D: COMMIT
  A-->>P: 200 · "você continua na fila"
  Note over D: a vaga fica livre sem atualizar a tabela vaga<br/>(nenhum agendamento ativo aponta para ela)

  W->>D: SELECT outbox PENDENTE FOR UPDATE SKIP LOCKED
  W->>D: avisa P do cancelamento
  W->>D: busca a próxima solicitação compatível (regras de prioridade)
  W->>D: INSERT agendamento PROPOSTO para P2 + outbox
  alt outra transação ocupou a vaga antes
    D-->>W: violação do índice único
    W->>W: descarta a tentativa
  end
  W->>P2: aviso de nova vaga (site e e-mail)
```

Na variante manual, os passos de matching saem do Worker: a vaga aparece como livre na fila do atendente, que faz a proposta pela API ([UC-003](../../requirements/use-cases/UC-003-propor-vaga.md)).
