# Sequência — confirmar proposta

Cenário de [UC-004](../../requirements/use-cases/UC-004-confirmar-proposta.md), incluindo a corrida com a expiração.

```mermaid
sequenceDiagram
  autonumber
  actor P as Paciente
  participant F as Frontend
  participant N as Nginx
  participant A as API
  participant D as PostgreSQL
  participant W as Worker
  participant S as SMTP

  P->>F: Confirmar presença
  F->>N: POST /api/v1/agendamentos/{id}/confirmar<br/>cookie + X-CSRF-Token
  N->>A: proxy
  A->>A: valida sessão e header CSRF
  A->>D: BEGIN
  A->>D: SELECT agendamento + solicitação FOR UPDATE
  alt não é do paciente
    A-->>F: 404
  else status ≠ PROPOSTO ou expira_em < agora
    A->>D: ROLLBACK
    A-->>F: 409 (expirada ou já respondida)
  else proposta válida
    A->>D: UPDATE agendamento → CONFIRMADO, respondido_em
    A->>D: UPDATE solicitação → AGENDADA
    A->>D: INSERT auditoria
    A->>D: INSERT outbox (AGENDAMENTO_CONFIRMADO)
    A->>D: COMMIT
    A-->>F: 200 + agendamento
    F-->>P: tela "Presença confirmada"
  end

  Note over W,D: execução seguinte do Worker
  W->>D: SELECT outbox PENDENTE FOR UPDATE SKIP LOCKED
  W->>D: INSERT notificação (IN_APP, EMAIL)
  W->>S: envia e-mail de confirmação
  W->>D: UPDATE outbox → PROCESSADO
```

**Corrida com a expiração:** se o job de expiração pegar o lock primeiro, ele muda o agendamento para `EXPIRADO`. Quando a API obtém o lock, vê o estado diferente de `PROPOSTO` e responde `409`. Se a API vencer, o Worker encontra `CONFIRMADO` e não faz nada.
