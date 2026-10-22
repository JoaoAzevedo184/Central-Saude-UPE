# Contexto para construir o frontend: Central Inteligente de Teleagendamento (CH/UPE)

> Cole este documento no começo da conversa com o ChatGPT (ou deixe-o na raiz do repositório para o Codex). Ele descreve o projeto, a API que já existe e as regras que as telas precisam respeitar. **A fonte de verdade da API é o OpenAPI do backend, em `http://localhost:8000/api/v1/openapi.json`** (Swagger em `/api/v1/docs`). Se este resumo e o OpenAPI divergirem, vale o OpenAPI, com uma exceção: os erros saem em Problem Details (`application/problem+json`), mesmo onde o OpenAPI ainda anuncia o formato padrão do FastAPI.

## 1. O projeto

- Protótipo acadêmico (Extensão III, Sistemas de Informação, UNINASSAU Olinda) de teleagendamento para pacientes do SUS do Complexo Hospitalar da UPE (CISAM, HUOC, PROCAPE).
- O desafio foi proposto pela diretora do Complexo, que validou as regras com a equipe em 15/10/2026.
- MVP em novembro de 2026. **Somente dados sintéticos**, nunca dados reais de pacientes.
- **Público do paciente:** pessoas com pouca familiaridade com tecnologia, muitas usando celular simples. As telas precisam de linguagem simples, botões grandes, poucos passos e boa leitura em tela pequena.
- **Público da equipe:** atendentes (operam as filas), gestores (acompanham) e administradores. Usam computador.
- **Protótipo no Figma:** https://www.figma.com/design/77RlPMwTFvClwHCAUcb71J/Projeto-extensao (11 telas, 01 a 11).

## 2. Stack do frontend (proposta no ADR-001; confirmar com o grupo)

- React + TypeScript + Vite, em `apps/web/` no monorepo.
- React Router para as rotas.
- TanStack Query para chamadas e cache.
- React Hook Form + Zod para formulários.
- Tipos da API gerados do OpenAPI (`npm run api:generate` em `apps/web`; o contrato também fica salvo em `docs/architecture/openapi.json`). O cliente HTTP é próprio (`src/shared/api/http.ts`), tipado a partir desses tipos.
- **Mobile-first**, responsivo. Acessibilidade WCAG AA: contraste, foco visível, rótulos em todo campo e navegação por teclado.

## 3. Como o frontend fala com a API

- **Base:** `/api/v1`. Em produção, o nginx serve o frontend e a API **no mesmo endereço**. Em desenvolvimento, use o proxy do Vite (`/api` → `http://localhost:8000`) para que tudo fique na mesma origem. Assim os cookies funcionam sem CORS.
- **Sessão em cookies `httpOnly`:**
  - o frontend **nunca** vê nem guarda tokens; não use `localStorage` para sessão;
  - toda chamada envia os cookies (`credentials: 'same-origin'` basta, porque frontend e API ficam no mesmo endereço).
- **CSRF:**
  - depois do login existe um cookie legível `csrf_token`;
  - em toda requisição POST, PUT, PATCH e DELETE, **menos** `/auth/registro` e `/auth/login`, envie o header `X-CSRF-Token` com o valor desse cookie;
  - sem ele, a API responde 403.
- **Sessão expirada:**
  - se uma chamada responder 401, faça **uma** chamada a `POST /auth/refresh` (com CSRF) e repita a original;
  - se o refresh falhar (qualquer status HTTP ou falha de rede), limpe a sessão e o cache no cliente, cancele as consultas em andamento e mande o usuário para `/entrar`, guardando a rota de origem no estado da navegação para voltar após o login;
  - nunca entre em loop;
  - se duas chamadas derem 401 ao mesmo tempo, faça um refresh só e reaproveite.
