# Base técnica do frontend

Implementada em `apps/web`, conforme a autorização de 2026-10-21 para a base do [ADR-001](../decisions/ADR-001-stack.md). Não inclui login, cadastro, painéis, formulários ou outras telas de negócio.

## Organização e dependências

React e TypeScript com Vite; React Router no modo declarativo; TanStack Query para consultas em memória; React Hook Form e Zod preparados para os futuros formulários. O transporte usa `fetch` nativo. ESLint, TypeScript e Vitest verificam a base. `openapi-typescript` gera os tipos do contrato real do FastAPI.

- `src/app`: rotas e criação do QueryClient.
- `src/layouts`: layouts vazios de paciente e equipe, com `Outlet` para futuras rotas filhas.
- `src/shared/api`: HTTP, CSRF, Problem Details e tipos gerados.
- `src/shared/auth`: consulta da sessão e guarda por papel.
- `src/styles`: CSS global mínimo.
- `src/test`: preparação dos testes; testes ficam junto dos módulos.
- `scripts`: geração e conferência dos tipos OpenAPI.

## Transporte e autenticação

O navegador sempre consulta `/api/v1` na mesma origem. Em desenvolvimento, o Vite encaminha `/api` para `WEB_API_PROXY_TARGET`, definido no `.env` da raiz (exemplo no `.env.example`); não remove nem reescreve o prefixo. Em produção, o Nginx precisa servir `dist` com fallback de rotas para `index.html` e encaminhar `/api` ao backend. `vite preview` apenas inspeciona o build, sem proxy de API.

O cliente envia cookies com `credentials: same-origin`, desabilita cache HTTP e recusa redirects e destinos fora de `/api/v1`. Access e refresh tokens continuam em cookies `httpOnly`, sem leitura ou persistência no JavaScript. Escritas leem o cookie `csrf_token` no momento do envio e preenchem `X-CSRF-Token`, inclusive após a rotação. Login e registro continuam dispensados de CSRF no servidor, como no [ADR-003](../decisions/ADR-003-autenticacao-web.md); o cliente pode enviar o header quando o cookie já existir.

Um `401` fora de `/auth/*` dispara `POST /auth/refresh`. Requisições simultâneas compartilham uma única promessa por instância da aplicação. Um contador identifica `401` atrasado para evitar outra rotação. Depois do refresh, cada pedido é repetido no máximo uma vez; falha de rede, `403`, conflitos e validação não são repetidos. Cancelar um pedido não cancela a renovação compartilhada. Outras abas têm instâncias próprias, sujeitas à tolerância do backend descrita no ADR-003.

Qualquer falha do refresh (HTTP ou rede), em qualquer consulta ou escrita, notifica `GerenciarSessao`: cancela as consultas em andamento, limpa o cache da aplicação e marca a sessão como ausente. Respostas tardias das consultas canceladas não repõem dados no cache. Um novo `401` após a única repetição também encerra a sessão. O redirecionamento para `/entrar` guarda caminho, busca e fragmento em `location.state.origem`, sem persistência em storage. `rotaAposLogin(location.state)` fornece o destino de retorno para a futura tela de login e recusa destinos externos ou que repitam `/entrar`.

`ApiError` preserva os campos e extensões de Problem Details e a resposta original, inclusive headers como `Retry-After`. Sua `message` vem de `mensagensPorTipo`, que cobre os types anunciados no OpenAPI; tipos desconhecidos, HTML ou corpo inválido geram mensagem genérica, sem expor `title`, `detail` ou o corpo do proxy. Tratamentos específicos devem usar `problem.type`, nunca comparar `detail`. Não há logs de payloads nem de dados da sessão.

`aplicarErrosDeValidacao(error, setError, campos)` integra o `errors` do 422 ao React Hook Form. Recebe a lista explícita de caminhos dos campos do formulário (inclusive índices como `respostas.0.valor`), remove somente o prefixo `body` de `loc`, aplica o primeiro erro de cada campo e foca o primeiro. Erros globais, de parâmetros, de campos extras ou malformados vão para `root.server` com mensagem genérica; erros de outros status retornam `false` para o chamador tratar.

## Sessão e rotas

`GET /me` fornece a sessão; o papel é validado contra `PACIENTE`, `ATENDENTE`, `GESTOR` e `ADMIN`. Papel desconhecido ou erro de consulta fecha o acesso. A consulta não persiste em storage, não usa retries automáticos e é revalidada nas montagens e eventos de foco/reconexão tratados pelo TanStack Query. A guarda oculta o layout durante a revalidação.

| Rota | Acesso | Conteúdo atual |
| --- | --- | --- |
| `/` | Público | Identificação mínima da base |
| `/entrar` | Público | Identificação da futura tela de login |
| `/paciente` | PACIENTE | Layout vazio |
| `/equipe` | ATENDENTE, GESTOR, ADMIN | Layout vazio |
| Outros caminhos | Público | Mensagem de página inexistente |

Sem sessão, a guarda redireciona para `/entrar` e guarda a origem no mesmo formato usado por `GerenciarSessao`. O formulário de login continua pendente. Papel diferente exibe acesso negado. A guarda apenas controla a navegação: dono, papel, escopo e suspensão continuam sendo conferidos pelo servidor conforme a [matriz de permissões](../security/access-control.md). Não há regras de negócio ou cálculo de fila no frontend.

Os [comandos de instalação, geração e validação](../../apps/web/README.md) ficam junto do pacote.
