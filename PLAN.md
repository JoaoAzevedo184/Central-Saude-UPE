# PLAN — MVP da Central de Teleagendamento (CH/UPE)

> Plano de trabalho até a entrega do MVP (novembro de 2026). Vale para o grupo e para os agentes (Claude Code e Codex): leia junto com o [`AGENTS.md`](AGENTS.md) antes de qualquer tarefa. Atualize este arquivo quando o escopo ou a ordem mudarem. **Estado em 08/11/2026, `main` em `0f54af7`, no ar em https://central-saude-upe.duckdns.org.**

## 1. Objetivo do MVP

Mostrar, com **dados sintéticos** e em dois navegadores (paciente e equipe), o ciclo completo:

```
paciente cria conta e faz o pedido
  → equipe vê o pedido na fila e classifica o risco
  → o sistema propõe uma vaga sozinho, pela ordem da fila
  → paciente confirma (ou diz "esta data não serve" e volta à fila)
  → equipe vê o pedido agendado
```

Tudo rodando na VM, com HTTPS, e com o seed de demonstração carregado.

**Critério de pronto:** o roteiro da seção 7 roda do começo ao fim na VM, sem intervenção manual no banco.

## 2. Fora do MVP

| Item | Para onde vai |
| --- | --- |
| **Módulo de documentos** (envio e conferência) | **Projeto novo, separado, em Rust**, pensado para vários centros hospitalares. A branch `backend/documents` (`136a8d8`) **não entra na `main`**: fica guardada como referência (ADR-031, regras de validação de arquivo, modelo de dados) |
| Agenda do dia e presença (equipe) | Leva 1, depois da apresentação (a API já existe) |
| Cadastro de agendas e painel de vagas | Leva 1. Hoje as agendas só vêm do seed; o Worker gera as vagas delas |
| Telas de administração | Leva 1. As rotas `/admin` existem, mas **a documentação da API (`/api/v1/docs`) fica desligada em produção**; na apresentação, a administração só aparece rodando local |
| Meus dados e edição de contato | Leva 2 (não há rota para editar) |
| Recuperação de senha do paciente | Leva 2, depois de decisão do grupo. Hoje a equipe redefine pelo terminal (`redefinir-senha --cpf`) |
| Prontuário, teleconsulta e regras por unidade | Depois de validar a [pesquisa sobre o CHU/UPE](docs/product/pesquisa-chu-upe/README.md) com o hospital |

## 3. Estado atual

### Backend (`apps/backend`): pronto para o MVP

Autenticação com papéis e cookies (CSRF, refresh, troca obrigatória de senha), cadastro com LGPD, filas e critérios, solicitação, classificação, proposta automática de vaga (Worker), confirmação, recusa e expiração, presença e falta, avisos e e-mail via outbox, indicadores, administração, auditoria e seed com histórico de 8 semanas. O contrato está em `docs/architecture/openapi.json`.

Entraram depois de 29/10:

- **Pacote de produção:** nginx no Docker Compose (HTTPS, cabeçalhos de segurança, limite de requisições), certificado Let's Encrypt com renovação, build do frontend em contêiner, `scripts/deploy.sh`, `scripts/backup.sh` com teste de restauração, e `/api/v1/docs` desligado em produção.
- **Limite de login separado:** 5 falhas por conta e 50 por IP em 15 minutos (`LOGIN_MAX_TENTATIVAS_IP`), também na troca de senha; registro com 50 por IP. Validação de CPF, CNS e telefone só com dígitos 0 a 9.
- **Senha de paciente pelo terminal:** `python -m app.infra.admin redefinir-senha --cpf CPF`.
- **Fila de demonstração:** `python -m app.infra.demonstracao preparar|desativar`, com as mesmas travas do seed, para a apresentação ao vivo (seção 7).

**Daqui até a entrega, o backend só recebe correções.**

### Frontend (`apps/web`)

| Tela | Estado |
| --- | --- |
| Entrar, Criar conta (3 etapas) | Pronto |
| Trocar senha (obrigatória) | Pronto |
| "/" redireciona conforme a sessão | Pronto |
| Meus atendimentos, com a proposta de vaga | Pronto |
| Novo pedido (3 etapas) | Pronto |
| Detalhe do pedido, linha do tempo e cancelamento (paciente) | Pronto |
| Avisos | Pronto |
| Layout da equipe | Pronto |
| Fila (equipe) | Pronto |
| Detalhe do pedido e classificação de risco (equipe) | Pronto |
| **Indicadores (gestor)** | **Em andamento**, com carregamento sob demanda (traz o pacote de volta para menos de 500 kB) |

### Infra

