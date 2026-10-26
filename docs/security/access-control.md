# Controle de acesso

## Princípios

1. **Negar por padrão.** Uma rota sem regra explícita não é acessível.
2. **Papel + dono + escopo.** O papel diz o que a pessoa pode fazer. Para pacientes, o dono do recurso diz sobre quais registros. Para a equipe, o escopo (`escopo_da_equipe()`, [ADR-025](../decisions/ADR-025-escopo-por-fila.md)) diz em quais **filas**.
3. **Verificar no servidor, sempre.** Esconder um botão no frontend não é controle de acesso.
4. **Recurso alheio responde `404`**, para não confirmar que ele existe.
5. **Um usuário, um papel.** Se alguém precisar de dois papéis, ganha duas contas *(proposta)*.
6. **Suspenso não entra.** Usuário com `situacao = 'SUSPENSO'` não faz login (mesma mensagem genérica de credenciais inválidas), não renova o refresh token, não passa por `usuario_da_sessao` e não tem escopo. A conta nunca é apagada ([ADR-028](../decisions/ADR-028-suspensao-de-acesso.md)).
7. **Senha temporária só serve para trocar a senha.** Conta criada ou redefinida pelo admin tem `senha_temporaria = true`; até a troca, toda rota autenticada responde `403` `troca-de-senha-obrigatoria`, menos `/me`, `/auth/trocar-senha`, `/auth/logout` e `/auth/refresh` ([RN-022](../requirements/business-rules.md)).

## Matriz de permissões

Legenda:
- ✅ permitido
- 🔒 só os próprios registros
- 🏥 só nas filas do escopo de `escopo_da_equipe()` ([ADR-025](../decisions/ADR-025-escopo-por-fila.md)), conforme a tabela de escopo abaixo
- — negado

| Ação | Paciente | Atendente | Gestor | Admin |
| --- | --- | --- | --- | --- |
| Criar conta de paciente | ✅ (sem login) | — | — | — |
| Ver e revogar consentimentos | 🔒 | — | — | — |
| Criar solicitação | 🔒 | — | — | — |
| Ver solicitações, agendamentos e linha do tempo | 🔒 (só eventos visíveis ao paciente; sem posição na fila) | 🏥 | 🏥 | ✅ |
| Confirmar, pedir outra data (só proposta), cancelar (até o início da vaga) | 🔒 | — | — | — |
| Ver e marcar como lidos os próprios avisos do site (`/avisos`; aviso de outro usuário → `404`) | 🔒 | 🔒 | 🔒 | 🔒 |
| Ver data, hora, unidade, endereço e **nome do profissional** da própria proposta ou consulta | 🔒 | 🏥 | 🏥 | ✅ |
| Cancelar agendamento em nome do paciente | — | 🏥 *(proposta)* | — | — |
| Validar/classificar solicitação (simulação da regulação) | — | 🏥 | — | — |
| Responder critérios de origem `REGULACAO`/`EQUIPE` | — | 🏥 *(proposta)* | — | — |
| Ver painel da fila e detalhe da solicitação, com posição e histórico | — | 🏥 | 🏥 | ✅ |
| Propor vaga | — | 🏥 fase futura ([ADR-021](../decisions/ADR-021-matching-automatico.md)) | — | — |
| Ver agenda do dia (nome abreviado) e painel de vagas | — | 🏥 | 🏥 | ✅ |
| Ler os critérios de origem `REGULACAO`/`EQUIPE` de uma fila (`GET /equipe/filas/{id}/criterios`): só o formulário, sem pesos, fatores nem pontos; sem auditoria | — | 🏥 | 🏥 | ✅ |
| Ler o termo de uso vigente (`GET /termos/vigente`) | público | público | público | público |
| Registrar comparecimento ou falta | — | 🏥 | — | — |
| Ver indicadores (`GET /equipe/indicadores`: só contagens e razões, sem dado de paciente; auditado). Atendente → `403`; `unidade_id` ou `fila_id` fora do escopo → `404` | — | — | 🏥 | ✅ |
| Cadastrar unidades, especialidades e filas (elegibilidade, prazos) | — | — | — | ✅ |
| Cadastrar agendas, bloquear vagas | — | — | — | ✅ |
| Configurar o protocolo de critérios das filas | — | — | — | ✅ |
| Consultar auditoria | — | — | — | ✅ |
| Criar contas da equipe (`POST /admin/usuarios`; senha temporária devolvida uma vez). Gestor sem unidade exige confirmar a visão central | — | — | — | ✅ |
| Atribuir filas a atendentes e unidades a gestores (o papel do alvo é conferido na API; gestor sem unidade exige confirmar a visão central) | — | — | — | ✅ |
| Suspender e reativar contas da equipe (`POST /admin/usuarios/{id}/suspender` e `/reativar`) | — | — | — | ✅ |
| Redefinir a senha de atendente ou gestor (`POST /admin/usuarios/{id}/redefinir-senha`) | — | — | — | ✅ |
| Redefinir a senha de um admin | — | — | — | só pelo terminal do servidor (`python -m app.infra.admin redefinir-senha`) |
| Trocar a própria senha (`POST /auth/trocar-senha`; vale também com senha temporária) | 🔒 | 🔒 | 🔒 | 🔒 |

## Escopo da equipe

| Papel | Filas que vê e opera | De onde vem |
| --- | --- | --- |
| ATENDENTE | Só as filas atribuídas a ele; sem atribuição, nenhuma | `usuario_fila` |
| GESTOR | As filas das unidades atribuídas a ele (um hospital); sem nenhuma unidade, a central inteira | `usuario_unidade` |
| ADMIN | Todas | — |
| Qualquer papel `SUSPENSO` | Nenhuma | `usuario.situacao` |

