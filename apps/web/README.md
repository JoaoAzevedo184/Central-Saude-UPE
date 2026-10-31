# Frontend — CH/UPE

React + TypeScript + Vite, com Entrar, Criar conta, Trocar senha, Meus atendimentos, Detalhe do pedido e Novo pedido em três etapas na área do paciente. Usa somente dados sintéticos. Arquitetura e limites: [frontend](../../docs/architecture/frontend.md).

## Executar

Requer Node.js 22.14+ da linha 22, ou a linha 24, e npm. A partir de `apps/web`:

```bash
npm ci
npm run dev
```

Abra `http://127.0.0.1:5173`. O Vite lê o `.env` da raiz e encaminha `/api` ao `WEB_API_PROXY_TARGET` (padrão `http://127.0.0.1:8000`), sem reescrever o caminho. Ajuste o destino se a porta da API for diferente. Não coloque segredos em variáveis `VITE_*`: elas ficam disponíveis no navegador. No desenvolvimento por HTTP, a API precisa usar `COOKIE_SECURE=false` e `COOKIE_DOMAIN` vazio, como no `.env.example`.

Execute banco e API no checkout principal, seguindo o README da raiz. Não suba Compose em worktrees. Não é necessário iniciar a API para conferir lint, testes ou build. As rotas `/paciente` e `/equipe` exigem uma sessão real da API. `/paciente` entrega Meus atendimentos, navegação e Sair; `/equipe` redireciona para `/equipe/fila`, com navegação da equipe, papel e Sair. `/paciente/novo` permite criar um pedido em três etapas. `/paciente/solicitacoes/:id` mostra status, proposta ou consulta, andamento, informações fornecidas e cancelamento. `/paciente/avisos` lista avisos e permite marcá-los como lidos. Após cadastro bem-sucedido, “Conta criada.” aparece uma vez e desaparece após seis segundos ou ao usar a navegação do cabeçalho. Não há login simulado na aplicação.

Falha de refresh em qualquer consulta limpa a sessão e o cache, cancela consultas pendentes e leva a `/entrar`, guardando a rota de origem em `location.state.origem`. A tela de login usa `rotaAposLogin(location.state)` para voltar a uma origem interna validada; sem ela, vai a `/paciente` ou `/equipe/fila` conforme o papel. O cliente HTTP próprio mantém `credentials: 'same-origin'` e usa os tipos gerados do backend. `ApiError.message` oferece a mensagem amigável por type; formulários podem chamar `aplicarErrosDeValidacao(error, setError, ['campo'])` para os erros 422, exibindo também `errors.root?.server?.message` para erros globais.

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

**Atualização de autenticação — 24/10/2026:** o contrato da Parte 1 (`be32204`) inclui `trocar_senha` e `POST /auth/trocar-senha`; os tipos foram regenerados pela ferramenta. Login usa `LoginSaida`, `/me` usa `EuSaida`, ambos com `trocar_senha?: true | null`. Ausência ou `null` seguem o fluxo habitual; `true` e o `403 /problemas/troca-de-senha-obrigatoria` encaminham à rota `/trocar-senha`, mantendo a sessão. O formulário obrigatório foi implementado em 26/10/2026, conforme a seção abaixo. O payload `TrocaSenhaEntrada` e a associação do erro 422 a `senha_atual` estão cobertos nos testes, sem refresh. A geração inclui `/admin/*` e remove as rotas administrativas antigas; não há telas administrativas nesta entrega. A API `GET /api/v1/equipe/indicadores` já existe no backend; a tela de indicadores e seu consumo ficam para a tarefa específica da tela de gestor/equipe.

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

Os testes de paciente incluem saída com sucesso e falha, cancelamento de consultas e limpeza de cache, contador, abas, paginação, vazio, repetição após erro, busca de proposta fora da página, parada antecipada, prazo em Recife, confirmação e recusa com CSRF, erro de proposta expirada, ADR-007, axe, foco e ausência de escrita em storage. O diálogo nativo é substituído por uma implementação mínima de `showModal`/`close` somente no jsdom; o comportamento no Chrome também foi conferido. Na verificação final desta entrega, `npm run lint`, `npm test`, `npm run build` e `npm run api:generate -- --check` passaram. O build emitiu dois avisos de comentários de otimização na dependência Zod, sem falhar. O axe também passou na tela e no diálogo no Chrome, com a regra de contraste ativa. Foi conferido no navegador que “Conta criada.” desaparece após seis segundos e não reaparece ao recarregar.