- **VM Oracle no ar desde 07/11:** São Paulo, Ampere A1 (ARM64, 2 OCPUs, 12 GB), Ubuntu 24.04, Always Free.
- Docker Compose com `postgres`, `api`, `worker`, `nginx` e `certbot`; API e PostgreSQL só em `127.0.0.1`.
- HTTPS válido (DuckDNS + Let's Encrypt), renovação testada.
- SSH só por chave e só pela rede privada (Tailscale); fail2ban e atualizações automáticas de segurança.
- Backup diário às 3h, com teste de restauração.
- Seed histórico de 8 semanas carregado. Todas as filas do seed estão cheias e sem vaga livre, como num hospital lotado; por isso a demonstração ao vivo usa a fila de demonstração.
- Senhas da equipe e dos pacientes de apresentação trocadas em 08/11, depois de aparecerem em capturas de tela.
- Passo a passo em [`docs/operations/deployment.md`](docs/operations/deployment.md).

### Referências

- Wireframes dos fluxos do paciente e da equipe (Excalidraw) e protótipo no Claude Design.
- [Pesquisa pública sobre o CHU/UPE](docs/product/pesquisa-chu-upe/README.md): catálogo preliminar de serviços e exames, regras encontradas e comparação com o MVP. **Ainda não verificada.**

## 4. Plano por semana

### Semanas 1 e 2 — 30/10 a 12/11: telas e VM (concluídas)

- [x] Detalhe do pedido, avisos e "Ver detalhes" (paciente).
- [x] Layout da equipe, fila, detalhe e classificação de risco.
- [x] VM, fases 0 a 6: segurança, Docker, aplicação, nginx com HTTPS, backup, deploy e seed.
- [x] Chave JWT de produção com 32 caracteres ou mais (a API recusa subir com chave curta).
- [x] Limite de login por IP, senha de paciente pelo terminal e fila de demonstração.
- [x] Troca das senhas expostas.

### Semana 3 — 09/11 a 19/11: demo de verdade

- [ ] **Tela de Indicadores:** implementação pronta; revisão cruzada, E2E manual com o gestor e deploy pendentes. Prazo 15/11.
- [ ] **Testes manuais que faltam:** recusa de proposta, cancelamento, reclassificação, escopo entre unidades pela URL e celular. Prazo 15/11.
- [ ] **Revalidar a pesquisa:** reabrir as fontes 1, 3, 4, 5 e 8 da pesquisa, registrar data de acesso e trecho, e confirmar se a Central de Teleagendamento do NUTES-CISAM está ativa. Prazo 15/11.
- [ ] **Ensaio ponta a ponta** com dois navegadores (seção 7), no celular e no computador, preparando e desativando a fila de demonstração. 16 a 18/11.
- [ ] **Teste de usabilidade** com 2 ou 3 pessoas de fora do grupo, no celular; anotar para o relatório. Até 19/11.
- [ ] **Vídeo da demonstração** como plano B. Até 19/11.
- [ ] Backup novo, último deploy e **congelamento da `main`**. 19/11.

### Semana 4 — 20/11 a 26/11: apresentação

- [ ] Só correções de defeito na `main`.
- [ ] Ensaio da apresentação (quem fala o quê; plano B com o vídeo).
- [ ] Slides, incluindo "o que é regra oficial e o que é proposta do MVP" (classes da pesquisa).
- [ ] Relatório do Projeto de Intervenção: problema, contexto (pesquisa revalidada), solução, resultados do teste de usabilidade e próximos passos (validação institucional e módulo de documentos).

## 5. Como trabalhamos

- **Uma tarefa = um worktree = uma branch**, criado no Orca a partir da `main` atualizada (`git pull --ff-only origin main` no checkout principal). Colegas sem Orca trabalham numa branch própria e abrem um Pull Request.
- **Revisão cruzada:** quem implementa com o Codex é revisado pelo Claude Code, e vice-versa. Um modelo nunca revisa o próprio trabalho. Todo prompt começa por um Passo 0 com plano e espera aprovação.
- **Agentes nunca fazem commit, push, merge, rebase, stash nem criam branch.** Quem faz é a pessoa. Se o trabalho precisar ser commitado antes de um merge da `main`, a pessoa commita na branch da tarefa, e a revisão olha `git diff main...HEAD`.
- **Os worktrees compartilham o mesmo banco de teste:** nunca rode o `scripts/testar.sh` em dois worktrees ao mesmo tempo.
- **Docker Compose só no checkout principal.** No worktree do frontend, só `npm run dev`. Antes de um E2E, confira se o Vite é do worktree certo (`ss -ltnp | grep 517`).
- **O contrato é o `openapi.json`, e quem muda o contrato é o backend.** O backend entra primeiro; depois, o frontend faz `git merge main` e roda `npm run api:generate`.
- **Nunca refazer (amend ou rebase) um commit que já foi para a `main` ou para o `origin`.** Arquivos gerados (`openapi.json`, `schema.d.ts`) não se resolvem à mão num conflito: regenere.
- **Depois de todo push, confira o CI** na aba Actions (jobs `backend`, `docker` e `infra`).
- **Senhas, tokens e o `.env` nunca vão para chat, print ou repositório.** Ao mostrar a saída de um comando que gera senha, mostre só a linha com o `id=`.
- **Na VM**, o Docker roda pelo atalho `PATH="$HOME/bin:$PATH"`, e o deploy é sempre pelo `scripts/deploy.sh`.
- **Toda tela entrega:** lint, testes, build, `npm run api:generate -- --check`, conferência em 360 px e desktop e E2E real contra a API da `main`. README e documentação descrevem a tela, sem contagem de testes nem relato de E2E.
- **Regras de produto que nenhuma tela quebra:**
  - o paciente nunca vê posição, tamanho da fila, nota nem risco;
  - risco só em 3 níveis, sempre com cor e texto;
  - nada pessoal no armazenamento do navegador nem no console;
  - toda escrita com CSRF;
  - datas no fuso de Recife;
  - só dados sintéticos.
- **Se a tela precisar de algo que a API não tem:** avise no Passo 0 e abra o pedido para o backend (tela, o que falta, por quê, exemplo do dado).

## 6. Riscos

| Risco | Efeito | O que fazer |
| --- | --- | --- |
| Pedido feito ao vivo não recebe vaga (todas as filas do seed estão cheias) | O passo central da demo não acontece | Preparar a fila de demonstração antes da apresentação; plano B: a proposta já aberta de um paciente do seed |
| A VM cai ou a Oracle recupera a instância por ociosidade | Sem demo ao vivo | Usar o sistema todo dia até a apresentação; vídeo da demo como plano B |
| A plateia erra a senha no mesmo Wi-Fi | Login travado | Resolvido: 50 falhas por IP e 5 por conta; no dia, dá para subir o limite por IP no `.env` |
| A banca pergunta se as regras são do hospital | Projeto parece desconectado da realidade | Slide com as classes da pesquisa; dizer o que é proposta (matching automático, nota, prazos) e o que falta validar |
| Pesquisa usada sem conferência | Afirmação errada no relatório | Só usar como fato o que for revalidado com URL, data e trecho |
| Decisões pendentes (RN-020: a primeira recusa mantém a posição?; ADR-030: histórico familiar) | Regra diferente do que a UPE espera | Manter o comportamento atual e registrar como pendência no relatório |
| Dados que parecem reais na apresentação | Confusão com dados da UPE | Dizer que os números e as filas são simulados |
| Credenciais expostas de novo | Acesso indevido à demo | Senhas só no gerenciador; trocar de novo pelo terminal se vazarem |

## 7. Roteiro da demonstração (critério de pronto)

**Antes de começar (na véspera):** preparar a fila "Consulta de demonstração" com `python -m app.infra.demonstracao preparar` (roteiro no README, com as travas ligadas e desligadas na ordem certa) e anotar a data da primeira vaga que o resumo informa. A vaga oferecida será para cerca de dois dias depois, por causa das regras de antecedência.

1. **Paciente (celular):** cria a conta na hora (dados inventados, CPF e CNS válidos de gerador) ou entra com a conta de apresentação e troca a senha temporária.
2. Faz um **novo pedido** na fila "Consulta de demonstração"; o pedido aparece como "em análise".
3. **Equipe (computador):** a atendente do CISAM entra, abre a **fila**, acha o pedido novo e **classifica** o risco, com motivo.
4. O **Worker propõe a vaga** em cerca de 1 minuto. Plano B: mostrar o pedido do seed que já está com proposta.
5. **Paciente:** vê a proposta com o prazo e **confirma**; o aviso aparece no sino.
6. **Equipe:** o pedido aparece como **agendado** na fila.
7. **Gestor:** indicadores das 8 semanas do seed.

**Depois da apresentação:** `python -m app.infra.demonstracao desativar`.

## 8. Depois do MVP

- **Leva 1 (dezembro, proposta):** backend de agendas e vagas, versão do pedido nas escritas (concorrência), nome e unidade da equipe no `/me`, autor no histórico, data do pedido no painel; telas de agenda do dia e presença, cadastro e painel de vagas, e usuários da equipe.
- **Leva 2:** critérios da regulação (respostas da equipe), cadastro de filas e unidades, Meus dados, recuperação de senha, termos públicos e página de erro, CAPTCHA no cadastro se o sistema abrir ao público.
- **Validação institucional** (a partir da [pesquisa](docs/product/pesquisa-chu-upe/README.md)): prontuário antes do pedido no CISAM, teleconsulta com consentimento, prazos de cancelamento e remarcação, reaproveitamento de vaga recusada (ADR-021 e RN-020) e códigos SIGTAP no catálogo. Revisar as filas do seed com o catálogo (por exemplo, mamografia no CISAM).
- **Módulo de documentos**, como projeto próprio em Rust, para vários centros hospitalares. Ponto de partida:
  - a branch `backend/documents` (ADR-031, regras de validação e recodificação de arquivo, estados do item e a trava "documentos antes da fila");
  - o plano "Situação atual e plano do módulo de documentos";
  - as telas D1 a D4 no Claude Design.
- **Operação:** cópia do backup fora da VM, monitoramento, SMTP real, acesso de emergência documentado, antivírus e criptografia em repouso.
