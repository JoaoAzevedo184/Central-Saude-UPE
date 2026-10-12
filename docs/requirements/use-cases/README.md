# Casos de uso

## Atores

| Ator | Descrição |
| --- | --- |
| Paciente | Usuário do SUS com conta no sistema |
| Atendente | Profissional que valida solicitações e acompanha a fila |
| Gestor | Acompanha indicadores |
| Administrador | Configura unidades, especialidades, agendas e regras |
| Sistema (Worker) | Executa tarefas automáticas: expirar propostas, enviar avisos |

Visão gráfica: [diagrama de casos de uso](../../architecture/diagrams/use-case.md).

## Índice

| ID | Caso de uso | Ator principal | Situação |
| --- | --- | --- | --- |
| [UC-001](UC-001-cadastrar-paciente.md) | Cadastrar paciente | Paciente | Detalhado |
| [UC-002](UC-002-solicitar-atendimento.md) | Solicitar atendimento | Paciente | Detalhado |
| [UC-003](UC-003-propor-vaga.md) | Propor vaga | Sistema (Worker); Atendente em fase futura | Detalhado; ADR-021 (provisório) |
| [UC-004](UC-004-confirmar-proposta.md) | Confirmar proposta | Paciente | Detalhado |
| [UC-005](UC-005-pedir-outra-data-ou-cancelar.md) | Pedir outra data ou cancelar | Paciente | Detalhado |
| [UC-006](UC-006-expirar-proposta.md) | Expirar proposta | Sistema | Detalhado |
| UC-007 | Validar solicitação | Atendente | A detalhar |
| UC-008 | Registrar comparecimento ou falta | Atendente | A detalhar, depende de **ABERTO-4** |
| UC-009 | Acompanhar indicadores | Gestor | A detalhar |
| UC-010 | Gerenciar unidades, especialidades, agendas e vagas | Administrador | A detalhar |

## Modelo

Cada caso de uso traz: atores, requisitos e regras relacionados, pré-condições, fluxo principal, fluxos alternativos (`A1`, `A2`...), exceções (`E1`, `E2`...), pós-condições, critérios de aceite e cuidados de segurança. Os critérios de aceite ficam no próprio caso de uso, no formato *Dado / Quando / Então*, e viram testes automatizados.