- **Erros** vêm em Problem Details (RFC 9457): `{ type, title, status, detail }`.
  - Mostre mensagens amigáveis a partir do `type`. Exemplos: `/problemas/credenciais-invalidas`, `/problemas/muitas-tentativas`, `/problemas/nao-elegivel`, `/problemas/solicitacao-duplicada`, `/problemas/proposta-expirada`, `/problemas/transicao-invalida`, `/problemas/sem-consentimento`, `/problemas/csrf-invalido`.
  - 422 traz os erros de validação por campo.
- **Datas:** a API manda ISO 8601 com fuso. Exiba sempre no fuso `America/Recife`, formato brasileiro (`21/10/2026 às 08:00`).

## 4. Rotas da API (resumo; confirme nomes e campos no OpenAPI)

**Autenticação**
- `POST /auth/registro`: cadastro do paciente (nome, CPF, CNS, data de nascimento, sexo, município, telefone, e-mail opcional, senha, aceite do termo e aceite opcional do lembrete por e-mail). Responde 201 e já inicia a sessão.
- `POST /auth/login`: `identificador` (CPF para paciente, e-mail para a equipe) e `senha`. Devolve o papel e a validade.
- `POST /auth/refresh` e `POST /auth/logout`.
- `GET /me`: quem está logado (papel e dados básicos).

**Paciente**
- `GET /filas`: filas ativas, com descrição para o paciente, `elegivel` e `motivo_inelegivel`.
- `GET /filas/{id}`: critérios que o paciente responde.
- `POST /solicitacoes`: cria o pedido (fila, turno preferido, origem do encaminhamento e respostas).
- `GET /solicitacoes?situacao=abertas|encerradas`: "Meus atendimentos" e a aba "Histórico".
- `GET /solicitacoes/{id}`: status, linha do tempo e o agendamento ativo (proposta com prazo, ou consulta confirmada com data, hora, unidade, endereço e profissional).
- `POST /solicitacoes/{id}/cancelar`: com `motivo_codigo`, escolhido numa lista (NAO_PRECISO_MAIS, CONSEGUI_EM_OUTRO_LUGAR, DIFICULDADE_DE_DESLOCAMENTO, CONFLITO_DE_HORARIO, OUTRO). **Não há campo de texto livre.**
- `POST /agendamentos/{id}/confirmar` e `POST /agendamentos/{id}/recusar`.
- `GET /avisos`, `GET /avisos/contagem` (sino do menu), `POST /avisos/{id}/lido` e `POST /avisos/lidos`.

**Equipe** (cada atendente só vê as filas atribuídas a ele)
- `GET /equipe/filas`: filas do escopo, com contagens.
- `GET /equipe/filas/{id}/solicitacoes?status=&ordenacao=prioridade|chegada`: o **painel da fila**, com posição, risco, nota, chegada e última mudança.
- `GET /equipe/solicitacoes/{id}`: detalhe com respostas e histórico completo.
- `POST /equipe/solicitacoes/{id}/classificar`: risco (VERMELHO, AMARELO ou VERDE) e motivo.
- `PUT /equipe/solicitacoes/{id}/respostas`: critérios da regulação.
- `GET /equipe/filas/{id}/agendamentos?data=AAAA-MM-DD`: agenda do dia.
- `POST /equipe/agendamentos/{id}/presenca`: `compareceu: true|false`.
- `GET /equipe/filas/{id}/vagas?de=&ate=`: situação das vagas, inclusive "livre sem proposta".

**Administração:** `POST /usuarios/{id}/suspender` e `/reativar`. Vão migrar para `/admin/...`.

## 5. Telas

### Paciente
1. **Entrar e criar conta:** login por CPF e senha; cadastro com máscara de CPF, CNS e telefone, aceite do termo (obrigatório) e do lembrete por e-mail (opcional).
2. **Meus atendimentos:** lista das solicitações abertas, cada uma com status em linguagem simples. Uma **proposta de vaga** aparece em destaque, com data, hora, local, profissional, o prazo ("confirme até 23/10 às 08:00") e os botões **Confirmar** e **Esta data não serve**.
3. **Nova solicitação** (3 etapas):
   1. **Encaminhamento e fila:** cada fila mostra a **descrição** de para que serve e quem pode entrar. Filas inelegíveis aparecem desabilitadas, com o motivo.
   2. **Preferências:** turno e as perguntas da fila.
   3. **Revisão:** o resumo do encaminhamento fica **aqui**, não na etapa 2.
