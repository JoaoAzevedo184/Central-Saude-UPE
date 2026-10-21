# API

> **Rascunho.** Sessão e conta, solicitações do paciente, resposta à proposta, painel da equipe, agenda do dia, presença e painel de vagas estão implementados; os demais endpoints são a proposta inicial e vão mudar durante a implementação. A referência definitiva será a documentação OpenAPI gerada pelo FastAPI em `/api/v1/docs`.

## Convenções (propostas)

- **Base:** `/api/v1`. Uma versão nova de URL só para mudanças incompatíveis.
- **Formato:** JSON com campos em `snake_case`. Datas em ISO 8601 com fuso (`2026-10-08T08:30:00-03:00`).
- **Autenticação:** cookies, descritos em [Sessão, cookies e CSRF](#sessão-cookies-e-csrf). O mobile, quando existir, usa `Authorization: Bearer` ([ADR-003](../decisions/ADR-003-autenticacao-web.md)).
- **Erros:** formato *Problem Details* (RFC 9457), `application/problem+json`, com `type`, `title`, `status` e `detail`. O `type` é um caminho relativo estável; o frontend decide o tratamento pelo `type`, nunca pelo texto. Valores em uso:

  | `type` | Status | Quando aparece |
  | --- | --- | --- |
  | `about:blank` | conforme o erro (`404`, `405`, `422`, `500`, `503`…) | Erros HTTP genéricos: rota inexistente, método não permitido, validação da entrada (com a lista `errors`), erro de entrada do domínio (`422`, como critério de outra fila ou valor inválido), erro inesperado, banco indisponível no `/health` |
  | `/problemas/transicao-invalida` | `409` | O estado de origem não permite a transição pedida (ex.: proposta já respondida, cancelar depois do início da vaga, comparecimento antes do início) |
  | `/problemas/proposta-expirada` | `409` | Confirmar ou recusar depois de `expira_em`, mesmo antes de o Worker expirar a proposta ([UC-004](../requirements/use-cases/UC-004-confirmar-proposta.md)) |
  | `/problemas/tolerancia-nao-encerrada` | `409` | Falta registrada antes de `início da vaga + tolerância`, inclusive no limite exato (RN-013) |
  | `/problemas/erro-de-dominio` | `409` | Outra regra de negócio violada, sem `type` mais específico |
  | `/problemas/operacao-nao-permitida` | `409` | A operação é válida em geral, mas não neste alvo (ex.: suspender a si mesmo, um paciente ou o último ADMIN ativo) |
  | `/problemas/nao-elegivel` | `409` | O paciente não cumpre a elegibilidade da fila (RN-017); o `detail` traz o motivo |
  | `/problemas/solicitacao-duplicada` | `409` | Já existe solicitação ativa do paciente na fila (RN-018); traz o campo extra `solicitacao_id` da existente |
  | `/problemas/sem-consentimento` | `403` | Sem consentimento vigente `AGENDAMENTO` para criar a solicitação (RN-009) |
  | `/problemas/cadastro-nao-concluido` | `409` | Registro com CPF, cartão do SUS ou e-mail já cadastrado; mensagem única, sem dizer qual campo (AM-005) |
  | `/problemas/nao-autenticado` | `401` | Sem sessão, access token inválido ou vencido, usuário suspenso ou sessão revogada; refresh inválido, vencido ou reutilizado |
  | `/problemas/credenciais-invalidas` | `401` | Login com identificador inexistente, senha errada ou conta suspensa; o corpo é idêntico nos três casos |
  | `/problemas/sem-permissao` | `403` | Papel sem permissão para a rota (`exige_papel`) |
  | `/problemas/csrf-invalido` | `403` | Escrita sem o header `X-CSRF-Token` ou com valor diferente do cookie |
  | `/problemas/muitas-tentativas` | `429` | Limite de tentativas de login ou de registro; traz o header `Retry-After` (em segundos) |
- **Códigos de status mais usados:**
  - `401`: sem sessão
  - `403`: sem permissão para o papel ou o escopo; CSRF inválido
  - `404`: recurso inexistente ou de outro paciente (nunca revelar que existe)
  - `409`: conflito de estado, como vaga já ocupada ou proposta já respondida
  - `422`: validação
  - `429`: muitas tentativas de login ou de registro (`Retry-After`)
- **Ações de estado** são sub-recursos com `POST` (`/agendamentos/{id}/confirmar`), não `PATCH` no campo `status`. Assim cada transição tem validação, autorização e auditoria próprias.
- **Paginação** de listas: `?limit=&offset=`. `limit` de 1 a 100 (padrão 50); `offset` a partir de 0.
- **Escopo da equipe por fila** ([ADR-025](../decisions/ADR-025-escopo-por-fila.md)): toda rota da equipe recebe `escopo = Depends(escopo_da_equipe)`, um conjunto de `fila_id`, e filtra por `fila_id IN escopo` **dentro da query**. Recurso de fila fora do escopo responde `404`, como recurso de outro paciente. Usuário suspenso não tem sessão ([ADR-028](../decisions/ADR-028-suspensao-de-acesso.md)).
- **O que o paciente vê** ([ADR-007](../decisions/ADR-007-paciente-ve-status.md)):
  - status da solicitação, a fila (nome e descrição) e a linha do tempo, com só os eventos de `historico_solicitacao` em que `visivel_paciente = true` (tipo, data e motivo);
  - **nunca** posição na fila, tamanho da fila, nota, pontos dos critérios, classificação de risco ou estimativa derivada deles;
  - os schemas de entrada do paciente aceitam só as respostas dos critérios com origem `PACIENTE`; os pontos e a nota são calculados no servidor.
- **O que a equipe vê:** além do que o paciente vê, a posição calculada na consulta, o risco, a nota, as respostas com os pontos e o histórico completo, com motivo. O CPF vai mascarado e o nome, abreviado na lista (ver [proteção de dados](../security/data-protection.md)).
- **Cache:** as respostas de `/api/v1/filas`, `/api/v1/solicitacoes` e `/api/v1/equipe/` levam `Cache-Control: no-store`, como `/auth/*` e `/me`.

## Endpoints

### Sessão e conta
Caminhos sob `/api/v1`. Respostas de `/auth/*` e `/me` levam `Cache-Control: no-store`.

| Método | Rota | Quem | CSRF | Descrição |
| --- | --- | --- | --- | --- |
| POST | `/auth/registro` | público | não | Cria a conta de paciente com consentimento obrigatório e inicia a sessão. `201` com `{papel, expira_em}`; campo fora do schema → `422`; duplicidade → `409`; limite por IP → `429` ([UC-001](../requirements/use-cases/UC-001-cadastrar-paciente.md)) |
| POST | `/auth/login` | público | não | Corpo `{identificador, senha}`. `identificador` com 11 dígitos (com ou sem pontuação) é CPF e vale só para paciente; qualquer outro valor é e-mail e vale só para a equipe. Responde `{papel, expira_em}`, nunca o token. Falha → `401` (`credenciais-invalidas`); bloqueio → `429` |
| POST | `/auth/refresh` | cookie `refresh_token` | sim | Renova a sessão com rotação do refresh token. Responde `{papel, expira_em}` |
| POST | `/auth/logout` | cookie `refresh_token` | sim | Revoga a família da sessão e apaga os cookies. `204`, idempotente: também responde `204` sem sessão |
| GET | `/me` | sessão | — | `{id, papel, nome}`. O paciente nunca recebe posição nem tamanho da fila ([ADR-007](../decisions/ADR-007-paciente-ve-status.md)). A equipe recebe `filas` (IDs do escopo, [ADR-025](../decisions/ADR-025-escopo-por-fila.md)) e `nome` fica ausente, porque `usuario` não tem nome |

### Sessão, cookies e CSRF

| Cookie | Conteúdo | `httpOnly` | `Path` | Duração |
| --- | --- | --- | --- | --- |
| `access_token` | JWT HS256 com `sub`, `sid` (família da sessão), `papel` (só informativo; a autorização usa o papel do banco), `iat`, `exp` e `jti` | sim | `/api/v1` | 15 min |
| `refresh_token` | valor opaco; no banco só o hash | sim | `/api/v1/auth` | 7 dias |
| `csrf_token` | valor aleatório | não (o frontend lê) | `/` | 7 dias |

- `Secure`, `SameSite` e `Domain` vêm da configuração (`COOKIE_SECURE`, `COOKIE_SAMESITE`, `COOKIE_DOMAIN`).
- **CSRF (double-submit):** o header `X-CSRF-Token` tem de ser igual ao cookie `csrf_token`. É exigido em todo `POST`, `PUT`, `PATCH` e `DELETE`, menos `/auth/registro` e `/auth/login`. Falha → `403` (`csrf-invalido`). Premissas e risco: AM-002 no [modelo de ameaças](../security/threat-model.md).
- **A cada requisição**, a dependência `usuario_da_sessao` relê o usuário e a família da sessão. Suspensão, logout e reuso do refresh cortam o acesso na hora ([ADR-028](../decisions/ADR-028-suspensao-de-acesso.md)).
- O serviço de tokens está pronto para `Authorization: Bearer`, mas a API ainda **não lê** esse header ([ADR-003](../decisions/ADR-003-autenticacao-web.md)).

### Paciente: filas e solicitações
Implementadas. Papel `PACIENTE` (dependência `paciente_da_sessao`); toda consulta filtra por `paciente_id` da sessão **dentro da query** e recurso alheio responde `404`. Os schemas de entrada usam `extra="forbid"` (AM-013).

| Método | Rota | Descrição |
| --- | --- | --- |
| GET | `/filas` | Filas ativas com unidade, especialidade, `descricao_paciente`, `elegivel` e `motivo_inelegivel` (texto fixo de `motivo_inelegivel()`). Sem contagem de pessoas |
| GET | `/filas/{id}` | Detalhe da fila com os critérios de origem `PACIENTE` (`id`, `codigo`, `descricao`, `tipo`, `opcoes`). Sem peso, fator nem pontos |
| POST | `/solicitacoes` | Cria a solicitação `EM_ANALISE` ([UC-002](../requirements/use-cases/UC-002-solicitar-atendimento.md)). Corpo: `fila_id`, `turno_preferido` (`MANHA`, `TARDE`, `QUALQUER`), `origem_encaminhamento` (texto de 2 a 200), `respostas` (`[{criterio_id, valor}]`, até 50; `valor` texto até 200). `201` com o detalhe |
| GET | `/solicitacoes?situacao=abertas\|encerradas&limit&offset` | Minhas solicitações. `encerradas` = `ATENDIDA` e `CANCELADA` |
| GET | `/solicitacoes/{id}` | `status`, fila, unidade, `data_pedido`, turno, `origem_encaminhamento`, as respostas próprias (`descricao`, `valor`; só origem `PACIENTE`), `linha_do_tempo` `[{tipo, data, motivo}]` só com `visivel_paciente = true`, na ordem `(ocorrido_em, seq)`, e `agendamento_ativo` (ver abaixo) |
| POST | `/solicitacoes/{id}/cancelar` | Corpo obrigatório `{motivo_codigo}`: `NAO_PRECISO_MAIS`, `CONSEGUI_EM_OUTRO_LUGAR`, `DIFICULDADE_DE_DESLOCAMENTO`, `CONFLITO_DE_HORARIO` ou `OUTRO`. Sem texto livre; a linha do tempo mostra o rótulo amigável. Vale em `EM_ANALISE`, `NA_FILA` (outbox `SOLICITACAO_CANCELADA`), `EM_PROPOSTA` e `AGENDADA` (outbox `AGENDAMENTO_CANCELADO`; o agendamento ativo vai para `CANCELADO` com `CANCELADO_PELO_PACIENTE`, só antes do início da vaga). `ATENDIDA`, `CANCELADA` ou vaga já iniciada → `409` (`transicao-invalida`) ([UC-005](../requirements/use-cases/UC-005-pedir-outra-data-ou-cancelar.md)) |
| POST | `/agendamentos/{id}/confirmar` | Só `PROPOSTO` e antes de `expira_em`. Agendamento `CONFIRMADO`, solicitação `AGENDADA`, evento `CONFIRMADA`, outbox `AGENDAMENTO_CONFIRMADO`. Depois do prazo → `409` `proposta-expirada`. Responde o detalhe da solicitação ([UC-004](../requirements/use-cases/UC-004-confirmar-proposta.md)) |
| POST | `/agendamentos/{id}/recusar` | "Esta data não serve". Só `PROPOSTO` e antes de `expira_em`. Agendamento `CANCELADO` com `RECUSADO_PELO_PACIENTE`, solicitação `NA_FILA` (mantém a posição ou vai para o fim, RN-020), evento `RECUSADA`, outbox `PROPOSTA_RECUSADA` ([UC-005](../requirements/use-cases/UC-005-pedir-outra-data-ou-cancelar.md)) |

Erros de `POST /solicitacoes`:

| Situação | Resposta |
| --- | --- |
| Sem consentimento `AGENDAMENTO` vigente | `403` `/problemas/sem-consentimento` |
| Paciente inelegível (RN-017) | `409` `/problemas/nao-elegivel` (`detail` = motivo) |
| Já existe solicitação ativa na fila (RN-018) | `409` `/problemas/solicitacao-duplicada`, com `solicitacao_id` da existente |
| Critério de outra fila ou de outra origem, repetido, ou valor inválido | `422` |
| Fila inexistente ou inativa | `422` |

- **`data` da linha do tempo é só o dia**, em `America/Recife`, sem hora: a hora de `ENTROU_NA_FILA` revelaria a `data_entrada_fila` e, com ela, a ordem de chegada (AM-014).
- **O paciente nunca recebe:** posição, tamanho da fila, total, nota, pontos, pesos, parâmetros ou fatores, `classificacao_risco`, `data_entrada_fila` nem a hora dos eventos.
- **`agendamento_ativo`** (proposta ou consulta confirmada, ou `null`): `id`, `status` (`PROPOSTO` ou `CONFIRMADO`), `inicio` e `fim` da vaga no fuso de Recife, `profissional`, `unidade` `{id, sigla, nome}`, `endereco` da unidade e `expira_em` (só na proposta). O nome do profissional é visível ao paciente ([proteção de dados](../security/data-protection.md)).
- Agendamento de outro paciente responde `404` em `confirmar` e `recusar`; o dono é conferido dentro da query.
- **Pendência:** "pedir outra data" com o agendamento já `CONFIRMADO` não existe; por ora o paciente cancela e abre nova solicitação ([UC-005](../requirements/use-cases/UC-005-pedir-outra-data-ou-cancelar.md)).

### Paciente: demais rotas *(proposta)*
| Método | Rota | Descrição |
| --- | --- | --- |
| GET | `/pacientes/me/consentimentos` | Consentimentos vigentes e histórico |
| POST | `/pacientes/me/consentimentos` | Concede um consentimento (finalidade, versão do termo) |
| POST | `/pacientes/me/consentimentos/{id}/revogar` | Revoga um consentimento |
| GET | `/pacientes/me/historico` | Histórico de atendimentos: realizados, faltas, propostas expiradas e canceladas |
| GET | `/pacientes/me/agendamentos` | Propostas, próximos e anteriores |
| GET | `/agendamentos/{id}` | Detalhe da proposta ou do agendamento (hoje vem em `agendamento_ativo` do detalhe da solicitação) |

### Avisos (RF-019)
Implementadas. Qualquer usuário autenticado vê só os próprios avisos do site (canal `IN_APP`); o filtro por `usuario_id` da sessão fica dentro da query e aviso de outro usuário responde `404`. A resposta não traz o canal `EMAIL`, o status de envio nem posição na fila. Respostas sem cache (`/api/v1/avisos`). A rota se chama `/avisos`, não `/notificacoes` como estava na proposta anterior.

| Método | Rota | Descrição |
| --- | --- | --- |
| GET | `/avisos?somente_nao_lidos&limit&offset` | Mais recentes primeiro (`limit` 1 a 100, padrão 50). Item: `id`, `tipo`, `titulo`, `corpo`, `solicitacao_id`, `criado_em`, `lido_em` (fuso de Recife) |
| GET | `/avisos/contagem` | `{nao_lidos}`, para o sino do menu |
| POST | `/avisos/lidos` | Marca todos como lidos; `204` |
| POST | `/avisos/{id}/lido` | Marca um como lido; `204`, idempotente (mantém a data da primeira leitura). Outro usuário ou inexistente → `404` |

Escrita exige `X-CSRF-Token`, como nas demais rotas.

### Equipe (atendente e gestor)
Implementadas as rotas `/equipe`. Prefixo `/equipe`; `escopo_da_equipe` é aplicado dentro da query e recurso fora do escopo responde `404`. Leitura: ATENDENTE, GESTOR e ADMIN. Escrita: só ATENDENTE. Toda leitura é auditada ([controle de acesso](../security/access-control.md)).

| Método | Rota | Descrição |
| --- | --- | --- |
| GET | `/equipe/filas` | Filas do escopo (inclui inativas) com `contagem_por_status` |
| GET | `/equipe/filas/{fila_id}/solicitacoes?status&ordenacao=prioridade\|chegada&limit&offset` | `{total, itens}`. Item: `id`, `status`, `posicao`, `classificacao_risco`, `nota`, `data_entrada_fila`, `paciente_nome` abreviado ("Maria S."), `paciente_cpf` mascarado (`***.482.***-10`) e `ultima_mudanca` `{tipo, ocorrido_em}`, **sem motivo** (o motivo fica no detalhe). `ocorrido_em` mantém a hora para a equipe (decidido em 2026-10-19); só o paciente vê a data sem hora |
| GET | `/equipe/solicitacoes/{id}` | Nome completo, CPF mascarado, respostas (critério, origem, valor, pontos), nota e histórico completo com motivo |
| POST | `/equipe/solicitacoes/{id}/classificar` | Corpo `{classificacao_risco, motivo?}`. Ver abaixo |
| PUT | `/equipe/solicitacoes/{id}/respostas` | Grava respostas dos critérios de origem `REGULACAO` e `EQUIPE`. Ver abaixo |
| GET | `/equipe/filas/{fila_id}/agendamentos?data=AAAA-MM-DD` | Agenda do dia (dia em Recife): `[{id, solicitacao_id, inicio, fim, profissional, paciente_nome, status, presenca_registrada}]`, nome abreviado, sem CPF. Entram `PROPOSTO`, `CONFIRMADO`, `REALIZADO` e `FALTOU`. Leitura auditada (`CONSULTAR_AGENDAMENTOS`) ([UC-008](../requirements/use-cases/UC-008-registrar-comparecimento-ou-falta.md)) |
| POST | `/equipe/agendamentos/{id}/presenca` | Só ATENDENTE. Corpo `{compareceu: bool}`. Ver abaixo |
| GET | `/equipe/filas/{fila_id}/vagas?de=AAAA-MM-DD&ate=AAAA-MM-DD` | Painel de vagas: `{total, sem_proposta, itens: [{id, inicio, fim, profissional, situacao}]}`. Período de 1 a 31 dias, inclusivo; fora disso → `422`. Leitura auditada (`CONSULTAR_VAGAS`). Ver abaixo |

- **Posição:** só para `NA_FILA`. É `ROW_NUMBER` sobre a fila inteira, calculado antes da paginação, e nunca gravado. A ordenação `prioridade` segue a mesma ordem de `ordenar_fila()` (risco, nota decrescente, chegada, id); `chegada` ordena só pela hora de chegada.
- **`classificar`:**
  - `EM_ANALISE` → `NA_FILA`: `data_entrada_fila` = agora; eventos `CLASSIFICADA` (invisível) e `ENTROU_NA_FILA` (visível, "Seu pedido entrou na fila."); outbox `SOLICITACAO_NA_FILA`.
  - `NA_FILA`: reclassifica. O `motivo` é obrigatório (3 a 500 caracteres); evento `RECLASSIFICADA` invisível ao paciente; sem outbox.
  - Outro estado → `409`.
  - É uma **simulação da regulação**: pelo [PRD](../product/PRD.md), o risco vem da regulação.
- **`respostas`:** a nota é recalculada por `calcular_nota`. Em `NA_FILA`, se a nota mudar, grava `RECLASSIFICADA` ("nota recalculada"), invisível ao paciente. Critério de origem `PACIENTE` ou de outra fila → `422`. Só em `EM_ANALISE` e `NA_FILA`; outro estado → `409` (o estado é conferido antes da validação da entrada). A auditoria guarda as respostas antes e depois.

- **Datas** (`data`, `de`, `ate`) aceitam de 2000-01-01 a 2100-12-31; fora disso → `422`.
- **`presenca`:** só de `CONFIRMADO` (outro estado → `409`). `true`: a partir do início da vaga (antes → `409` `transicao-invalida`); agendamento `REALIZADO`, solicitação `ATENDIDA`, evento `ATENDIDA`, outbox `ATENDIMENTO_REGISTRADO`. `false`: só depois de `início + tolerancia_atraso_min` da fila (antes ou no limite → `409` `tolerancia-nao-encerrada`); agendamento `FALTOU`, solicitação no fim da fila (RN-014), eventos `FALTOU` e `REENTROU_NA_FILA`, outbox `FALTA_REGISTRADA`. Agendamento fora do escopo → `404`. Responde o detalhe da solicitação da equipe.
- **`situacao` da vaga**, calculada na consulta por `situacao_da_vaga()` e nunca gravada: `PROPOSTA` e `CONFIRMADA` (agendamento ativo), `BLOQUEADA`, `ENCERRADA` (já começou, sem agendamento ativo), `LIVRE_SEM_PROPOSTA` (livre, mas `calcular_expira_em()` não deixa a janela mínima, RN-016; candidata a encaixe manual, [ADR-021](../decisions/ADR-021-matching-automatico.md)) e `LIVRE`. `sem_proposta` conta as `LIVRE_SEM_PROPOSTA`.

### Equipe: demais rotas *(proposta)*
| Método | Rota | Descrição |
| --- | --- | --- |
| POST | `/agendamentos` | Propõe uma vaga para uma solicitação — fase futura (proposta manual, [ADR-021](../decisions/ADR-021-matching-automatico.md)) |
| GET | `/indicadores?de=&ate=&unidade_id=` | Confirmação, faltas, tempo até confirmação, vagas reaproveitadas, tamanho de cada fila (gestor: unidades do escopo) |

### Administração
> **Decidido (2026-10-19):** toda rota de administração fica sob `/admin/*`, porque `GET /filas` e `GET /filas/{id}` pertencem ao paciente. Os caminhos abaixo são relativos a `/api/v1`, como no resto do documento.
>
> **Divergência temporária:** `POST /usuarios/{id}/suspender` e `/reativar` já estão implementados em `/api/v1/usuarios/...`, fora do prefixo. A mudança para `/admin/usuarios/...` exige alterar o código e os testes e fica para uma tarefa própria.

| Método | Rota | Descrição |
| --- | --- | --- |
| GET, POST, PATCH | `/admin/unidades` | Unidades |
| GET, POST, PATCH | `/admin/especialidades` | Especialidades |
| GET, POST, PATCH | `/admin/filas` | Filas: descrição para o paciente, elegibilidade, prazo de confirmação e tolerância |
| GET, POST, PATCH | `/admin/filas/{id}/criterios` | Protocolo da fila: critérios, tipos, pesos e parâmetros |
| GET, POST, PATCH | `/admin/agendas` | Agendas; criar uma agenda gera as vagas da vigência |
| POST | `/admin/vagas/{id}/bloquear` e `/admin/vagas/{id}/desbloquear` | Estado administrativo da vaga |
| GET, POST | `/admin/usuarios` | Contas da equipe |
| POST | `/admin/usuarios/{id}/suspender` e `/admin/usuarios/{id}/reativar` (hoje em `/usuarios/...`, ver divergência acima) | Suspensão de acesso ([ADR-028](../decisions/ADR-028-suspensao-de-acesso.md)). Suspender recebe `{motivo}` (3 a 500 caracteres). Só ADMIN; ambas respondem `204`. Regras em [controle de acesso](../security/access-control.md) |
| PUT | `/admin/usuarios/{id}/filas` e `/admin/usuarios/{id}/unidades` | Atribuições de escopo; filas só para ATENDENTE e unidades só para GESTOR |
| GET | `/admin/auditoria?entidade=&entidade_id=` | Trilha de auditoria |

### Operação
| Método | Rota | Descrição |
| --- | --- | --- |
| GET | `/health` | Verificação de saúde para o Nginx e o monitoramento |
