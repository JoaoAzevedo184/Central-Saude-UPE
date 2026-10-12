# Controle de acesso

## Princípios

1. **Negar por padrão.** Uma rota sem regra explícita não é acessível.
2. **Papel + dono + escopo.** O papel diz o que a pessoa pode fazer. Para pacientes, o dono do recurso diz sobre quais registros. Para a equipe, o escopo de unidade (**ABERTO-3**) diz em quais unidades.
3. **Verificar no servidor, sempre.** Esconder um botão no frontend não é controle de acesso.
4. **Recurso alheio responde `404`**, para não confirmar que ele existe.
5. **Um usuário, um papel.** Se alguém precisar de dois papéis, ganha duas contas *(proposta)*.

## Matriz de permissões

Legenda:
- ✅ permitido
- 🔒 só os próprios registros
- 🏥 dentro do escopo de unidade (**ABERTO-3**)
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
| Propor vaga | — | 🏥 se **ABERTO-1** = manual | — | — |
| Registrar comparecimento ou falta | — | 🏥 | — | — |
| Ver indicadores | — | — | 🏥 | ✅ |
| Cadastrar unidades, especialidades, ofertas | — | — | — | ✅ |
| Cadastrar agendas, bloquear vagas | — | — | — | ✅ |
| Configurar regras de prioridade | — | — | — | ✅ |
| Consultar auditoria | — | — | — | ✅ |
| Criar contas da equipe | — | — | — | ✅ |

Se **ABERTO-3** for "todas as unidades", todo 🏥 vira ✅ para aquele papel.

## Implementação

- O papel vem do usuário da sessão, carregado no servidor; nunca do corpo ou dos parâmetros da requisição.
- Uma dependência do FastAPI por regra de acesso (`exige_papel(...)`, `paciente_da_sessao`, `escopo_da_equipe`), aplicada na rota; as rotas não repetem a verificação à mão.
- Consultas do paciente sempre incluem `paciente_id = <paciente da sessão>` na própria query, em vez de buscar pelo ID e comparar depois.
- Se o escopo por unidade for adotado, as consultas da equipe recebem o conjunto de unidades permitidas e filtram por ele.

## Testes obrigatórios

Para cada rota com ID:
- paciente A tentando acessar o recurso do paciente B → `404`;
- papel sem permissão → `403`;
- sem sessão → `401`;
- requisição de escrita sem header CSRF → rejeitada.
