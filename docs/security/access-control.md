# Controle de acesso

## Princípios

1. **Negar por padrão.** Uma rota sem regra explícita não é acessível.
2. **Papel + dono + escopo.** O papel diz o que a pessoa pode fazer. Para pacientes, o dono do recurso diz sobre quais registros. Para a equipe, o escopo de unidade (`escopo_da_equipe()`, [ADR-023](../decisions/ADR-023-escopo-todas-as-unidades.md)) diz em quais unidades.
3. **Verificar no servidor, sempre.** Esconder um botão no frontend não é controle de acesso.
4. **Recurso alheio responde `404`**, para não confirmar que ele existe.
5. **Um usuário, um papel.** Se alguém precisar de dois papéis, ganha duas contas *(proposta)*.

## Matriz de permissões

Legenda:
- ✅ permitido
- 🔒 só os próprios registros
- 🏥 dentro do escopo de `escopo_da_equipe()`; no MVP, o escopo é "todas as unidades" ([ADR-023](../decisions/ADR-023-escopo-todas-as-unidades.md))
- — negado

| Ação | Paciente | Atendente | Gestor | Admin |
| --- | --- | --- | --- | --- |
| Criar conta de paciente | ✅ (sem login) | — | — | — |
| Ver e revogar consentimentos | 🔒 | — | — | — |
| Criar solicitação | 🔒 | — | — | — |
| Ver solicitações e agendamentos | 🔒 (sem posição na fila) | 🏥 | 🏥 | ✅ |
| Confirmar, pedir outra data, cancelar | 🔒 | — | — | — |
| Cancelar agendamento em nome do paciente | — | 🏥 *(proposta)* | — | — |
| Validar solicitação | — | 🏥 | — | — |
| Ver fila ordenada | — | 🏥 | 🏥 | ✅ |
| Propor vaga | — | 🏥 fase futura ([ADR-021](../decisions/ADR-021-matching-automatico.md)) | — | — |
| Registrar comparecimento ou falta | — | 🏥 | — | — |
| Ver indicadores | — | — | 🏥 | ✅ |
| Cadastrar unidades, especialidades, ofertas | — | — | — | ✅ |
| Cadastrar agendas, bloquear vagas | — | — | — | ✅ |
| Configurar regras de prioridade | — | — | — | ✅ |
| Consultar auditoria | — | — | — | ✅ |
| Criar contas da equipe | — | — | — | ✅ |

No MVP, `escopo_da_equipe()` devolve todas as unidades, então todo 🏥 equivale na prática a ✅. O 🏥 continua na matriz porque o escopo sempre passa pela dependência.

## Implementação

- O papel vem do usuário da sessão, carregado no servidor; nunca do corpo ou dos parâmetros da requisição.
- Uma dependência do FastAPI por regra de acesso (`exige_papel(...)`, `paciente_da_sessao`, `escopo_da_equipe`), aplicada na rota; as rotas não repetem a verificação à mão.
- Consultas do paciente sempre incluem `paciente_id = <paciente da sessão>` na própria query, em vez de buscar pelo ID e comparar depois.
- **Obrigatório desde o primeiro dia:** toda rota da equipe recebe `escopo = Depends(escopo_da_equipe)`, e as consultas recebem o escopo como parâmetro. No MVP, o escopo é "todas as unidades"; com `ESCOPO_POR_UNIDADE=true`, passa a ser as unidades do usuário, sem mudar as rotas ([ADR-023](../decisions/ADR-023-escopo-todas-as-unidades.md)).

## Testes obrigatórios

Para cada rota com ID:
- paciente A tentando acessar o recurso do paciente B → `404`;
- papel sem permissão → `403`;
- sem sessão → `401`;
- requisição de escrita sem header CSRF → rejeitada.
