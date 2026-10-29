# PLAN — MVP da Central de Teleagendamento (CH/UPE)

> Plano de trabalho até a entrega do MVP (novembro de 2026). Vale para o grupo e para os agentes (Claude Code e Codex): leia junto com o [`AGENTS.md`](http://AGENTS.md) antes de qualquer tarefa. Atualize este arquivo quando o escopo ou a ordem mudarem. **Estado em 29/10/2026,** `main` **em** `dd7316a`**.**

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

## 2. Fora do MVP (decidido em 29/10)


| Item                                           | Para onde vai                                                                                                                                                                                                                             |
| ---------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Módulo de documentos** (envio e conferência) | **Projeto novo, separado, em Rust**, pensado para vários centros hospitalares. A branch `backend/documents` (`136a8d8`) **não entra na** `main`: fica guardada como referência (ADR-031, regras de validação de arquivo, modelo de dados) |
| Agenda do dia e presença (equipe)              | Depois do MVP. Falta e reaproveitamento aparecem nos números do seed                                                                                                                                                                      |
| Tela de vagas (equipe)                         | Depois do MVP                                                                                                                                                                                                                             |
| Telas de administração                         | Depois do MVP. As contas da demo vêm do seed; as rotas `/admin` existem e podem ser mostradas pelo Swagger                                                                                                                                |
| Meus dados e edição de contato                 | Depois do MVP (não há rota para editar)                                                                                                                                                                                                   |
| Recuperação de senha do paciente               | Depende de decisão do grupo; fora do MVP                                                                                                                                                                                                  |
| Tela de indicadores (gestor)                   | **Só se sobrar tempo** (a API já existe)                                                                                                                                                                                                  |


## 3. Estado atual

### Backend (`apps/backend`): pronto para o MVP

Autenticação com papéis e cookies (CSRF, refresh, troca obrigatória de senha), cadastro com LGPD, filas e critérios, solicitação, classificação, proposta automática de vaga (Worker), confirmação, recusa e expiração, presença e falta, avisos e e-mail via outbox, indicadores, administração, auditoria e seed com histórico de 8 semanas. O contrato está em `docs/architecture/openapi.json`.

**Daqui até a entrega, o backend só recebe correções e o que as telas pedirem.**

### Frontend (`apps/web`)


| Tela                                                                        | Estado                                   |
| --------------------------------------------------------------------------- | ---------------------------------------- |
| Entrar, Criar conta (3 etapas)                                              | Pronto                                   |
| Trocar senha (obrigatória)                                                  | Pronto                                   |
| "/" redireciona conforme a sessão                                           | Pronto                                   |
| Meus atendimentos, com a proposta de vaga (confirmar / esta data não serve) | Pronto                                   |
| Novo pedido (3 etapas)                                                      | Pronto                                   |
| **Detalhe do pedido, linha do tempo e cancelamento (paciente)**             | **Falta**                                |
| **Avisos (lista simples)**                                                  | **Falta** (o contador no menu já existe) |
| **Layout da equipe**                                                        | **Falta**                                |
| **Fila (equipe)**                                                           | **Falta**                                |
| **Detalhe do pedido e classificação de risco (equipe)**                     | **Falta**                                |
| Indicadores (gestor)                                                        | Opcional                                 |


### Infra

- Docker Compose local funcionando (postgres, api, worker, mailpit).
- **VM Oracle ainda não configurada.** O roteiro de configuração está no prompt "Configurar a VM" (fases 0 a 5).

### Referências de tela

- Wireframes dos fluxos do paciente e da equipe (Excalidraw).
- Protótipo navegável no Claude Design: telas da fila, classificação e indicadores. É **referência visual**; o código de verdade segue o contrato da API.

## 4. Plano por semana

As datas são propostas; o grupo ajusta.

### Semana 1 — 30/10 a 05/11: paciente completo

- \[ \] **Detalhe do pedido (paciente):** status em linguagem simples, linha do tempo (só datas), dados da consulta quando agendada, **cancelar com motivo** (lista fechada). Rotas: `GET /solicitacoes/{id}`, `POST /solicitacoes/{id}/cancelar`.
- \[ \] **Avisos:** lista, marcar como lido, marcar todos. Rotas: `GET /avisos`, `POST /avisos/{id}/lido`, `POST /avisos/lidos`.
- \[ \] Ligar "Ver detalhes" de Meus atendimentos ao detalhe.
- \[ \] **VM, fases 0 e 1** (inventário e segurança básica), em paralelo.

### Semana 2 — 06/11 a 12/11: equipe

- \[ \] **Layout da equipe:** menu lateral (Fila; Indicadores só para gestor, se existir), nome e papel, Sair.
- \[ \] **Fila:** escolha da fila do escopo, tabela com posição, risco (3 cores, sempre com texto), nome abreviado, CPF mascarado, chegada, status e tipo/data da última mudança; ordenação por prioridade ou chegada; filtro por status. Rotas: `GET /equipe/filas`, `GET /equipe/filas/{id}/solicitacoes`.
- \[ \] **Detalhe e classificação:** respostas, histórico completo (com motivo), critérios da regulação, **classificar** (risco + motivo). Rotas: `GET /equipe/solicitacoes/{id}`, `GET /equipe/filas/{id}/criterios`, `PUT /equipe/solicitacoes/{id}/respostas`, `POST /equipe/solicitacoes/{id}/classificar`.
- \[ \] **VM, fases 2 e 3** (Docker e aplicação).

### Semana 3 — 13/11 a 19/11: demo de verdade

- \[ \] **VM, fases 4 e 5:** nginx com HTTPS e cabeçalhos de segurança, limite de taxa, backup e [`deploy.sh`](http://deploy.sh). Configuração final salva em `deploy/nginx/`.
- \[ \] Chave JWT de produção com 32 bytes ou mais; de preferência, a API recusa subir com chave curta (tarefa pequena de backend).
- \[ \] **Seed de demonstração na VM** (roteiro na seção 6 do README: parar API e Worker, ligar `DEMO_SEED_PERMITIDO`, rodar, desligar, subir).
- \[ \] **Ensaio ponta a ponta** com dois navegadores (seção 7), no celular e no computador.
- \[ \] Teste rápido de usabilidade com 2 ou 3 pessoas de fora do grupo, no celular; anotar para o relatório.
- \[ \] Se sobrar tempo: tela de indicadores.

### Semana 4 — 20/11 a 26/11: congelamento

- \[ \] **Congelar a** `main`: só correções de defeito.
- \[ \] Ensaio da apresentação (quem fala o quê; plano B com vídeo gravado caso a VM caia).
- \[ \] Relatório do Projeto de Intervenção: problema, solução, resultados do teste de usabilidade e próximos passos (incluindo o módulo de documentos como projeto futuro).

## 5. Como trabalhamos

- **Uma tarefa = um worktree = uma branch**, criado no Orca a partir da `main` atualizada (`git pull --ff-only origin main` no checkout principal).
- **O Codex implementa e o Claude revisa** (um modelo nunca revisa o próprio trabalho). Todo prompt começa por um Passo 0 com plano e espera aprovação.
- **Agentes nunca fazem commit, push, merge, rebase nem criam branch.** Quem faz é a pessoa.
- **Docker Compose só no checkout principal.** No worktree do frontend, só `npm run dev`.
- **O contrato é o** `openapi.json`**, e quem muda o contrato é o backend.** Quando backend e frontend ficam prontos juntos, o backend entra primeiro; depois, o frontend faz `git merge main` e roda `npm run api:generate`.
- **Nunca refazer (amend ou rebase) um commit que já foi para a** `main` **ou para o** `origin`**.**
- **Arquivos gerados** (`openapi.json`, `schema.d.ts`) não se resolvem à mão num conflito: regenere.
- **Toda tela entrega:** lint, testes, build, `npm run api:generate -- --check`, conferência em 360 px e desktop e, quando possível, E2E real contra a API da `main`.
- **Regras de produto que nenhuma tela quebra:**
  - o paciente nunca vê posição, tamanho da fila, nota nem risco;
  - risco só em 3 cores, sempre com texto;
  - nada pessoal no armazenamento do navegador nem no console;
  - toda escrita com CSRF;
  - datas no fuso de Recife;
  - só dados sintéticos.
- **Se a tela precisar de algo que a API não tem:** marcar `// TODO(api)` e abrir o pedido para o backend (tela, o que falta, por quê, exemplo do dado).

## 6. Riscos


| Risco                                                                                                  | Efeito                              | O que fazer                                                                                  |
| ------------------------------------------------------------------------------------------------------ | ----------------------------------- | -------------------------------------------------------------------------------------------- |
| As 3 telas da equipe demoram mais que uma semana                                                       | A demo não fecha o ciclo            | A fila e a classificação vêm antes de qualquer outra coisa; indicadores só depois            |
| A VM dá problema perto da data                                                                         | Sem demo ao vivo                    | Começar a VM na semana 1, em paralelo; gravar um vídeo da demo na semana 3 como plano B      |
| Mudança de contrato no meio das telas                                                                  | Tipos quebram no frontend           | Backend congelado, exceto correções; toda mudança passa pelo `openapi.json` e pelo `--check` |
| Decisões pendentes do grupo (RN-020: a primeira recusa mantém a posição?; ADR-030: histórico familiar) | Regra diferente do que a UPE espera | Manter o comportamento atual no MVP e registrar como pendência no relatório                  |
| Dados que parecem reais na apresentação                                                                | Confusão com dados da UPE           | Dizer que os números são simulados; o seed já marca isso no README                           |


## 7. Roteiro da demonstração (critério de pronto)

1. **Paciente (celular):** entra com a conta de apresentação, troca a senha temporária e vê Meus atendimentos.
2. Faz um **novo pedido**; o pedido aparece como "em análise".
3. **Equipe (computador):** atendente entra, troca a senha, abre a **fila**, acha o pedido novo e **classifica** o risco.
4. O **Worker propõe a vaga** (na demo, dá para mostrar um pedido do seed que já está com proposta).
5. **Paciente:** vê a proposta com o prazo, **confirma**; o aviso aparece no sino.
6. **Equipe:** o pedido aparece como **agendado** na fila.
7. (Opcional) **Gestor:** indicadores das 8 semanas do seed.

## 8. Depois do MVP

- **Módulo de documentos**, como projeto próprio em Rust, para vários centros hospitalares. Ponto de partida:
  - a branch `backend/documents` deste repositório (ADR-031, as regras de validação e recodificação de arquivo, os estados do item e a trava "documentos antes da fila");
  - o plano "Situação atual e plano do módulo de documentos";
  - as telas D1 a D4 no Claude Design.
- Agenda do dia e presença, vagas, administração e Meus dados.
- Recuperação de senha do paciente.
- Antivírus e criptografia em repouso (requisitos de produção).