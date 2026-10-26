# Diagrama de casos de uso

O Mermaid não tem um tipo nativo de diagrama de casos de uso; este é um equivalente em fluxograma, com os atores à esquerda e à direita e os casos de uso no centro. Detalhes de cada caso em [casos de uso](../../requirements/use-cases/README.md).

```mermaid
flowchart LR
  pac["👤 Paciente"]
  sis["⚙️ Sistema (Worker)"]
  ate["👤 Atendente"]
  ges["👤 Gestor"]
  adm["👤 Administrador"]

  subgraph central["Central de Teleagendamento"]
    uc1(["UC-001 Cadastrar paciente"])
    uc2(["UC-002 Solicitar atendimento"])
    uc4(["UC-004 Confirmar proposta"])
    uc5(["UC-005 Pedir outra data ou cancelar"])
    uc3(["UC-003 Propor vaga"])
    uc6(["UC-006 Expirar proposta"])
    uc7(["UC-007 Validar solicitação"])
    uc8(["UC-008 Registrar comparecimento ou falta"])
    uc9(["UC-009 Acompanhar indicadores"])
    uc10(["UC-010 Administrar equipe, unidades, agendas e vagas"])
  end

  pac --- uc1
  pac --- uc2
  pac --- uc4
  pac --- uc5
  uc3 --- sis
  uc6 --- sis
  uc3 --- ate
  uc7 --- ate
  uc8 --- ate
  uc9 --- ges
  uc9 --- adm
  uc10 --- adm

  uc5 -. "libera vaga para" .-> uc3
  uc6 -. "libera vaga para" .-> uc3
```

UC-003 aparece ligado ao Sistema e ao Atendente. No MVP, quem propõe é o Sistema ([ADR-021](../../decisions/ADR-021-matching-automatico.md), provisório); a ligação com o Atendente é a proposta manual, de fase futura.
