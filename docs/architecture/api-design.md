# API

> **Rascunho.** Os endpoints abaixo são a proposta inicial e vão mudar durante a implementação. A referência definitiva será a documentação OpenAPI gerada pelo FastAPI em `/api/v1/docs`.

## Convenções (propostas)

- **Base:** `/api/v1`. Uma versão nova de URL só para mudanças incompatíveis.
- **Formato:** JSON com campos em `snake_case`. Datas em ISO 8601 com fuso (`2026-10-08T08:30:00-03:00`).
- **Autenticação:** cookie `httpOnly` com o refresh token; requisições que alteram estado (`POST`, `PUT`, `PATCH`, `DELETE`) enviam o header `X-CSRF-Token`. O mobile, quando existir, usa `Authorization: Bearer` ([ADR-003](../decisions/ADR-003-autenticacao-web.md)).
- **Erros:** formato *Problem Details* (RFC 9457), `application/problem+json`, com `type`, `title`, `status` e `detail`.
- **Códigos de status mais usados:**
  - `401`: sem sessão
  - `403`: sem permissão para o papel ou o escopo
  - `404`: recurso inexistente ou de outro paciente (nunca revelar que existe)
  - `409`: conflito de estado, como vaga já ocupada ou proposta já respondida
  - `422`: validação
- **Ações de estado** são sub-recursos com `POST` (`/agendamentos/{id}/confirmar`), não `PATCH` no campo `status`. Assim cada transição tem validação, autorização e auditoria próprias.
- **Paginação** de listas: `?limite=&cursor=`.

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
| GET | `/pacientes/me/solicitacoes` | Solicitações com status, **sem posição na fila** (RN-007) |
| POST | `/solicitacoes` | Nova solicitação |
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
| GET | `/filas?especialidade_id=&unidade_id=` | Fila ordenada pelas regras de prioridade (escopo vem de `escopo_da_equipe()`; no MVP, todas as unidades — [ADR-023](../decisions/ADR-023-escopo-todas-as-unidades.md)) |
| POST | `/solicitacoes/{id}/validar` | `EM_ANALISE` → `NA_FILA` |
| POST | `/agendamentos` | Propõe uma vaga para uma solicitação — fase futura (proposta manual, [ADR-021](../decisions/ADR-021-matching-automatico.md)) |
| POST | `/agendamentos/{id}/registrar-comparecimento` | `CONFIRMADO` → `REALIZADO` |
| POST | `/agendamentos/{id}/registrar-falta` | `CONFIRMADO` → `FALTOU` |
| GET | `/indicadores?de=&ate=&unidade_id=` | Confirmação, faltas, tempo até confirmação, vagas reaproveitadas, fila por especialidade |

### Administração
| Método | Rota | Descrição |
| --- | --- | --- |
| GET, POST, PATCH | `/unidades` | Unidades |
| GET, POST, PATCH | `/especialidades` | Especialidades |
| GET, POST, PATCH | `/ofertas` | Especialidade numa unidade, com prazo de resposta |
| GET, POST, PATCH | `/agendas` | Agendas; criar uma agenda gera as vagas da vigência |
| POST | `/vagas/{id}/bloquear` e `/vagas/{id}/desbloquear` | Estado administrativo da vaga |
| GET, PUT | `/regras-prioridade` | Ordem e parâmetros das regras da fila |
| GET | `/auditoria?entidade=&entidade_id=` | Trilha de auditoria |

### Operação
| Método | Rota | Descrição |
| --- | --- | --- |
| GET | `/health` | Verificação de saúde para o Nginx e o monitoramento |
