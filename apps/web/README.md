# Frontend — CH/UPE

React + TypeScript + Vite, com Entrar, Criar conta e Meus atendimentos na área do paciente. Usa somente dados sintéticos. Arquitetura e limites: [frontend](../../docs/architecture/frontend.md).

## Executar

Requer Node.js 22.14+ da linha 22, ou a linha 24, e npm. A partir de `apps/web`:

```bash
npm ci
npm run dev
```

Abra `http://127.0.0.1:5173`. O Vite lê o `.env` da raiz e encaminha `/api` ao `WEB_API_PROXY_TARGET` (padrão `http://127.0.0.1:8000`), sem reescrever o caminho. Ajuste o destino se a porta da API for diferente. Não coloque segredos em variáveis `VITE_*`: elas ficam disponíveis no navegador. No desenvolvimento por HTTP, a API precisa usar `COOKIE_SECURE=false` e `COOKIE_DOMAIN` vazio, como no `.env.example`.

Execute banco e API no checkout principal, seguindo o README da raiz. Não suba Compose em worktrees. Não é necessário iniciar a API para conferir lint, testes ou build. As rotas `/paciente` e `/equipe` exigem uma sessão real da API. `/paciente` entrega Meus atendimentos, navegação e Sair; `/equipe` continua com layout vazio. `/paciente/novo`, `/paciente/solicitacoes/:id` e `/paciente/avisos` são provisórias, apenas com título. Após cadastro bem-sucedido, “Conta criada.” aparece uma vez e desaparece após seis segundos ou ao usar a navegação do cabeçalho. Não há login simulado na aplicação.

Falha de refresh em qualquer consulta limpa a sessão e o cache, cancela consultas pendentes e leva a `/entrar`, guardando a rota de origem em `location.state.origem`. A tela de login usa `rotaAposLogin(location.state)` para voltar a uma origem interna validada; sem ela, vai a `/paciente` ou `/equipe` conforme o papel. O cliente HTTP próprio mantém `credentials: 'same-origin'` e usa os tipos gerados do backend. `ApiError.message` oferece a mensagem amigável por type; formulários podem chamar `aplicarErrosDeValidacao(error, setError, ['campo'])` para os erros 422, exibindo também `errors.root?.server?.message` para erros globais.

## Tipos OpenAPI

O arquivo `src/shared/api/generated/schema.d.ts` é gerado e versionado. Nunca edite à mão. Com o ambiente Python do backend preparado (`uv sync --frozen` em `apps/backend`):

```bash
npm run api:generate
npm run api:generate -- --check
```

O script importa o FastAPI com configuração sintética isolada, exporta `app.openapi()` e gera os tipos sem conectar ao PostgreSQL. Se preferir uma API já em execução:

```bash
npm run api:generate -- http://127.0.0.1:8000/api/v1/openapi.json
```

