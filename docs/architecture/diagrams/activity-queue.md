# Atividades — da solicitação ao atendimento

Percurso completo de uma solicitação pela fila, com as decisões e os caminhos alternativos. Os losangos marcados com ABERTO dependem de [questões em aberto](../../requirements/open-questions.md); o marcado com ADR segue uma decisão provisória.

```mermaid
flowchart TD
  inicio([Paciente envia a solicitação]) --> consent{Consentimento<br/>vigente?}
  consent -- não --> bloqueia[Bloqueia e oferece<br/>conceder consentimento] --> fim0([Fim])
  consent -- sim --> analise[Solicitação EM_ANALISE]
  analise --> valida{Atendente valida<br/>o encaminhamento?}
  valida -- não --> cancelada([CANCELADA])
  valida -- sim --> fila[NA_FILA]

  fila --> vaga{Há vaga livre<br/>compatível?}
  vaga -- não --> espera[Aguarda vaga<br/>criada ou liberada] --> vaga
  vaga -- sim --> ordena[Ordena a fila pelas<br/>regras de prioridade]
  ordena --> quem{Quem propõe?<br/>ADR-021}
  quem -->|"automático (MVP)"| escolheA[Sistema escolhe<br/>o primeiro elegível]
  quem -.->|"manual (futuro)"| escolheM[Atendente escolhe]
  escolheA --> prazo
  escolheM --> prazo
  prazo{Prazo de resposta cabe<br/>antes da vaga? RN-008}
  prazo -- não --> semprop[Vaga fica livre<br/>painel: vaga sem proposta] --> fila
  prazo -- sim --> proposta[Agendamento PROPOSTO<br/>solicitação EM_PROPOSTA<br/>aviso ao paciente]

  proposta --> resposta{Resposta do paciente}
  resposta -- confirma --> confirmado[CONFIRMADO<br/>solicitação AGENDADA]
  resposta -- pede outra data --> libera1[Agendamento CANCELADO<br/>vaga liberada] --> fila
  resposta -- não vou precisar --> libera2[Agendamento CANCELADO<br/>vaga liberada] --> cancelada
  resposta -- prazo vence --> expira[EXPIRADO pelo Worker<br/>vaga liberada] --> fila

  confirmado --> dia{No dia do atendimento}
  dia -- comparece --> atendida([REALIZADO<br/>solicitação ATENDIDA])
  dia -- falta --> falta{ABERTO-4<br/>efeito da falta}
  falta -- volta à fila --> fila
  falta -- encerra --> cancelada
  confirmado -- cancela antes --> libera1
```

Toda vaga liberada (cancelamento ou expiração) volta ao losango "Há vaga livre compatível?" para o próximo paciente (RN-005).
