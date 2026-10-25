# API

> **Rascunho.** Sessão e conta (com a troca de senha), solicitações do paciente, resposta à proposta, painel da equipe, agenda do dia, presença, painel de vagas, indicadores do gestor e a administração de contas estão implementados; os demais endpoints são a proposta inicial e vão mudar durante a implementação. A referência definitiva será a documentação OpenAPI gerada pelo FastAPI em `/api/v1/docs`.

## Convenções (propostas)

- **Base:** `/api/v1`. Uma versão nova de URL só para mudanças incompatíveis.
- **Formato:** JSON com campos em `snake_case`. Datas em ISO 8601 com fuso (`2026-10-08T08:30:00-03:00`).
- **Autenticação:** cookies, descritos em [Sessão, cookies e CSRF](#sessão-cookies-e-csrf).
- **Erros:** formato *Problem Details* (RFC 9457), `application/problem+json`, com `type`, `title`, `status` e `detail`. O `type` é um caminho relativo estável; o frontend decide o tratamento pelo `type`, nunca pelo texto. Valores em uso:

  | `type` | Status | Quando aparece |
  | --- | --- | --- |
  | `about:blank` | conforme o erro (`404`, `405`, `422`, `500`, `503`…) | Erros HTTP genéricos: rota inexistente, método não permitido, validação da entrada (com a lista `errors`), erro de entrada do domínio (`422`, como critério de outra fila ou valor inválido), erro inesperado, banco indisponível no `/health` |
  | `/problemas/transicao-invalida` | `409` | O estado de origem não permite a transição pedida (ex.: proposta já respondida, cancelar depois do início da vaga, comparecimento antes do início) |
  | `/problemas/proposta-expirada` | `409` | Confirmar ou recusar depois de `expira_em`, mesmo antes de o Worker expirar a proposta ([UC-004](../requirements/use-cases/UC-004-confirmar-proposta.md)) |
  | `/problemas/tolerancia-nao-encerrada` | `409` | Falta registrada antes de `início da vaga + tolerância`, inclusive no limite exato (RN-013) |
  | `/problemas/erro-de-dominio` | `409` | Outra regra de negócio violada, sem `type` mais específico |
  | `/problemas/operacao-nao-permitida` | `409` | A operação é válida em geral, mas não neste alvo (ex.: suspender a si mesmo, um paciente ou o último ADMIN ativo; redefinir a senha de um ADMIN pela API; atribuir fila a quem não é ATENDENTE ou unidade a quem não é GESTOR) |
  | `/problemas/visao-central-nao-confirmada` | `409` | Gestor sem unidade (criar ou atribuir) sem `confirmar_visao_central: true`: sem unidades, ele passa a ver a central inteira ([ADR-025](../decisions/ADR-025-escopo-por-fila.md)) |
  | `/problemas/email-ja-cadastrado` | `409` | `POST /admin/usuarios` com e-mail que já tem conta. Só o ADMIN vê este erro, então a mensagem pode ser específica (diferente do registro, AM-005) |
  | `/problemas/nao-elegivel` | `409` | O paciente não cumpre a elegibilidade da fila (RN-017); o `detail` traz o motivo |
  | `/problemas/solicitacao-duplicada` | `409` | Já existe solicitação ativa do paciente na fila (RN-018); traz o campo extra `solicitacao_id` da existente |
  | `/problemas/sem-consentimento` | `403` | Sem consentimento vigente `AGENDAMENTO` para criar a solicitação (RN-009) |
  | `/problemas/cadastro-nao-concluido` | `409` | Registro com CPF, cartão do SUS ou e-mail já cadastrado; mensagem única, sem dizer qual campo (AM-005) |
  | `/problemas/nao-autenticado` | `401` | Sem sessão, access token inválido ou vencido, usuário suspenso ou sessão revogada; refresh inválido, vencido ou reutilizado |
  | `/problemas/credenciais-invalidas` | `401` | Login com identificador inexistente, senha errada ou conta suspensa; o corpo é idêntico nos três casos |
  | `/problemas/sem-permissao` | `403` | Papel sem permissão para a rota (`exige_papel`) |
  | `/problemas/csrf-invalido` | `403` | Escrita sem o header `X-CSRF-Token` ou com valor diferente do cookie |
  | `/problemas/muitas-tentativas` | `429` | Limite de tentativas de login, de registro ou de troca de senha; traz o header `Retry-After` (em segundos) |
  | `/problemas/troca-de-senha-obrigatoria` | `403` | Conta com senha temporária chamando qualquer rota autenticada que não seja `/me`, `/auth/trocar-senha`, `/auth/logout` ou `/auth/refresh` ([RN-022](../requirements/business-rules.md)) |
  | `/problemas/consulta-demorada` | `503` | Uma consulta dos indicadores passou de `INDICADORES_TIMEOUT_S` (padrão 5 s). Traz `Retry-After: 30` e uma mensagem neutra; nunca `500` |
  - **No OpenAPI:** o corpo de erro é o schema `Problema` (`type`, `title`, `status`, `detail`, `instance`, `errors`), servido como `application/problem+json`. O `HTTPValidationError` do FastAPI não existe no contrato, porque o `422` real também é Problem Details. Cada rota declara as respostas de erro que pode dar (`401`, `403`, `404`, `409`, `422`…), com o `type` na descrição. Os tipos ficam sob `/problemas/*` (tabela acima).
- **Códigos de status mais usados:**
  - `401`: sem sessão
  - `403`: sem permissão para o papel ou o escopo; CSRF inválido; troca de senha obrigatória
  - `404`: recurso inexistente ou de outro paciente (nunca revelar que existe)
  - `409`: conflito de estado, como vaga já ocupada ou proposta já respondida
  - `422`: validação
  - `429`: muitas tentativas de login, de registro ou de troca de senha (`Retry-After`)
  - `503`: banco indisponível no `/health`; consulta de indicadores acima do tempo máximo (`Retry-After`)
- **Ações de estado** são sub-recursos com `POST` (`/agendamentos/{id}/confirmar`), não `PATCH` no campo `status`. Assim cada transição tem validação, autorização e auditoria próprias.
- **Paginação** de listas: `?limit=&offset=`. `limit` de 1 a 100 (padrão 50); `offset` a partir de 0. A resposta é sempre `{total, itens}`, em que `total` conta os itens do filtro antes de `limit` e `offset`. Vale para `GET /filas`, `/solicitacoes`, `/avisos`, `/equipe/filas`, e o painel `/equipe/filas/{fila_id}/solicitacoes`. Exceções: o painel de vagas (`{total, sem_proposta, itens}`, que não pagina), `/avisos/contagem` (`{nao_lidos}`) e a agenda do dia, que segue um array simples.
- **Enums nomeados:** papéis, riscos, turnos, status, situações da vaga, tipos de evento, tipos e origens de critério e motivos de cancelamento vêm de `app/dominio/vocabulario.py`, a mesma fonte do `CHECK` do banco, e aparecem como enums com nome no OpenAPI. Mudar um valor exige migração e regenerar o snapshot (ver [Contrato OpenAPI](#contrato-openapi)).
- **Escopo da equipe por fila** ([ADR-025](../decisions/ADR-025-escopo-por-fila.md)): toda rota da equipe recebe `escopo = Depends(escopo_da_equipe)`, um conjunto de `fila_id`, e filtra por `fila_id IN escopo` **dentro da query**. Recurso de fila fora do escopo responde `404`, como recurso de outro paciente. Usuário suspenso não tem sessão ([ADR-028](../decisions/ADR-028-suspensao-de-acesso.md)).
- **O que o paciente vê** ([ADR-007](../decisions/ADR-007-paciente-ve-status.md)):
  - status da solicitação, a fila (nome e descrição) e a linha do tempo, com só os eventos de `historico_solicitacao` em que `visivel_paciente = true` (tipo, data e motivo);
  - **nunca** posição na fila, tamanho da fila, nota, pontos dos critérios, classificação de risco ou estimativa derivada deles;
  - os schemas de entrada do paciente aceitam só as respostas dos critérios com origem `PACIENTE`; os pontos e a nota são calculados no servidor.
- **O que a equipe vê:** além do que o paciente vê, a posição calculada na consulta, o risco, a nota, as respostas com os pontos e o histórico completo, com motivo. O CPF vai mascarado e o nome, abreviado na lista (ver [proteção de dados](../security/data-protection.md)).
- **Cache:** as respostas de `/api/v1/filas`, `/api/v1/solicitacoes`, `/api/v1/avisos`, `/api/v1/equipe/` e `/api/v1/admin/` levam `Cache-Control: no-store`, como `/auth/*` e `/me`. Em `/admin/` isso importa: a senha temporária sai na resposta. A exceção é `/termos/vigente` (público, `Cache-Control: public, max-age=3600`).

## Endpoints

### Sessão e conta
Caminhos sob `/api/v1`. Respostas de `/auth/*` e `/me` levam `Cache-Control: no-store`; `/termos/vigente` é a exceção pública.

| Método | Rota | Quem | CSRF | Descrição |
| --- | --- | --- | --- | --- |
| POST | `/auth/registro` | público | não | Cria a conta de paciente com consentimento obrigatório e inicia a sessão. `201` com `{papel, expira_em}`; campo fora do schema → `422`; duplicidade → `409`; limite por IP → `429` ([UC-001](../requirements/use-cases/UC-001-cadastrar-paciente.md)) |
| POST | `/auth/login` | público | não | Corpo `{identificador, senha}`. `identificador` com 11 dígitos (com ou sem pontuação) é CPF e vale só para paciente; qualquer outro valor é e-mail e vale só para a equipe. Responde `{papel, expira_em}`, nunca o token; com senha temporária, responde também `trocar_senha: true` (a chave não existe nos demais casos). Falha → `401` (`credenciais-invalidas`); bloqueio → `429` |
| POST | `/auth/refresh` | cookie `refresh_token` | sim | Renova a sessão com rotação do refresh token. Responde `{papel, expira_em}` |
| POST | `/auth/logout` | cookie `refresh_token` | sim | Revoga a família da sessão e apaga os cookies. `204`, idempotente: também responde `204` sem sessão |
| POST | `/auth/trocar-senha` | sessão, mesmo com senha temporária | sim | Corpo `{senha_atual, senha_nova}`; qualquer papel. `204`. A nova senha tem ao menos 10 caracteres e é diferente da atual (`422`). Senha atual errada → `422` no campo `senha_atual` e conta na janela de tentativas (`TROCA_SENHA`, mesmo limite do login, por usuário e por IP, AM-020); excesso → `429`, sem revogar nada. Zera `senha_temporaria`, **revoga as outras sessões** do usuário (a atual continua) e grava a auditoria `TROCAR_SENHA` (sem a senha) |
| GET | `/me` | sessão, mesmo com senha temporária | — | `{id, papel, nome, filas}`, sempre com as quatro chaves; com senha temporária, mais `trocar_senha: true`. Paciente: `nome` preenchido e `filas` `null`. Equipe: `nome` `null`, porque `usuario` não tem nome, e `filas` com os IDs do escopo ([ADR-025](../decisions/ADR-025-escopo-por-fila.md)). Nunca traz posição nem tamanho da fila ([ADR-007](../decisions/ADR-007-paciente-ve-status.md)) |
| GET | `/termos/vigente` | público | — | `{versao, texto}` do termo em vigor (`TERMO_VERSAO_ATUAL`), para a tela de cadastro; é a versão que `/auth/registro` aceita ([UC-001](../requirements/use-cases/UC-001-cadastrar-paciente.md)). Única rota com cache: `Cache-Control: public, max-age=3600` |

### Sessão, cookies e CSRF

| Cookie | Conteúdo | `httpOnly` | `Path` | Duração |
| --- | --- | --- | --- | --- |
| `access_token` | JWT HS256 com `sub`, `sid` (família da sessão), `papel` (só informativo; a autorização usa o papel do banco), `iat`, `exp` e `jti` | sim | `/api/v1` | 15 min |
| `refresh_token` | valor opaco; no banco só o hash | sim | `/api/v1/auth` | 7 dias |
| `csrf_token` | valor aleatório | não (o frontend lê) | `/` | 7 dias |

- `Secure`, `SameSite` e `Domain` vêm da configuração (`COOKIE_SECURE`, `COOKIE_SAMESITE`, `COOKIE_DOMAIN`).
- **CSRF (double-submit):** o header `X-CSRF-Token` tem de ser igual ao cookie `csrf_token`. É exigido em todo `POST`, `PUT`, `PATCH` e `DELETE`, menos `/auth/registro` e `/auth/login` (inclusive em `/auth/trocar-senha` e em todo `/admin`). Falha → `403` (`csrf-invalido`). Premissas e risco: AM-002 no [modelo de ameaças](../security/threat-model.md).
- **A cada requisição**, a dependência `usuario_da_sessao_sem_troca` (que `usuario_da_sessao` envolve) relê o usuário e a família da sessão. Suspensão, logout e reuso do refresh cortam o acesso na hora ([ADR-028](../decisions/ADR-028-suspensao-de-acesso.md)).
- **Troca obrigatória de senha** ([RN-022](../requirements/business-rules.md)): conta criada ou redefinida pelo ADMIN (ou pelo terminal) tem `usuario.senha_temporaria = true`. Até trocar a senha, a pessoa só chama `GET /me`, `POST /auth/trocar-senha`, `POST /auth/logout` e `POST /auth/refresh`; qualquer outra rota autenticada responde `403` `/problemas/troca-de-senha-obrigatoria`. O frontend decide pelo aviso `trocar_senha: true` do login e do `/me`. A regra está na dependência `usuario_da_sessao`, então rota nova nasce protegida (negar por padrão); só `/me` e a troca de senha usam `usuario_da_sessao_sem_troca`. O OpenAPI declara esse `403` em toda rota autenticada.
- O serviço de tokens aceita o token fora de cookie, mas a API **não lê** `Authorization: Bearer` e não vai ler: o app mobile foi descartado ([ADR-003](../decisions/ADR-003-autenticacao-web.md)).

### Paciente: filas e solicitações
Implementadas. Papel `PACIENTE` (dependência `paciente_da_sessao`); toda consulta filtra por `paciente_id` da sessão **dentro da query** e recurso alheio responde `404`. Os schemas de entrada usam `extra="forbid"` (AM-013).

| Método | Rota | Descrição |
| --- | --- | --- |
| GET | `/filas?limit&offset` | `{total, itens}` de filas ativas com unidade, especialidade, `descricao_paciente`, `elegivel` e `motivo_inelegivel` (texto fixo de `motivo_inelegivel()`). Sem contagem de pessoas; o `total` é o de filas ativas |
| GET | `/filas/{id}` | Detalhe da fila com os critérios de origem `PACIENTE` (`id`, `codigo`, `descricao`, `tipo`, `opcoes`). Sem peso, fator nem pontos |
| POST | `/solicitacoes` | Cria a solicitação `EM_ANALISE` ([UC-002](../requirements/use-cases/UC-002-solicitar-atendimento.md)). Corpo: `fila_id`, `turno_preferido` (`MANHA`, `TARDE`, `QUALQUER`), `origem_encaminhamento` (texto de 2 a 200), `respostas` (`[{criterio_id, valor}]`, até 50; `valor` texto até 200). `201` com o detalhe |
| GET | `/solicitacoes?situacao=abertas\|encerradas&limit&offset` | `{total, itens}` das minhas solicitações. `encerradas` = `ATENDIDA` e `CANCELADA`. Cada item traz o resumo e `agendamento_ativo` `{id, status, inicio, expira_em, unidade, profissional}` ou `null` (`expira_em` só na proposta), para confirmar ou recusar sem abrir o detalhe |
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
- **O paciente nunca recebe:** posição, tamanho da fila, nota, pontos, pesos, parâmetros ou fatores, `classificacao_risco`, `data_entrada_fila` nem a hora dos eventos.
- **`total` do envelope `{total, itens}`** é o tamanho da própria lista do paciente (suas solicitações ou avisos) ou o das filas ativas. Nunca é o tamanho de uma fila de espera (ADR-007).
- **`agendamento_ativo`** no detalhe (proposta ou consulta confirmada, ou `null`): `id`, `status` (`PROPOSTO` ou `CONFIRMADO`), `inicio` e `fim` da vaga no fuso de Recife, `profissional`, `unidade` `{id, sigla, nome}`, `endereco` da unidade e `expira_em` (só na proposta). O nome do profissional é visível ao paciente ([proteção de dados](../security/data-protection.md)).
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
Implementadas. Qualquer usuário autenticado vê só os próprios avisos do site (canal `IN_APP`); o filtro por `usuario_id` da sessão fica dentro da query e aviso de outro usuário responde `404`. A resposta não traz o canal `EMAIL`, o status de envio nem posição na fila. Respostas sem cache (`/api/v1/avisos`); a única rota com cache é `/termos/vigente`. A rota se chama `/avisos`, não `/notificacoes` como estava na proposta anterior.

| Método | Rota | Descrição |
| --- | --- | --- |
| GET | `/avisos?somente_nao_lidos&limit&offset` | `{total, itens}`, mais recentes primeiro (`limit` 1 a 100, padrão 50). Item: `id`, `tipo`, `titulo`, `corpo`, `solicitacao_id`, `criado_em`, `lido_em` (fuso de Recife) |
| GET | `/avisos/contagem` | `{nao_lidos}`, para o sino do menu |
| POST | `/avisos/lidos` | Marca todos como lidos; `204` |
| POST | `/avisos/{id}/lido` | Marca um como lido; `204`, idempotente (mantém a data da primeira leitura). Outro usuário ou inexistente → `404` |

Escrita exige `X-CSRF-Token`, como nas demais rotas.

### Equipe (atendente e gestor)
Implementadas as rotas `/equipe`. Prefixo `/equipe`; `escopo_da_equipe` é aplicado dentro da query e recurso fora do escopo responde `404`. Leitura: ATENDENTE, GESTOR e ADMIN (os indicadores, só GESTOR e ADMIN). Escrita: só ATENDENTE. Toda leitura é auditada ([controle de acesso](../security/access-control.md)).

| Método | Rota | Descrição |
| --- | --- | --- |
| GET | `/equipe/filas?limit&offset` | `{total, itens}` das filas do escopo (inclui inativas) com `contagem_por_status` |
| GET | `/equipe/filas/{fila_id}/criterios` | Critérios ativos de origem `REGULACAO` e `EQUIPE` da fila, para montar o formulário de `PUT .../respostas`: `[{id, codigo, descricao, tipo, origem, opcoes, faixas}]` (`opcoes` só em `OPCAO`, `faixas` `{min, max}` só em `NUMERO`). Sem peso, fator nem pontos. Fila fora do escopo → `404`. Sem auditoria, porque não traz dado de paciente |
| GET | `/equipe/filas/{fila_id}/solicitacoes?status&ordenacao=prioridade\|chegada&limit&offset` | `{total, itens}`. Item: `id`, `status`, `posicao`, `classificacao_risco`, `nota`, `data_entrada_fila`, `paciente_nome` abreviado ("Maria S."), `paciente_cpf` mascarado (`***.482.***-10`) e `ultima_mudanca` `{tipo, ocorrido_em}`, **sem motivo** (o motivo fica no detalhe). `ocorrido_em` mantém a hora para a equipe (decidido em 2026-10-19); só o paciente vê a data sem hora |
| GET | `/equipe/solicitacoes/{id}` | Nome completo, CPF mascarado, respostas (critério, origem, valor, pontos), nota e histórico completo com motivo |
| POST | `/equipe/solicitacoes/{id}/classificar` | Corpo `{classificacao_risco, motivo?}`. Ver abaixo |
| PUT | `/equipe/solicitacoes/{id}/respostas` | Grava respostas dos critérios de origem `REGULACAO` e `EQUIPE`. Ver abaixo |
| GET | `/equipe/filas/{fila_id}/agendamentos?data=AAAA-MM-DD` | Agenda do dia (dia em Recife): `[{id, solicitacao_id, inicio, fim, profissional, paciente_nome, status, presenca_registrada}]`, nome abreviado, sem CPF. Entram `PROPOSTO`, `CONFIRMADO`, `REALIZADO` e `FALTOU`. Leitura auditada (`CONSULTAR_AGENDAMENTOS`) ([UC-008](../requirements/use-cases/UC-008-registrar-comparecimento-ou-falta.md)) |
| POST | `/equipe/agendamentos/{id}/presenca` | Só ATENDENTE. Corpo `{compareceu: bool}`. Ver abaixo |
| GET | `/equipe/filas/{fila_id}/vagas?de=AAAA-MM-DD&ate=AAAA-MM-DD` | Painel de vagas: `{total, sem_proposta, itens: [{id, inicio, fim, profissional, situacao}]}`. Período de 1 a 31 dias, inclusivo; fora disso → `422`. Leitura auditada (`CONSULTAR_VAGAS`). Ver abaixo |
| GET | `/equipe/indicadores?de=&ate=&unidade_id=&fila_id=` | Só GESTOR e ADMIN (atendente → `403`). Indicadores do período, só contagens e razões, sem dado de paciente. Leitura auditada (`CONSULTAR_INDICADORES`). Ver [Indicadores do gestor](#indicadores-do-gestor) |

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

### Indicadores do gestor

`GET /equipe/indicadores?de=AAAA-MM-DD&ate=AAAA-MM-DD&unidade_id=&fila_id=` ([RF-037](../requirements/functional-requirements.md), fórmulas em [RN-021](../requirements/business-rules.md)).

- **Período:** `de` e `ate` são dias em `America/Recife`, inclusivos, de 1 a 366 dias; `ate` antes de `de`, período maior ou data fora de 2000-01-01 a 2100-12-31 → `422`. Não há padrão: os dois são obrigatórios.
- **Escopo:** `escopo_da_equipe` filtra as filas dentro da consulta (gestor: as filas das suas unidades; gestor sem unidade e ADMIN: todas). `unidade_id` e `fila_id` só encolhem o escopo. Unidade ou fila fora do escopo, inexistente ou sem nenhuma fila no escopo → `404`. Filas inativas entram nas contas.
- **Resposta** (`IndicadoresSaida`): `de`, `ate`, `unidade_id`, `fila_id`, `totais`, `semanas`, `tempo_de_espera` e `fila_atual`.
  - `totais` e cada item de `semanas` (um por segunda-feira de Recife que toca o período, mesmo sem dado, com a chave `semana`) trazem as mesmas contagens: `confirmadas`, `recusadas`, `expiradas`, `propostas_encerradas`, `propostas_canceladas_sem_resposta`, `realizadas`, `faltas`, `solicitacoes_criadas`, `desistencias`, `vagas_ofertadas`, `vagas_ocupadas`, `vagas_reaproveitadas`, `vagas_perdidas`, e as razões `taxa_confirmacao`, `taxa_recusa`, `taxa_expiracao`, `taxa_faltas`, `taxa_desistencia`. O total é a soma das semanas.
  - Razão com denominador 0 é `null`, nunca `0`; as razões vêm arredondadas a 4 casas.
  - `tempo_de_espera`: `{confirmacoes, mediana_dias, p90_dias}`, em dias com 2 casas; `null` sem dado.
  - `fila_atual`: `{VERMELHO, AMARELO, VERDE}`, as solicitações `NA_FILA` **agora**, qualquer que seja o período. Só a equipe vê isto; nada disso chega ao paciente ([ADR-007](../decisions/ADR-007-paciente-ve-status.md)).
- **Custo:** um número fixo de consultas agregadas no banco (sem N+1). Cada consulta roda com `SET LOCAL statement_timeout` (`INDICADORES_TIMEOUT_S`, padrão 5 s) e `jit = off`. Passou do tempo → `503` `/problemas/consulta-demorada` com `Retry-After: 30`, depois de desfazer a transação. O limite de requisições por usuário ficará no Nginx da VM, não na API *(proposta; o Nginx ainda não está configurado no repositório)* ([AM-025](../security/threat-model.md)).
- **Auditoria:** `CONSULTAR_INDICADORES` com `de`, `ate`, `unidade_id` e `fila_id` ([proteção de dados](../security/data-protection.md)).

### Equipe: demais rotas *(proposta)*
| Método | Rota | Descrição |
| --- | --- | --- |
| POST | `/agendamentos` | Propõe uma vaga para uma solicitação — fase futura (proposta manual, [ADR-021](../decisions/ADR-021-matching-automatico.md)) |

### Administração
Prefixo `/admin`, só `ADMIN` (`exige_papel("ADMIN")`), todas com `Cache-Control: no-store` e CSRF nas escritas. Os caminhos são relativos a `/api/v1`. Decidido em 2026-10-19: toda rota de administração fica sob `/admin/*`, porque `GET /filas` e `GET /filas/{id}` pertencem ao paciente. As rotas antigas `POST /usuarios/{id}/suspender` e `/reativar` **foram removidas**; só existem sob `/admin/usuarios/...`.

**Implementadas** ([RF-033](../requirements/functional-requirements.md), RF-035, RF-036; [ADR-028](../decisions/ADR-028-suspensao-de-acesso.md)):

| Método | Rota | Descrição |
| --- | --- | --- |
| GET | `/admin/usuarios?papel=&situacao=&limit&offset` | `{total, itens}` das contas da equipe (sem pacientes), na ordem de criação. Item: `id`, `email`, `papel`, `situacao`, `senha_temporaria`, `filas` (só ATENDENTE) e `unidades` (só GESTOR). Nunca traz hash nem senha |
| POST | `/admin/usuarios` | Corpo `{email, papel (ATENDENTE, GESTOR ou ADMIN), unidade_ids?, confirmar_visao_central?}`. Cria a conta com senha temporária forte (16 caracteres aleatórios) e `senha_temporaria = true`. `201` com `{id, senha_temporaria}`: **a senha aparece só nesta resposta**. `unidade_ids` só para GESTOR (outro papel → `422`); GESTOR sem unidade exige `confirmar_visao_central: true` (`409` `visao-central-nao-confirmada`); e-mail repetido → `409` `email-ja-cadastrado`. Auditoria `CRIAR_USUARIO` com papel e unidades |
| POST | `/admin/usuarios/{id}/redefinir-senha` | Nova senha temporária, devolvida uma vez (`200` `{id, senha_temporaria}`), e **revogação de todas as sessões** do usuário. Só ATENDENTE e GESTOR; ADMIN → `409` `operacao-nao-permitida` (a senha de um admin é recuperada pelo terminal, abaixo). Auditoria `REDEFINIR_SENHA` sem a senha |
| PUT | `/admin/usuarios/{id}/filas` | Substitui as filas do ATENDENTE (`{fila_ids}`, até 500). Outro papel → `409`; fila inexistente → `422`. Auditoria `ATRIBUIR_FILAS` com antes e depois. `204` |
| PUT | `/admin/usuarios/{id}/unidades` | Substitui as unidades do GESTOR (`{unidade_ids, confirmar_visao_central?}`). Lista vazia faz o gestor ver a central inteira e exige `confirmar_visao_central: true`. Outro papel → `409`. Auditoria `ATRIBUIR_UNIDADES` (com `visao_central`). `204` |
| POST | `/admin/usuarios/{id}/suspender` | Corpo `{motivo}` (3 a 500 caracteres). `204`. Regras e erros em [controle de acesso](../security/access-control.md) |
| POST | `/admin/usuarios/{id}/reativar` | `204`. Conta já ativa → `409` `transicao-invalida` |
| GET | `/admin/filas?limit&offset` | `{total, itens}` de todas as filas (inclui inativas) com `unidade` `{id, sigla}` e `especialidade` `{id, nome}`, para a tela de atribuição |

- Usuário inexistente → `404`. Toda alteração trava a conta alvo com `FOR UPDATE`.
- **Senha temporária:** gerada por `secrets.token_urlsafe(12)`, gravada só como hash, nunca em log nem em auditoria, e sem validade (risco aceito, AM-021). A pessoa troca no primeiro acesso ([RN-022](../requirements/business-rules.md)).
- **Pelo terminal do servidor:** `python -m app.infra.admin redefinir-senha --email <email>` gera a senha temporária de qualquer conta da equipe, inclusive ADMIN, e a imprime uma vez. Roda em qualquer `APP_ENV`, porque quem tem o servidor já tem o banco. Auditoria `REDEFINIR_SENHA` sem ator e com `origem: terminal`. Conta inexistente → mensagem no `stderr` e saída `1`.

**Propostas** (ainda não implementadas):

| Método | Rota | Descrição |
| --- | --- | --- |
| GET, POST, PATCH | `/admin/unidades` | Unidades |
| GET, POST, PATCH | `/admin/especialidades` | Especialidades |
| POST, PATCH | `/admin/filas` | Filas: descrição para o paciente, elegibilidade, prazo de confirmação e tolerância |
| GET, POST, PATCH | `/admin/filas/{id}/criterios` | Protocolo da fila: critérios, tipos, pesos e parâmetros |
| GET, POST, PATCH | `/admin/agendas` | Agendas; criar uma agenda gera as vagas da vigência |
| POST | `/admin/vagas/{id}/bloquear` e `/admin/vagas/{id}/desbloquear` | Estado administrativo da vaga |
| GET | `/admin/auditoria?entidade=&entidade_id=` | Trilha de auditoria |

### Operação
| Método | Rota | Descrição |
| --- | --- | --- |
| GET | `/health` | Verificação de saúde para o Nginx e o monitoramento |

## Contrato OpenAPI

- **Segurança:** o OpenAPI declara três esquemas. `cookieSessao` (cookie do access token) e `cookieRefresh` (cookie do refresh token) são `apiKey` em cookie. `csrfToken` é `apiKey` no header `X-CSRF-Token`; entra nas rotas de escrita, menos `/auth/registro` e `/auth/login`.
- **Snapshot:** `docs/architecture/openapi.json` é a cópia versionada do contrato. `apps/backend/tests/test_contrato.py` falha se a API gerar algo diferente dela. Depois de mudar rota, schema ou enum, regenere e revise o diff:

  ```bash
  ATUALIZAR_OPENAPI=1 scripts/testar.sh tests/test_contrato.py
  ```
