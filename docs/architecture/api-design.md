# API

> **Rascunho.** Os endpoints abaixo são a proposta inicial e vão mudar durante a implementação. A referência definitiva será a documentação OpenAPI gerada pelo FastAPI em `/api/v1/docs`.

## Convenções (propostas)

- **Base:** `/api/v1`. Uma versão nova de URL só para mudanças incompatíveis.
- **Formato:** JSON com campos em `snake_case`. Datas em ISO 8601 com fuso (`2026-10-08T08:30:00-03:00`).
- **Autenticação:** cookie `httpOnly` com o refresh token; requisições que alteram estado (`POST`, `PUT`, `PATCH`, `DELETE`) enviam o header `X-CSRF-Token`. O mobile, quando existir, usa `Authorization: Bearer` ([ADR-003](../decisions/ADR-003-autenticacao-web.md)).
- **Erros:** formato *Problem Details* (RFC 9457), `application/problem+json`, com `type`, `title`, `status` e `detail`. O `type` é um caminho relativo estável; o frontend decide o tratamento pelo `type`, nunca pelo texto. Valores em uso:

  | `type` | Status | Quando aparece |
  | --- | --- | --- |
  | `about:blank` | conforme o erro (`404`, `405`, `422`, `500`, `503`…) | Erros HTTP genéricos: rota inexistente, método não permitido, validação da entrada (com a lista `errors`), erro inesperado, banco indisponível no `/health` |
  | `/problemas/transicao-invalida` | `409` | O estado de origem não permite a transição pedida (ex.: proposta já respondida) |
  | `/problemas/erro-de-dominio` | `409` | Outra regra de negócio violada, sem `type` mais específico |
- **Códigos de status mais usados:**
  - `401`: sem sessão
  - `403`: sem permissão para o papel ou o escopo
  - `404`: recurso inexistente ou de outro paciente (nunca revelar que existe)
  - `409`: conflito de estado, como vaga já ocupada ou proposta já respondida
  - `422`: validação
- **Ações de estado** são sub-recursos com `POST` (`/agendamentos/{id}/confirmar`), não `PATCH` no campo `status`. Assim cada transição tem validação, autorização e auditoria próprias.
- **Paginação** de listas: `?limite=&cursor=`.
- **Escopo da equipe por fila** ([ADR-025](../decisions/ADR-025-escopo-por-fila.md)): toda rota da equipe recebe `escopo = Depends(escopo_da_equipe)`, um conjunto de `fila_id`, e filtra por `fila_id IN escopo` **dentro da query**. Recurso de fila fora do escopo responde `404`, como recurso de outro paciente. Usuário suspenso não tem sessão ([ADR-028](../decisions/ADR-028-suspensao-de-acesso.md)).
- **O que o paciente vê** ([ADR-007](../decisions/ADR-007-paciente-ve-status.md)):
  - status da solicitação, a fila (nome e descrição) e a linha do tempo, com só os eventos de `historico_solicitacao` em que `visivel_paciente = true` (tipo, data e motivo);
  - **nunca** posição na fila, tamanho da fila, nota, pontos dos critérios, classificação de risco ou estimativa derivada deles;
  - os schemas de entrada do paciente aceitam só as respostas dos critérios com origem `PACIENTE`; os pontos e a nota são calculados no servidor.
- **O que a equipe vê:** além do que o paciente vê, a posição calculada na consulta (`ordenar_fila()`), o risco, a nota, as respostas e o motivo da última mudança de posição.

## Endpoints

### Sessão e conta
| Método | Rota | Quem | Descrição |
| --- | --- | --- | --- |
| POST | `/auth/registro` | público | Cria conta de paciente com consentimento obrigatório |
| POST | `/auth/login` | público | CPF (paciente) ou e-mail (equipe) e senha |
| POST | `/auth/refresh` | sessão | Renova o access token |
| POST | `/auth/logout` | sessão | Encerra a sessão |
| GET | `/me` | sessão | Dados do usuário logado e papel |

