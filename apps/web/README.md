# Frontend — CH/UPE

React + TypeScript + Vite, com as telas Entrar e Criar conta. Usa somente dados sintéticos. Arquitetura e limites: [frontend](../../docs/architecture/frontend.md).

## Executar

Requer Node.js 22.14+ da linha 22, ou a linha 24, e npm. A partir de `apps/web`:

```bash
npm ci
npm run dev
```

Abra `http://127.0.0.1:5173`. O Vite lê o `.env` da raiz e encaminha `/api` ao `WEB_API_PROXY_TARGET` (padrão `http://127.0.0.1:8000`), sem reescrever o caminho. Ajuste o destino se a porta da API for diferente. Não coloque segredos em variáveis `VITE_*`: elas ficam disponíveis no navegador. No desenvolvimento por HTTP, a API precisa usar `COOKIE_SECURE=false` e `COOKIE_DOMAIN` vazio, como no `.env.example`.

Execute banco e API no checkout principal, seguindo o README da raiz. Não suba Compose em worktrees. Não é necessário iniciar a API para conferir lint, testes ou build. As rotas `/paciente` e `/equipe` exigem uma sessão real da API e continuam com layouts vazios. `/paciente` também exibe “Conta criada.” após cadastro bem-sucedido. Não há login simulado na aplicação.

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

## Validar

```bash
npm run lint
npm test
npm run build
```

`lint` inclui ESLint e verificação TypeScript. Vitest cobre HTTP/CSRF/refresh, erros, guardas de rota, login, cadastro e máscaras com respostas sintéticas. O build fica em `dist/` (ignorado pelo Git). `npm run preview` permite inspecionar esses arquivos, sem proxy de API. O [proxy de desenvolvimento](https://vite.dev/config/server-options#server-proxy) não substitui a configuração do Nginx em produção.

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

`vitest-axe` verifica login e todas as etapas do cadastro, incluindo termo expandido. A regra de contraste fica desativada no jsdom, que não calcula a apresentação como um navegador; as razões de contraste são documentadas acima. Há teste que intercepta `Storage.prototype.setItem`, `removeItem` e `clear` durante cadastro, retorno de etapa e envio, abrangendo localStorage e sessionStorage.

Conferência visual realizada no Chrome em **360×640** e **1440×1024**: duas telas e três etapas, termo expandido, foco inicial de erro, teclado, ausência de rolagem horizontal, alvos de toque e tamanho da fonte. Na inspeção do cadastro, o termo foi interceptado com o texto sintético do repositório. Essa inspeção não representa integração com o backend.

O bloqueio inicial de **404** no termo vigente foi resolvido pela atualização da API do checkout principal. Em **24/10/2026**, o ciclo de autenticação foi verificado no Chrome/Playwright em **360×640**, contra essa API real, pelo proxy do Vite, sem mocks:

- Termo vigente: **200**, versão `1.0`; texto completo exibido e mesma versão enviada no cadastro.
- Cadastro pelo formulário: **201**; navegação para `/paciente`, aviso “Conta criada.” e `/me` **200** com papel `PACIENTE`.
- Logout real com o cliente HTTP da aplicação, cookies e `X-CSRF-Token`: **204**; `/me` passou a **401** e reabrir a rota protegida levou a `/entrar`.
- Novo login pelo formulário: **200**; retorno a `/paciente` e `/me` **200**, com o mesmo ID da conta criada.
- Nenhuma escrita em localStorage/sessionStorage durante o cadastro. Cookies access/refresh conferidos como `httpOnly`.

Limite da verificação: `/paciente` ainda é um layout vazio, sem tela de Meus atendimentos nem botão Sair. O logout foi chamado pelo endpoint real no navegador; portanto, o ciclo de sessão passou, mas não há validação de um botão Sair. Foi criada uma conta de desenvolvimento com CPF e CNS gerados pelos utilitários sintéticos existentes. Nenhum Docker Compose foi iniciado no worktree e nenhum serviço do checkout principal foi alterado.