**E2E real desta entrega: pendente.** O roteiro está preparado para criar um paciente sintético, usar o atendente do seed pela API da equipe para classificar o pedido, aguardar a proposta do Worker e confirmar pelo botão da interface. A execução aguarda a senha de desenvolvimento do seed; ainda não há comprovação de proposta criada pelo Worker nem de confirmação ou recusa ponta a ponta nesta entrega.

## Correções de sessão B1/B2 — 24/10/2026

O HTTP associa respostas à época de autenticação e serializa escritas de cookies de login, registro, logout e refresh. Isso impede que `Set-Cookie` antigo sobrescreva um login novo. O logout também verifica a época antes e depois de cancelar consultas, protegendo estado e navegação de sessões novas, inclusive com troca obrigatória. A guarda mantém a árvore montada durante revalidação de `/me`; uma resposta concluída com `trocar_senha=true` ou um `403` específico encaminha à rota provisória sem tratar o bloqueio como logout.

As regressões usam dados sintéticos e cobrem login com senha temporária, `/me` com troca obrigatória, transição de `false` para `true`, `403` sem limpeza/refresh, `422` com erro em `senha_atual`, logout atrasado com `204`, ordem de aplicação de cookies em logout/refresh antes de login/registro e diálogo/confirmação preservados durante revalidação. A simulação de cookies verifica a ordem do transporte; não representa uma nova execução E2E com o backend atualizado.

Validação daquela rodada: `npm test` passou; `npm run lint`, `npm run build` e `npm run api:generate -- --check` também passaram. O build manteve os dois avisos de comentários de otimização do Zod. Naquela etapa, o check de geração usava o contrato antigo local e a regeneração dependia da atualização administrativa da main. As revisões de código e segurança terminaram sem achados pendentes.

## Correções finais I1/I2 e espera de autenticação — 24/10/2026

A tela corrige a página atual quando uma nova resposta reduz o total, buscando a última página válida antes de exibir a lista. Total zero retorna à página inicial. O layout diferencia fechar o menu (foco no botão Menu) de navegar (foco no conteúdo principal após a mudança de rota), inclusive com Enter e Esc.

Cada operação coordenada de autenticação tem limite de **15 segundos**, centralizado em `limiteOperacaoAuthMs`. O limite aborta o fetch anterior antes de liberar o próximo envio; sinais e épocas impedem efeitos de respostas tardias. Abort de autenticação ainda enfileirada termina imediatamente, impede seu envio e preserva o funcionamento da fila. Timers e listeners são removidos ao finalizar. B1/B2 e o fluxo provisório de troca obrigatória permanecem cobertos.

Vitest passou, incluindo redução do total de 6 para 5, total zero, resposta tardia de página antiga, foco após navegação, logout/refresh travados antes de login/registro, cancelamento enfileirado, corpo de login travado e respostas/rejeições tardias. No Chrome com API interceptada, a paginação corrigiu os offsets, Enter focou `main#conteudo-paciente` e Esc restaurou Menu. Logout e refresh travados atingiram o limite real de 15 segundos, com `net::ERR_ABORTED`; login prosseguiu e uma tentativa posterior de resposta antiga com `Set-Cookie` preservou a sessão e os cookies novos, inclusive com `trocar_senha=true`. O axe passou na rota provisória após a navegação.

Essas reproduções usam somente dados sintéticos interceptados. **E2E real: pendente e não executado naquela rodada.** Naquele momento o OpenAPI local ainda era antigo; a atualização de contrato descrita acima veio depois, sem edição manual dos tipos gerados.

## Validação do contrato da Parte 1 — 24/10/2026

Após a regeneração, `npm test` passou; lint, build e check de geração também passaram. A cobertura inclui login e `/me` com troca obrigatória, campo ausente ou `null`, revalidação descobrindo o bloqueio, 403 sem refresh/limpeza de sessão e 422 associado a `senha_atual` com CSRF. Os testes de B1/B2, I1/I2 e timeout de autenticação continuam passando. O catálogo de mensagens inclui os três Problem Details novos. **E2E real: PENDENTE.**

## Novo pedido — 25/10/2026

