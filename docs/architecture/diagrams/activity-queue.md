# Atividades — da solicitação ao atendimento

Percurso completo de uma solicitação pela fila, com as decisões e os caminhos alternativos. Os losangos marcados com RN ou ADR seguem as [regras de negócio](../../requirements/business-rules.md) e as decisões da UPE de 15/10/2026.

```mermaid
flowchart TD
  inicio([Paciente escolhe a fila]) --> eleg{Elegível para a fila?<br/>RN-017}
  eleg -- não --> recusa[Recusa e explica o motivo] --> fim0
  eleg -- sim --> consent{Consentimento<br/>vigente?}
  consent -- não --> bloqueia[Bloqueia e oferece<br/>conceder consentimento] --> fim0([Fim])
  consent -- sim --> analise[Solicitação EM_ANALISE]
  analise --> valida{Atendente valida<br/>o encaminhamento?}
  valida -- não --> cancelada([CANCELADA])
  valida -- sim --> fila[NA_FILA<br/>com risco classificado]

  fila --> vaga{Há vaga livre<br/>compatível?}
  vaga -- não --> espera[Aguarda vaga<br/>criada ou liberada] --> vaga
  vaga -- sim --> ordena[Ordena a fila: risco,<br/>nota, hora de chegada<br/>RN-015]
  ordena --> escolheA[Sistema propõe ao<br/>primeiro da fila<br/>ADR-021]
  escolheA --> prazo
  prazo{Sobra a janela mínima<br/>para responder?<br/>RN-008, RN-016}
  prazo -- não --> semprop[Vaga fica livre<br/>painel: vaga sem proposta] --> fila
  prazo -- sim --> proposta[Agendamento PROPOSTO<br/>solicitação EM_PROPOSTA<br/>aviso ao paciente]

  proposta --> resposta{Resposta do paciente}
  resposta -- confirma --> confirmado[CONFIRMADO<br/>solicitação AGENDADA]
  resposta -- pede outra data --> libera1[Agendamento CANCELADO<br/>vaga liberada] --> fila
  resposta -- não vou precisar --> libera2[Agendamento CANCELADO<br/>vaga liberada] --> cancelada
  resposta -- prazo vence --> expira[EXPIRADO pelo Worker<br/>vaga liberada] --> fimfila[Volta ao fim da fila<br/>com o motivo<br/>RN-014]
  fimfila --> fila

  confirmado --> dia{No dia do atendimento}
  dia -- comparece --> atendida([REALIZADO<br/>solicitação ATENDIDA])
  dia -- não chegou --> tol{Passou a tolerância?<br/>RN-013}
  tol -- não --> dia
  tol -- sim --> faltou[FALTOU] --> fimfila
  confirmado -- cancela antes --> libera2
```

Toda vaga liberada (cancelamento ou expiração) volta ao losango "Há vaga livre compatível?" para o próximo paciente (RN-005).
