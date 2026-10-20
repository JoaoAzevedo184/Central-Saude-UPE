# Controle de acesso

## Princípios

1. **Negar por padrão.** Uma rota sem regra explícita não é acessível.
2. **Papel + dono + escopo.** O papel diz o que a pessoa pode fazer. Para pacientes, o dono do recurso diz sobre quais registros. Para a equipe, o escopo (`escopo_da_equipe()`, [ADR-025](../decisions/ADR-025-escopo-por-fila.md)) diz em quais **filas**.
3. **Verificar no servidor, sempre.** Esconder um botão no frontend não é controle de acesso.
4. **Recurso alheio responde `404`**, para não confirmar que ele existe.
5. **Um usuário, um papel.** Se alguém precisar de dois papéis, ganha duas contas *(proposta)*.
6. **Suspenso não entra.** Usuário com `situacao = 'SUSPENSO'` não faz login (mesma mensagem genérica de credenciais inválidas), não renova o refresh token, não passa por `usuario_da_sessao` e não tem escopo. A conta nunca é apagada ([ADR-028](../decisions/ADR-028-suspensao-de-acesso.md)).

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
| Confirmar, pedir outra data, cancelar | 🔒 | — | — | — |
| Cancelar agendamento em nome do paciente | — | 🏥 *(proposta)* | — | — |
| Validar solicitação | — | 🏥 | — | — |
| Ver fila ordenada, com posição e motivo da última mudança | — | 🏥 | 🏥 | ✅ |
| Propor vaga | — | 🏥 fase futura ([ADR-021](../decisions/ADR-021-matching-automatico.md)) | — | — |
| Registrar comparecimento ou falta | — | 🏥 | — | — |
| Ver indicadores | — | — | 🏥 | ✅ |
| Cadastrar unidades, especialidades e filas (elegibilidade, prazos) | — | — | — | ✅ |
| Cadastrar agendas, bloquear vagas | — | — | — | ✅ |
| Configurar o protocolo de critérios das filas | — | — | — | ✅ |
| Consultar auditoria | — | — | — | ✅ |
| Criar contas da equipe | — | — | — | ✅ |
| Atribuir filas a atendentes e unidades a gestores | — | — | — | ✅ |
| Suspender e reativar contas da equipe (`POST /usuarios/{id}/suspender` e `/reativar`) | — | — | — | ✅ |

## Escopo da equipe

| Papel | Filas que vê e opera | De onde vem |
| --- | --- | --- |
| ATENDENTE | Só as filas atribuídas a ele; sem atribuição, nenhuma | `usuario_fila` |
| GESTOR | As filas das unidades atribuídas a ele (um hospital); sem nenhuma unidade, a central inteira | `usuario_unidade` |
| ADMIN | Todas | — |
| Qualquer papel `SUSPENSO` | Nenhuma | `usuario.situacao` |

A regra está em `calcular_escopo()` (`app/dominio/acesso.py`) e falha fechada: papel desconhecido ou dado ausente devolvem um escopo vazio.

O banco não impede que um usuário de outro papel apareça em `usuario_fila` ou `usuario_unidade`. O domínio ignora essas linhas, e a futura tela de administração deve validar o papel ao gravar a atribuição (RF-035).

## Implementação

- O papel vem do usuário da sessão, carregado no servidor; nunca do corpo ou dos parâmetros da requisição.
- Uma dependência do FastAPI por regra de acesso, aplicada na rota; as rotas não repetem a verificação à mão:
  - `usuario_da_sessao`: lê o access token, carrega o usuário e confere, **a cada requisição**, a situação (`pode_autenticar()`) e se a família da sessão (`sid`) segue ativa. Falha → `401`;
  - `exige_papel(...)`: constrói em cima de `usuario_da_sessao` e responde `403` para outro papel;
  - `escopo_da_equipe`: conjunto de filas da equipe;
  - `paciente_da_sessao`: *(proposta)*, ainda não implementada.
- Consultas do paciente sempre incluem `paciente_id = <paciente da sessão>` na própria query, em vez de buscar pelo ID e comparar depois.
- **Obrigatório:** toda rota da equipe recebe `escopo = Depends(escopo_da_equipe)`, um conjunto de `fila_id`, e filtra por `fila_id IN escopo` dentro da query. Recurso de fila fora do escopo responde `404`.

## Suspender e reativar ([ADR-028](../decisions/ADR-028-suspensao-de-acesso.md))

Rotas `POST /usuarios/{id}/suspender` (corpo `motivo`) e `POST /usuarios/{id}/reativar`: só `ADMIN` (`exige_papel("ADMIN")`), respondem `204` e gravam auditoria.

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