A regra está em `calcular_escopo()` (`app/dominio/acesso.py`) e falha fechada: papel desconhecido ou dado ausente devolvem um escopo vazio.

O banco não impede que um usuário de outro papel apareça em `usuario_fila` ou `usuario_unidade`. O domínio ignora essas linhas, e a API de administração valida o papel ao gravar a atribuição (RF-035): fila só para ATENDENTE e unidade só para GESTOR, senão `409`.

**Gestor sem unidade vê a central inteira**, e isso nunca acontece por omissão: criar ou atribuir um gestor sem unidades exige `confirmar_visao_central: true`, senão `409` `visao-central-nao-confirmada` (`verificar_atribuicao_de_unidades`, [AM-022](threat-model.md)). A auditoria marca `visao_central` na atribuição.

## Implementação

- O papel vem do usuário da sessão, carregado no servidor; nunca do corpo ou dos parâmetros da requisição.
- Uma dependência do FastAPI por regra de acesso, aplicada na rota; as rotas não repetem a verificação à mão:
  - `usuario_da_sessao_sem_troca`: lê o access token, carrega o usuário e confere, **a cada requisição**, a situação (`pode_autenticar()`) e se a família da sessão (`sid`) segue ativa. Falha → `401`. Só `/me` e `/auth/trocar-senha` o usam direto;
  - `usuario_da_sessao`: constrói em cima da anterior e, com `senha_temporaria`, responde `403` `troca-de-senha-obrigatoria`. É o que as demais rotas usam, então rota nova nasce protegida;
  - `exige_papel(...)`: constrói em cima de `usuario_da_sessao` e responde `403` para outro papel (a rota de administração usa `exige_papel("ADMIN")`; a de indicadores, `GESTOR` e `ADMIN`);
  - `escopo_da_equipe`: conjunto de filas da equipe;
  - `paciente_da_sessao`: exige o papel `PACIENTE` e devolve o paciente da sessão; as rotas do paciente usam o `paciente_id` dele na query.
- Consultas do paciente sempre incluem `paciente_id = <paciente da sessão>` na própria query, em vez de buscar pelo ID e comparar depois.
- **Obrigatório:** toda rota da equipe recebe `escopo = Depends(escopo_da_equipe)`, um conjunto de `fila_id`, e filtra por `fila_id IN escopo` dentro da query. Recurso de fila fora do escopo responde `404`.

## Auditoria das leituras da equipe

Ler o painel, o detalhe, a agenda do dia, o painel de vagas e os indicadores também é auditado (AM-007), sem nome, CPF nem respostas:

| Ação | Entidade | Dados registrados |
| --- | --- | --- |
| `CONSULTAR_PAINEL` | `fila` | filtros `status`, `ordenacao`, `limit` e `offset` |
| `CONSULTAR_SOLICITACAO` | `solicitacao` | só o ID da entidade |
| `CONSULTAR_AGENDAMENTOS` | `fila` | a `data` consultada |
| `CONSULTAR_VAGAS` | `fila` | o período `de` e `ate` |
| `CONSULTAR_INDICADORES` | `fila`, `unidade` ou `usuario` (o filtro mais específico; sem filtro, o próprio gestor) | `de`, `ate`, `unidade_id` e `fila_id` |

## Auditoria da administração

Toda escrita de `/admin` grava uma linha em `auditoria` com o admin como ator e a conta alvo como entidade. **Nunca** vão para lá senha, hash nem e-mail completo.

| Ação | Dados registrados |
| --- | --- |
| `CRIAR_USUARIO` | papel e IDs das unidades |
| `REDEFINIR_SENHA` | nada (pelo terminal: ator vazio e `origem: terminal`) |
| `ATRIBUIR_FILAS` | IDs das filas, antes e depois |
| `ATRIBUIR_UNIDADES` | IDs das unidades, antes e depois, e `visao_central` |
| `SUSPENDER`, `REATIVAR` | situação antes e depois |
| `TROCAR_SENHA` (o próprio usuário) | nada |

## Suspender e reativar ([ADR-028](../decisions/ADR-028-suspensao-de-acesso.md))

Rotas `POST /admin/usuarios/{id}/suspender` (corpo `motivo`) e `POST /admin/usuarios/{id}/reativar`: só `ADMIN` (`exige_papel("ADMIN")`), respondem `204` e gravam auditoria. As rotas antigas, fora do prefixo `/admin`, foram removidas ([API](../architecture/api-design.md#administração)).

| Situação | Resposta |
| --- | --- |
| Usuário inexistente | `404` |
| Alvo é paciente (só contas da equipe são suspensas) | `409` (`operacao-nao-permitida`) |
| Admin suspende a si mesmo | `409` (`operacao-nao-permitida`) |
| Alvo é o último ADMIN ativo | `409` (`operacao-nao-permitida`) |
| Conta já suspensa (ou já ativa, ao reativar) | `409` (`transicao-invalida`) |

- A rota trava os ADMIN ativos com `FOR UPDATE` antes de contar, para dois admins suspendendo um ao outro ao mesmo tempo não deixarem a central sem nenhum.
- Suspender **revoga todas as sessões** do usuário. O access token que ainda não venceu cai na próxima requisição, porque `usuario_da_sessao` relê a situação e a família.

## Testes obrigatórios

Para cada rota com ID:
- paciente A tentando acessar o recurso do paciente B → `404`;
- papel sem permissão → `403`;
- sem sessão → `401`;
- requisição de escrita sem header CSRF → rejeitada.

Para cada rota da equipe:
- atendente acessando recurso de fila não atribuída → `404`;
- gestor de um hospital acessando fila de outro hospital → `404`;
- usuário suspenso → `401` (não tem sessão).
