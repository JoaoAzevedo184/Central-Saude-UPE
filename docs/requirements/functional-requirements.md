# Requisitos funcionais

**Prioridade:** **M** = obrigatório no MVP · **D** = desejável no MVP · **F** = fase futura.

| ID | Requisito | Ator | Prior. | Casos de uso | Regras |
| --- | --- | --- | --- | --- | --- |
| RF-001 | Paciente cria conta com CPF, cartão do SUS e consentimento LGPD obrigatório | Paciente | M | UC-001 | RN-009 |
| RF-002 | Usuário entra e sai do sistema; a sessão é renovada sem novo login enquanto válida | Todos | M | UC-001 | — |
| RF-003 | O sistema restringe cada ação ao papel do usuário (Paciente, Atendente, Gestor, Admin) | Todos | M | todos | ver [controle de acesso](../security/access-control.md) |
| RF-004 | Paciente consulta e revoga seus consentimentos | Paciente | M | — | RN-009 |
| RF-005 | Admin cadastra unidades, especialidades e filas (descrição para o paciente, elegibilidade, prazo de confirmação e tolerância de atraso) | Admin | M | UC-010 | RN-012, RN-013, RN-017 |
| RF-006 | Admin cadastra agendas (profissional, dias, horário, duração, vigência) e o sistema gera as vagas | Admin | M | UC-010 | — |
| RF-007 | Admin bloqueia e desbloqueia vagas | Admin | M | UC-010 | RN-001 |
| RF-008 | Paciente registra uma solicitação numa fila para a qual é elegível, com preferência de turno e canal de aviso, e responde os critérios do protocolo que cabem a ele | Paciente | M | UC-002 | RN-006, RN-009, RN-017 |
| RF-009 | Atendente valida a solicitação, que passa a aguardar vaga | Atendente | M | UC-007 | — |
| RF-010 | Atendente e gestor veem as filas do seu escopo, ordenadas por risco, nota e hora de chegada | Atendente, Gestor | M | UC-003 | RN-006, RN-015 |
| RF-011 | O sistema ou o atendente propõe uma vaga ao paciente, com prazo de resposta | Sistema ([ADR-021](../decisions/ADR-021-matching-automatico.md)); proposta manual pelo atendente em fase futura | M | UC-003 | RN-001, RN-002, RN-003, RN-008 |
| RF-012 | Paciente confirma uma proposta | Paciente | M | UC-004 | RN-001, RN-003 |
| RF-013 | Paciente pede outra data e continua na fila | Paciente | M | UC-005 | RN-004 |
| RF-014 | Paciente cancela ("não vou precisar") | Paciente | M | UC-005 | RN-004 |
| RF-015 | O sistema expira propostas não respondidas no prazo e devolve a solicitação ao fim da fila | Sistema | M | UC-006 | RN-003, RN-014 |
| RF-016 | Vaga liberada por cancelamento ou expiração volta a ser oferecida ao próximo da fila | Sistema ou Atendente | M | UC-003 | RN-005 |
| RF-017 | Atendente registra comparecimento ou falta; a falta só depois da tolerância e devolve a solicitação ao fim da fila | Atendente | M | UC-008 | RN-013, RN-014 |
| RF-018 | O sistema avisa o paciente no site e por e-mail quando a solicitação ou o agendamento mudam | Sistema | M | UC-003 a UC-006 | RN-011 |
| RF-019 | Paciente consulta seus avisos e os marca como lidos | Paciente | M | — | — |
| RF-020 | Paciente acompanha o status das solicitações e dos agendamentos, sem posição na fila | Paciente | M | — | RN-007 |
| RF-021 | Gestor consulta indicadores: confirmação, faltas, tempo até confirmação, vagas reaproveitadas, fila por especialidade | Gestor | M | UC-009 | — |
| RF-022 | Admin configura o protocolo de cada fila: critérios, tipos, pesos e faixas, marcados como simulados | Admin | M | UC-010 | RN-006 |
| RF-023 | Admin consulta a trilha de auditoria de uma solicitação ou agendamento | Admin | M | — | RN-010 |
| RF-024 | O sistema envia lembrete antes do atendimento confirmado | Sistema | D | — | RN-009 |
| RF-025 | Paciente ouve em voz alta os detalhes do agendamento | Paciente | D | — | — |
| RF-026 | Avisos por Telegram | Sistema | F | — | — |
| RF-027 | App mobile com notificações push | Paciente | F | — | — |
| RF-028 | Paciente vê a descrição de cada fila (para que serve e quem pode entrar) antes de pedir | Paciente | M | UC-002 | RN-017 |
| RF-029 | Paciente acompanha a linha do tempo da solicitação, com o motivo de cada mudança e sem posição na fila | Paciente | M | UC-002, UC-006, UC-008 | RN-007, RN-014 |
| RF-030 | Paciente consulta o histórico de atendimentos (realizados, faltas, propostas expiradas e canceladas) | Paciente | M | — | RN-007 |
| RF-031 | A equipe vê a posição de cada solicitação na fila e o motivo da última mudança de posição; o paciente não vê | Atendente, Gestor | M | UC-003 | RN-007, RN-015 |
| RF-032 | O painel da equipe ordena as solicitações por criticidade (risco e nota) e, no empate, por hora de chegada | Atendente, Gestor | M | UC-003 | RN-015 |
| RF-033 | Admin suspende e reativa o acesso de um profissional, com data e motivo; o usuário suspenso não entra e a auditoria continua apontando para ele | Admin | M | UC-010 | — ([ADR-028](../decisions/ADR-028-suspensao-de-acesso.md)) |
| RF-034 | O cadastro do paciente registra sexo e município, usados só para elegibilidade e direcionamento | Paciente | M | UC-001 | RN-017 |
| RF-035 | Admin atribui filas a atendentes e unidades a gestores; o sistema valida que só ATENDENTE recebe fila e só GESTOR recebe unidade | Admin | M | UC-010 | — ([ADR-025](../decisions/ADR-025-escopo-por-fila.md)) |