A [arquitetura do fluxo UC-002](../../docs/architecture/frontend.md#nova-solicitação-uc-002--25102026) descreve o contrato e os estados de `/paciente/novo`. As etapas são Atendimento (lista incremental e elegibilidade), Informações (origem, turno e perguntas opcionais) e Revisar (resumo e envio). A unidade/especialidade vem da fila escolhida. Só a etapa final envia `POST /solicitacoes` com CSRF. Sucesso 201 retorna a Meus atendimentos com mensagem única, consumida do Router mesmo com o layout montado.

Não há persistência do formulário. Ausência de resposta, false e zero são distintos; códigos das opções são literais. A tela trata 422 por campo quando possível, ambos os conflitos 409 reais e os 403 por type. Falha de rede no POST orienta conferir a lista antes de tentar de novo, sem retry automático. Detalhes de fila atrasados e respostas de uma sessão antiga são descartados. Consentimento novo, anexos, busca, detalhe completo e seleção independente de unidade/profissional continuam fora do escopo.

Conferência real: login, três etapas, POST 201 pela interface, mensagem, cartão e consulta oficial de confirmação; sem mocks/interceptações. Chromium/axe passou nas etapas, erro e sucesso. Capturas e relatório estão em `/tmp/nova-solicitacao-e2e/`, fora do repositório. Nenhum Docker Compose foi executado no worktree.

Validação final da tela: `npm run lint`, `npm test`, `npm run build`, `npm run api:generate -- --check` e `git diff --check` passaram. O build mantém os dois avisos anteriores de comentários de otimização do Zod. Evidência final do navegador: `/tmp/nova-solicitacao-e2e/final/relatorio.json`, com zero violações axe nos cinco estados, zero escritas em storage, POST 201 com CSRF e conferência oficial do pedido. Alvos de seleção de 44 px, controles/botões de 52 px e nenhum scroll horizontal nas três resoluções.

## Trocar senha — 26/10/2026

`/trocar-senha` atende os quatro papéis, somente quando há troca obrigatória. Usa layout mínimo próprio e logout compartilhado com o paciente. Senhas ficam no formulário em memória, sem storage, URL, logs ou cache de queries/mutations. A nova senha exige 10–256 code points, sem trim, diferença da atual e confirmação igual. O mínimo 10 está também declarado no OpenAPI atualizado. Os 422 de `senha_atual` e `senha_nova` usam o adaptador compartilhado para localização/foco, com mensagens locais por campo e código. Não há exibição de `msg`/`detail` brutos; códigos ou campos não reconhecidos geram erro global seguro.

A política de refresh exclui somente os pares POST + pathname exatos de login, registro, refresh e logout; query não muda a classificação. Essas quatro operações usam a fila existente de cookies. Trocar senha fica fora dela: pode renovar em 401 e repetir uma única vez com CSRF relido, sem deadlock.

Sucesso 204 não navega imediatamente: cancela `/me` antigo, espera nova consulta e cache atualizado, confere identidade e flag, libera a trava pela época esperada e navega. Se a verificação falhar, informa que a senha mudou e oferece apenas tentar `/me` novamente. Refetch com erro e sessão conhecida preserva o formulário.

Validação: lint, testes, build e check de tipos com exportação do OpenAPI do backend atualizado passaram. O comando sem URL ainda depende de `.venv` do backend, ausente neste worktree. Para conferir contra a API real existente: `npm run api:generate -- --check http://127.0.0.1:8000/api/v1/openapi.json`. Build mantém os dois avisos conhecidos do Zod.

E2E GESTOR aprovado com backend real, comando oficial para senha temporária, POST 204, `/me` 200 e `/equipe`; nenhuma credencial foi registrada. Axe e teclado passaram em 360×640, 360×800 e 1440×1024. Evidências sem senhas em `/tmp/trocar-senha-evidencias/`. E2E PACIENTE pendente por ausência de conta temporária utilizável; sem seed nem manipulação manual do banco. Warning MSW de `/filas` em Meus atendimentos permanece separado.

## Detalhe do pedido — 29/10/2026

`/paciente/solicitacoes/:id` usa `GET /solicitacoes/{id}`. O topo reaproveita `SeloStatus`; o detalhe mostra os seis estados, com carregamento, erro com nova tentativa e 404 neutro. Consulta confirmada tem data por extenso em Recife, unidade, endereço (ou “Confirme o endereço com a unidade.”), profissional e orientações de chegada/documentos.

A `LinhaDoTempo` fica em `shared/ui` e recebe apenas data e texto. A página usa textos locais por tipo, ordena por data preservando a ordem entre eventos do mesmo dia e omite CLASSIFICADA/RECLASSIFICADA, motivos e campos extras. Datas civis já vêm convertidas pelo backend; não são reinterpretadas como UTC. Respostas vazias são omitidas; false e zero aparecem como “Não” e “0”.

`PropostaVaga`, `useProposta` e os componentes de `RespostaProposta` são compartilhados com Meus atendimentos. Os testes existentes de Meus atendimentos permanecem sem alteração. O cancelamento tem cinco motivos fechados e envia somente `motivo_codigo`, via HTTP compartilhado com CSRF. Está disponível em EM_ANALISE, NA_FILA, EM_PROPOSTA e AGENDADA; com agendamento ativo, somente antes do início. A interface atualiza esse limite também por temporizador. O servidor decide em definitivo, e 409 informa mudança e recarrega os dados. Sucesso atualiza detalhe e invalida listas, propostas e contador. Cancelamento de leituras e verificação da época protegem a atualização de cache contra respostas antigas.

O diálogo compartilhado inclui select, input e textarea na contenção de foco, além dos botões e links. O cancelamento começa no seletor de motivo, fecha com Esc e restaura o foco ao acionador. Não há campo livre nem persistência em storage. A política existente de refresh permanece: não há retry por falha de rede, conflito ou validação; 401 pode renovar a sessão e repetir uma vez.

Validação automatizada: lint, testes, build e `npm run api:generate -- --check` passaram. O ambiente Python local foi preparado com `uv sync --frozen`, sem conectar ao banco. O build mantém os dois avisos conhecidos do Zod. A conferência visual com API sintética interceptada cobriu os seis status e o diálogo em 360×640, 360×800 e 1440×1024: 21 capturas, zero violações axe com contraste ativo, sem overflow horizontal e alvos de pelo menos 44 px. Teclado, contenção nos dois sentidos, Esc e restauração passaram. Evidências locais: `/tmp/detalhe-pedido-evidencias/visual.json` e capturas na mesma pasta. Essa inspeção visual não representa E2E real.

O E2E com API real, sem mocks/interceptações, criou uma conta sintética por `POST /auth/registro` (201), com documentos gerados pelos utilitários oficiais e senha aleatória mantida fora do repositório e dos relatórios. Preparou dois pedidos pela API (201) e cancelou ambos pela interface (200), verificando CSRF, corpo somente com `motivo_codigo`, GET oficial com CANCELADA, evento de cancelamento e cartão no Histórico. A segunda execução ocorreu para investigar uma falha do seletor do roteiro no Histórico (o ícone faz parte do texto do selo); a conferência corrigida reutilizou os pedidos já cancelados, sem novas escritas. EM_ANALISE, diálogo e CANCELADA passaram no axe em 360×800 e desktop, sem escritas em storage. Relatório: `/tmp/detalhe-pedido-evidencias/real.json`; capturas `real-*.png`. Nenhum seed foi executado e não houve manipulação direta do banco.

**E2E dos pedidos do seed: pendente de credencial dos pacientes de apresentação.** Não há senha de seed no `.env` principal nem nas variáveis do processo. Os outros quatro estados foram validados por MSW e pela conferência visual interceptada; isso não substitui a inspeção desses pedidos na API real.

### Correções da revisão do detalhe

O relógio sincroniza novos horários antes da pintura e impede ações com uma leitura anterior, inclusive se o GET terminar depois do início. Timers próprios acompanham início e expiração e reconferem disparos antecipados. No detalhe, o diálogo da proposta fecha com mensagem neutra se a leitura atual mudar o status, agendamento, data ou prazo, ou se o prazo terminar com a tela aberta. Durante um POST já em andamento, o resultado da escrita continua sendo tratado pelo fluxo existente. Meus atendimentos continua usando o comportamento compartilhado sem essa referência de detalhe; seus testes não foram editados.

As regressões cobrem GET atrasado sem inserir o botão no DOM, início alterado, passagem do relógio pelo início e pela expiração, mudanças da proposta, 404 recebido pelo POST e logout pelo botão Sair com cancelamento pendente, seguido de novo login e resposta antiga. O teste do GET 404 durante envio foi mantido com nome explícito. Os testes verificam que a resposta antiga não altera a tela nem o cache da sessão nova.

Durante a sincronização provisória do relógio, um diálogo de cancelamento já aberto preserva o motivo e seu acionador. Se os novos horários continuarem futuros, ele permanece aberto e Esc restaura o foco; há testes para mudança de início e de prazo.


## Avisos — 29/10/2026

`/paciente/avisos` lista avisos lidos e não lidos, com dez por página, deduplicação por ID e “Carregar mais”. Título e corpo são exibidos como texto escapado da API, sem filtro de palavras. Fallbacks preenchem somente campos ausentes/vazios, com opção genérica para tipo desconhecido. Não lidos mostram “Novo” e texto em negrito; lidos não têm rótulo.

“Ver pedido” é um link real. No clique normal ou Enter, tenta marcar o aviso antes de navegar e mostra “Abrindo…” com `aria-busy`, ignorando repetição. Falha do POST ou espera de 3 segundos também levam ao pedido, sem marcar localmente nem exibir alerta na lista. Avisos já lidos abrem diretamente; modificadores preservam a abertura nativa em outra aba/janela.

“Marcar todos como lidos” aparece somente quando a contagem compartilhada é maior que zero, inclusive para avisos sem pedido ou fora das páginas carregadas. Durante o POST, fica desabilitado com `aria-busy`; no sucesso, o foco vai para a mensagem de confirmação. Lista e contador são revalidados sem atualização otimista. CSRF, refresh em 401, abort e época da sessão seguem o cliente compartilhado, sem persistência em storage ou retry automático de falha de rede.

Os comandos de desenvolvimento e verificação estão em [Executar](#executar) e [Validar](#validar). O fluxo de cache e navegação está descrito na [arquitetura da tela](../../docs/architecture/frontend.md#avisos-rf-019--29102026).

## Equipe — layout e Fila

`/equipe` leva a `/equipe/fila` para atendente, gestor e administrador. A raiz e o login usam o mesmo destino por papel; acessar a área de outro papel redireciona para a própria área. A troca obrigatória de senha tem prioridade. O menu lateral do desktop contém Fila e, no rodapé, o papel e Sair. Em telas estreitas, Menu abre e fecha a navegação com teclado e Esc. Há link Pular para o conteúdo e indicação da página atual. Indicadores permanece fora do menu enquanto não houver tela.

A Fila carrega as filas do escopo em páginas de até cem. Uma fila é exibida como texto, várias usam seletor e nenhuma orienta procurar o gestor. Inativas aparecem depois das ativas, com “(inativa)”. O filtro mostra as contagens por status; Todos apresenta a soma. Prioridade é a ordenação inicial; Ordem de chegada preserva a ordem recebida da API e explica que as posições continuam seguindo a prioridade.

São vinte pedidos por página, com posição somente em NA_FILA, risco com texto e três cores, nome abreviado, CPF mascarado, entrada na fila, status e última mudança. Nome e CPF são exibidos como recebidos. Sem entrada, aparece “Ainda não entrou na fila”; sem classificação, um selo neutro. Eventos ausentes ou desconhecidos aparecem como traço. A pontuação não aparece. No desktop, a tabela usa caption e cabeçalhos com scope; abaixo de 900 px, cartões apresentam os mesmos dados.

Fila, ordenação, status e página ficam na URL, permitindo restaurar o estado com Voltar. Só identificadores e filtros conhecidos entram nos links. Atualizar e voltar à aba revalidam pedidos e contagens, sem polling; a hora da última busca aparece junto do botão. Há estados de carregamento, erro com nova tentativa, acesso indisponível e vazio do filtro, além do anúncio acessível da quantidade e página.

O nome abre `/equipe/solicitacoes/:id`, destino provisório com apenas o título e “‹ Voltar para a fila”, preservando os filtros. Detalhe e classificação ficam para a próxima tela. As leituras e o logout usam o cliente HTTP e a proteção de sessão existentes, sem dados pessoais em storage, console ou URL. O contrato e o fluxo estão descritos na [arquitetura da equipe](../../docs/architecture/frontend.md#layout-da-equipe-e-fila-rf-031032).