### Paciente
| Método | Rota | Descrição |
| --- | --- | --- |
| GET | `/pacientes/me/consentimentos` | Consentimentos vigentes e histórico |
| POST | `/pacientes/me/consentimentos` | Concede um consentimento (finalidade, versão do termo) |
| POST | `/pacientes/me/consentimentos/{id}/revogar` | Revoga um consentimento |
| GET | `/filas/disponiveis?especialidade_id=` | Filas para as quais o paciente é elegível, com a descrição para o paciente (RN-017) |
| GET | `/pacientes/me/solicitacoes` | Solicitações com status, **sem posição na fila** (RN-007) |
| GET | `/solicitacoes/{id}/linha-do-tempo` | Eventos visíveis ao paciente, com motivo; sem posição |
| GET | `/pacientes/me/historico` | Histórico de atendimentos: realizados, faltas, propostas expiradas e canceladas |
| POST | `/solicitacoes` | Nova solicitação numa fila, com as respostas dos critérios de origem `PACIENTE` |
| POST | `/solicitacoes/{id}/cancelar` | "Não vou precisar" |
| GET | `/pacientes/me/agendamentos` | Propostas, próximos e anteriores |
| GET | `/agendamentos/{id}` | Detalhe da proposta ou do agendamento |
| POST | `/agendamentos/{id}/confirmar` | Confirma presença |
| POST | `/agendamentos/{id}/pedir-outra-data` | Cancela este agendamento e mantém a solicitação na fila |
| POST | `/agendamentos/{id}/cancelar` | Cancela o agendamento |
| GET | `/notificacoes` | Avisos do usuário |
| POST | `/notificacoes/{id}/marcar-lida` | Marca como lido |

### Equipe (atendente e gestor)
| Método | Rota | Descrição |
| --- | --- | --- |
| GET | `/filas` | Filas do escopo do usuário |
| GET | `/filas/{id}/solicitacoes` | Fila ordenada por risco, nota e hora de chegada, com posição e motivo da última mudança (só filas do escopo) |
| POST | `/solicitacoes/{id}/validar` | `EM_ANALISE` → `NA_FILA`, com a classificação de risco |
| POST | `/agendamentos` | Propõe uma vaga para uma solicitação — fase futura (proposta manual, [ADR-021](../decisions/ADR-021-matching-automatico.md)) |
| POST | `/agendamentos/{id}/registrar-comparecimento` | `CONFIRMADO` → `REALIZADO` |
| POST | `/agendamentos/{id}/registrar-falta` | `CONFIRMADO` → `FALTOU`, só depois da tolerância; a solicitação volta ao fim da fila (RN-013, RN-014) |
| GET | `/indicadores?de=&ate=&unidade_id=` | Confirmação, faltas, tempo até confirmação, vagas reaproveitadas, tamanho de cada fila (gestor: unidades do escopo) |

### Administração
| Método | Rota | Descrição |
| --- | --- | --- |
| GET, POST, PATCH | `/unidades` | Unidades |
| GET, POST, PATCH | `/especialidades` | Especialidades |
| GET, POST, PATCH | `/filas` | Filas: descrição para o paciente, elegibilidade, prazo de confirmação e tolerância |
| GET, POST, PATCH | `/filas/{id}/criterios` | Protocolo da fila: critérios, tipos, pesos e parâmetros |
| GET, POST, PATCH | `/agendas` | Agendas; criar uma agenda gera as vagas da vigência |
| POST | `/vagas/{id}/bloquear` e `/vagas/{id}/desbloquear` | Estado administrativo da vaga |
| GET, POST | `/usuarios` | Contas da equipe |
| POST | `/usuarios/{id}/suspender` e `/usuarios/{id}/reativar` | Suspensão de acesso, com motivo ([ADR-028](../decisions/ADR-028-suspensao-de-acesso.md)) |
| PUT | `/usuarios/{id}/filas` e `/usuarios/{id}/unidades` | Atribuições de escopo; filas só para ATENDENTE e unidades só para GESTOR |
| GET | `/auditoria?entidade=&entidade_id=` | Trilha de auditoria |

### Operação
| Método | Rota | Descrição |
| --- | --- | --- |
| GET | `/health` | Verificação de saúde para o Nginx e o monitoramento |
