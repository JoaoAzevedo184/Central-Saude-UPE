# Base web — CH/UPE

Base técnica React + TypeScript + Vite, sem telas de negócio. Usa somente dados sintéticos. Arquitetura e limites: [frontend](../../docs/architecture/frontend.md).

## Executar

Requer Node.js 22.14+ da linha 22, ou a linha 24, e npm. A partir de `apps/web`:

```bash
npm ci
npm run dev
```

Abra `http://127.0.0.1:5173`. O Vite lê o `.env` da raiz e encaminha `/api` ao `WEB_API_PROXY_TARGET` (padrão `http://127.0.0.1:8000`), sem reescrever o caminho. Ajuste o destino se a porta da API for diferente. Não coloque segredos em variáveis `VITE_*`: elas ficam disponíveis no navegador. No desenvolvimento por HTTP, a API precisa usar `COOKIE_SECURE=false` e `COOKIE_DOMAIN` vazio, como no `.env.example`.

Execute banco e API no checkout principal, seguindo o README da raiz. Não suba Compose em worktrees. Não é necessário iniciar a API para conferir lint, testes ou build. As rotas `/paciente` e `/equipe` exigem uma sessão real da API; não há login simulado ou formulário de login nesta base.

Falha de refresh em qualquer consulta limpa a sessão e o cache, cancela consultas pendentes e leva a `/entrar` (ainda sem formulário), guardando a rota de origem em `location.state.origem`. A futura tela de login usa `rotaAposLogin(location.state)` para voltar. O cliente HTTP próprio mantém `credentials: 'same-origin'` e usa os tipos gerados do backend. `ApiError.message` oferece a mensagem amigável por type; formulários podem chamar `aplicarErrosDeValidacao(error, setError, ['campo'])` para os erros 422, exibindo também `errors.root?.server?.message` para erros globais.

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

`lint` inclui ESLint e verificação TypeScript. Vitest cobre HTTP/CSRF/refresh, erros e guardas de rota com respostas sintéticas. O build fica em `dist/` (ignorado pelo Git). `npm run preview` permite inspecionar esses arquivos, sem proxy de API. O [proxy de desenvolvimento](https://vite.dev/config/server-options#server-proxy) não substitui a configuração do Nginx em produção.

Para os testes existentes do backend, use `scripts/testar.sh` a partir da raiz; cada worktree recebe seu próprio banco de teste.