O build usa o arquivo gerado e não depende de Python, rede ou API em execução. Gere os tipos novamente após mudanças de contrato. Referência da ferramenta: [OpenAPI TypeScript CLI](https://openapi-ts.dev/cli).

**Atualização de autenticação — 24/10/2026:** o contrato deste worktree ainda não inclui `trocar_senha` ou `POST /auth/trocar-senha`. Não foram inventados DTOs nem editados tipos gerados. A detecção em runtime do campo opcional e do `403 /problemas/troca-de-senha-obrigatoria` já encaminha à rota provisória `/trocar-senha`, mantendo a sessão, sem formulário de troca. A regeneração com o novo contrato depende do merge da main; depois dele, execute os dois comandos acima e ajuste os consumidores tipados. O `--check` atual confere apenas o contrato antigo disponível neste worktree.

## Validar

```bash
npm run lint
npm test
npm run build
npm run api:generate -- --check
```

`lint` inclui ESLint e verificação TypeScript. Vitest cobre HTTP/CSRF/refresh, erros, guardas de rota, login, cadastro, máscaras, layout do paciente, lista, resposta à proposta e datas em Recife, com respostas sintéticas. O build fica em `dist/` (ignorado pelo Git). `npm run preview` permite inspecionar esses arquivos, sem proxy de API. O [proxy de desenvolvimento](https://vite.dev/config/server-options#server-proxy) não substitui a configuração do Nginx em produção.

Para os testes existentes do backend, use `scripts/testar.sh` a partir da raiz; cada worktree recebe seu próprio banco de teste.

## Entrar e criar conta

- `/entrar`: CPF ou e-mail, senha com mostrar/ocultar, envio com carregamento, alertas 401/429/rede e link Criar conta. A máscara preserva e-mails digitados com início numérico. CPF é enviado sem pontuação.
- `/criar-conta`: três etapas — Seus dados; Contato; Senha e termo. Os dados ficam no React Hook Form em memória e são descartados ao sair/recarregar. Não há escrita em localStorage ou sessionStorage.
- O termo é buscado em `/termos/vigente`, apresentado completo como texto escapado em painel expansível; a versão vem dessa resposta. Falha de carregamento impede o envio. Versão recusada pelo servidor exige novo carregamento e novo aceite.
- Validação Zod: limites do contrato, CPF com verificadores e rejeição de todos iguais, CNS definitivo/provisório, data não futura e idade até 130 anos completos em Recife, senha de 10–256 caracteres e confirmação igual. E-mail opcional usa o formato aceito pelo servidor. Lembretes são opcionais e ficam desmarcados/desabilitados sem e-mail.
- Erros 422 de etapas anteriores levam à etapa do campo e focam o primeiro erro. O 409 usa a mensagem genérica do backend sem identificar dado duplicado.
- Depois de login/registro, o cache anterior é limpo; a guarda do destino consulta `/me`. Uma falha nessa consulta não reapresenta o cadastro para um segundo POST.
- Não há recuperação de senha: há um `TODO(api)` em `Entrar.tsx` para quando existir endpoint.

## Visual e acessibilidade

Os tokens estão em `src/styles/tokens.css`. As cores vêm dos SVGs fornecidos; eles contêm letras convertidas em curvas, sem identificação confiável da fonte. Usa-se `system-ui, sans-serif`, sem fonte externa. Campos têm fonte de 16 px e altura de 52 px; botões e demais alvos têm pelo menos 44 px. Foco visível, rótulos, ajuda/erro por `aria-describedby`, alertas e navegação por teclado fazem parte dos componentes.

Contrastes calculados pela luminância relativa sRGB de WCAG, razão `(L maior + 0,05) / (L menor + 0,05)`, arredondados a duas casas. Todos passam AA para texto normal (mínimo 4,5:1):

| Texto | Fundo branco `#FFFFFF` | Fundo suave `#E6F1EF` |
| --- | --- | --- |
| Secundário `#4F6168` | **6,48:1** | **5,61:1** |
| Erro `#A12622` | **7,46:1** | **6,46:1** |

`#D5DFE1` é usado em divisores; contornos dos campos usam `#4F6168` para identificação dos controles. No celular, o painel institucional vira um cabeçalho compacto. O link Criar conta foi conferido sem rolagem inicial em **360×640**.

## Cobertura das telas e inspeção no navegador

Os testes das telas usam Testing Library, user-event e MSW (somente em testes). Os documentos de `src/test/fixtures/documentos-sinteticos.json` foram gerados por `apps/backend/tests/sinteticos.py`, incluindo CNS definitivos e provisórios.

`vitest-axe` verifica login, todas as etapas do cadastro (incluindo termo expandido), Meus atendimentos e diálogo da proposta. A regra de contraste fica desativada no jsdom, que não calcula a apresentação como um navegador; as razões de contraste são documentadas acima. Há teste que intercepta `Storage.prototype.setItem`, `removeItem` e `clear` durante cadastro, retorno de etapa e envio, abrangendo localStorage e sessionStorage.

Conferência visual realizada no Chrome em **360×640** e **1440×1024**: duas telas e três etapas, termo expandido, foco inicial de erro, teclado, ausência de rolagem horizontal, alvos de toque e tamanho da fonte. Na inspeção do cadastro, o termo foi interceptado com o texto sintético do repositório. Essa inspeção não representa integração com o backend.

O bloqueio inicial de **404** no termo vigente foi resolvido pela atualização da API do checkout principal. Em **24/10/2026**, o ciclo de autenticação foi verificado no Chrome/Playwright em **360×640**, contra essa API real, pelo proxy do Vite, sem mocks:

- Termo vigente: **200**, versão `1.0`; texto completo exibido e mesma versão enviada no cadastro.
- Cadastro pelo formulário: **201**; navegação para `/paciente`, aviso “Conta criada.” e `/me` **200** com papel `PACIENTE`.
- Logout real com o cliente HTTP da aplicação, cookies e `X-CSRF-Token`: **204**; `/me` passou a **401** e reabrir a rota protegida levou a `/entrar`.
- Novo login pelo formulário: **200**; retorno a `/paciente` e `/me` **200**, com o mesmo ID da conta criada.
- Nenhuma escrita em localStorage/sessionStorage durante o cadastro. Cookies access/refresh conferidos como `httpOnly`.

Limite dessa verificação anterior: naquela versão, `/paciente` ainda era um layout vazio, sem Meus atendimentos nem botão Sair. O logout foi chamado pelo endpoint real no navegador; esse registro confirma o ciclo de sessão daquela versão, não o botão Sair implementado depois. Foi criada uma conta de desenvolvimento com CPF e CNS gerados pelos utilitários sintéticos existentes. Nenhum Docker Compose foi iniciado no worktree e nenhum serviço do checkout principal foi alterado.

## Entrega de Meus atendimentos (24/10/2026)

A [arquitetura da tela](../../docs/architecture/frontend.md#meus-atendimentos-e-proposta-de-vaga) descreve a paginação, a busca complementar com parada antecipada, atualização de cache, resposta à proposta e acessibilidade. O layout do paciente inclui navegação, contador de avisos e saída, inclusive limpeza local quando o logout falha. As rotas provisórias não antecipam formulários, detalhe ou lista de avisos.

A inspeção visual no Chrome usou **360×640**, **360×800** e **1440×1024**, com dados sintéticos interceptados. Foram conferidos ausência de rolagem horizontal, alvos visíveis de pelo menos 44 px, menu por teclado e diálogo com foco inicial, contenção nos dois sentidos, Esc e retorno ao acionador. Capturas e relatório local: `/tmp/central-upe-paciente/visual-360.png`, `visual-1440.png`, `menu-360.png`, `dialogo-360.png`, `dialogo-1440.png`, `visual-360x640.png` e `visual.json`. Essa inspeção não comprova integração com o backend.

Os testes de paciente incluem saída com sucesso e falha, cancelamento de consultas e limpeza de cache, contador, abas, paginação, vazio, repetição após erro, busca de proposta fora da página, parada antecipada, prazo em Recife, confirmação e recusa com CSRF, erro de proposta expirada, ADR-007, axe, foco e ausência de escrita em storage. O diálogo nativo é substituído por uma implementação mínima de `showModal`/`close` somente no jsdom; o comportamento no Chrome também foi conferido. Na verificação final desta entrega, `npm run lint`, `npm test` (**170 testes**, 9 arquivos), `npm run build` e `npm run api:generate -- --check` passaram. O build emitiu dois avisos de comentários de otimização na dependência Zod, sem falhar. O axe também passou na tela e no diálogo no Chrome, com a regra de contraste ativa. Foi conferido no navegador que “Conta criada.” desaparece após seis segundos e não reaparece ao recarregar.

**E2E real desta entrega: pendente.** O roteiro está preparado para criar um paciente sintético, usar o atendente do seed pela API da equipe para classificar o pedido, aguardar a proposta do Worker e confirmar pelo botão da interface. A execução aguarda a senha de desenvolvimento do seed; ainda não há comprovação de proposta criada pelo Worker nem de confirmação ou recusa ponta a ponta nesta entrega.

## Correções de sessão B1/B2 — 24/10/2026

O HTTP associa respostas à época de autenticação e serializa escritas de cookies de login, registro, logout e refresh. Isso impede que `Set-Cookie` antigo sobrescreva um login novo. O logout também verifica a época antes e depois de cancelar consultas, protegendo estado e navegação de sessões novas, inclusive com troca obrigatória. A guarda mantém a árvore montada durante revalidação de `/me`; uma resposta concluída com `trocar_senha=true` ou um `403` específico encaminha à rota provisória sem tratar o bloqueio como logout.

As regressões usam dados sintéticos e cobrem login com senha temporária, `/me` com troca obrigatória, transição de `false` para `true`, `403` sem limpeza/refresh, `422` com erro em `senha_atual`, logout atrasado com `204`, ordem de aplicação de cookies em logout/refresh antes de login/registro e diálogo/confirmação preservados durante revalidação. A simulação de cookies verifica a ordem do transporte; não representa uma nova execução E2E com o backend atualizado.

Validação desta rodada: `npm test` passou com **191 testes em 9 arquivos**; `npm run lint`, `npm run build` e `npm run api:generate -- --check` também passaram. O build mantém os dois avisos de comentários de otimização do Zod. O check de geração usa o contrato antigo local; a regeneração com a atualização administrativa continua dependente do merge da main. As revisões de código e segurança terminaram sem achados pendentes.

## Correções finais I1/I2 e espera de autenticação — 24/10/2026

A tela corrige a página atual quando uma nova resposta reduz o total, buscando a última página válida antes de exibir a lista. Total zero retorna à página inicial. O layout diferencia fechar o menu (foco no botão Menu) de navegar (foco no conteúdo principal após a mudança de rota), inclusive com Enter e Esc.

Cada operação coordenada de autenticação tem limite de **15 segundos**, centralizado em `limiteOperacaoAuthMs`. O limite aborta o fetch anterior antes de liberar o próximo envio; sinais e épocas impedem efeitos de respostas tardias. Abort de autenticação ainda enfileirada termina imediatamente, impede seu envio e preserva o funcionamento da fila. Timers e listeners são removidos ao finalizar. B1/B2 e o fluxo provisório de troca obrigatória permanecem cobertos.

Vitest passou com **208 testes em 9 arquivos**, incluindo redução do total de 6 para 5, total zero, resposta tardia de página antiga, foco após navegação, logout/refresh travados antes de login/registro, cancelamento enfileirado, corpo de login travado e respostas/rejeições tardias. No Chrome com API interceptada, a paginação corrigiu os offsets, Enter focou `main#conteudo-paciente` e Esc restaurou Menu. Logout e refresh travados atingiram o limite real de 15 segundos, com `net::ERR_ABORTED`; login prosseguiu e uma tentativa posterior de resposta antiga com `Set-Cookie` preservou a sessão e os cookies novos, inclusive com `trocar_senha=true`. O axe passou na rota provisória após a navegação.

Essas reproduções usam somente dados sintéticos interceptados. **E2E real: pendente e não executado nesta rodada.** O OpenAPI local continua antigo; nenhum tipo gerado foi editado manualmente.