4. **Detalhe da solicitação:** a **linha do tempo** do começo ao fim (só com a data, sem hora), as respostas dadas e o botão de cancelar, com a lista de motivos.
5. **Histórico de atendimentos** (aba): solicitações atendidas e canceladas.
6. **Avisos:** a lista e o sino no menu, com o contador de não lidos.

### Equipe
7. **Painel da fila:** tabela com **posição**, risco, nome abreviado ("Maria S."), CPF mascarado, chegada, status e **tipo e data da última mudança**. O **motivo** da mudança aparece só no detalhe (tela 8), porque pode conter informação de saúde.
   - Ordenação por prioridade ou por chegada, e filtro por status.
   - Status para a equipe: **"Aguardando confirmação"** (proposta enviada) e **"Agendado"** (confirmado).
8. **Detalhe da solicitação (equipe):** respostas, histórico completo, **classificar risco** e responder os critérios da regulação.
9. **Agenda do dia:** registrar presença ou falta.
10. **Vagas:** visão do período, com destaque para as vagas livres que não puderam ser propostas.
11. **Indicadores** (gestor): taxa de confirmação, faltas, tempo médio e vagas aproveitadas. **A API ainda vai ser criada**; deixe a tela com dados de exemplo e o lugar das chamadas marcado.

## 6. Regras que as telas NÃO podem quebrar

1. **O paciente nunca vê posição na fila, tamanho da fila, nota nem cor de risco.** Para ele, só o status e a linha do tempo. Posição e risco são só da equipe.
2. **Risco tem só três cores:** vermelho, amarelo e verde. Sempre com o texto junto (não use só a cor), por acessibilidade.
3. **Textos do paciente** em português simples, sem termos técnicos ("solicitação" pode virar "pedido").
4. **Nada de dado pessoal no armazenamento do navegador.** No máximo, preferências de interface.
5. **Toda escrita com CSRF**; toda chamada enviando os cookies.
6. **Datas no fuso de Recife, em formato brasileiro.**
7. **Estados de toda tela:** carregando, vazio, erro com mensagem amigável e sucesso.
8. **Somente dados sintéticos** em exemplos, mocks e prints.

## 7. Imagens do Figma

As imagens das telas mostram o **visual** (cores, espaçamentos, componentes), mas são **anteriores à validação com a UPE**. Quando uma imagem e este documento divergirem, vale o documento (seções 5 e 6):
- risco só em vermelho, amarelo e verde;
- resumo do encaminhamento na etapa Revisão;
- o paciente nunca vê posição nem risco;
- os textos novos de "Como a fila funciona".

## 8. Lacunas conhecidas da API (não invente; marque com `// TODO(api)`)

- Indicadores (ainda sem rota).

Já resolvidos no backend (21/10): termo vigente (`GET /termos/vigente`), proposta ativa na lista de "Meus atendimentos", critérios da equipe (`GET /equipe/filas/{id}/criterios`), paginação uniforme `{ total, itens }`, enums e erros declarados no OpenAPI. Confira sempre o OpenAPI antes de cada tela.

## 9. Como trabalhar comigo (instruções para a IA)

- Uma tela por vez. Antes de escrever, diga quais rotas da API a tela usa e quais componentes vai criar.
- Comece pela base:
  - cliente HTTP com CSRF e refresh;
  - rotas protegidas por papel;
  - layout do paciente e layout da equipe;
  - tratamento de Problem Details.
- Crie componentes reutilizáveis: botão, campo com máscara, cartão de status, selo de risco, linha do tempo, tabela e paginação.
- Não invente campos da API. Se faltar algo, pergunte ou marque com `// TODO(api)`.
- Entregue arquivos completos, com o caminho de cada um dentro de `apps/web/`.
