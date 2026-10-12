# Modelo de ameaças

Método: STRIDE aplicado aos pontos de entrada do sistema. **Impacto** e **probabilidade** são estimativas da equipe (Alto, Médio, Baixo) para priorizar o trabalho do MVP.

## Pontos de entrada e fronteiras de confiança

```mermaid
flowchart LR
  ext(["Internet<br/>não confiável"]) -->|HTTPS| nginx["Nginx"]
  nginx --> api["API"]
  api --> db[("PostgreSQL")]
  worker["Worker"] --> db
  worker -->|SMTP| mail[["Provedor de e-mail"]]
  dev(["Integrantes<br/>SSH e GitHub"]) -.-> vm["VM"]
  classDef fronteira stroke-dasharray: 5 5
```

| Ponto de entrada | Quem alcança |
| --- | --- |
| `POST /auth/login`, `POST /auth/registro` | Qualquer pessoa na internet |
| Rotas do paciente com ID (`/agendamentos/{id}`, `/solicitacoes/{id}`) | Pacientes autenticados |
| Rotas da equipe (fila, validação, indicadores, auditoria) | Atendentes, gestores e admins |
| E-mails enviados | Quem tiver acesso à caixa de entrada do paciente |
| SSH na VM, repositório no GitHub | Integrantes da equipe |

## Ameaças

| ID | STRIDE | Ameaça | Impacto | Prob. | Mitigação | Situação |
| --- | --- | --- | --- | --- | --- | --- |
| AM-001 | Divulgação | Paciente troca o ID na URL e vê ou altera o agendamento de outra pessoa (IDOR) | Alto | Alta | Toda consulta da área do paciente filtra pelo paciente da sessão; recurso alheio responde `404`; teste de acesso negado por rota | Decidido |
| AM-002 | Falsificação | Site malicioso dispara uma ação usando o cookie do paciente (CSRF) | Alto | Média | `SameSite` no cookie + header `X-CSRF-Token` obrigatório | Decidido |
| AM-003 | Falsificação | Script injetado rouba a sessão (XSS) | Alto | Média | Token em cookie `httpOnly`; escape automático do frontend; `Content-Security-Policy` | Parcial: CSP proposta |
| AM-004 | Negação de serviço / Falsificação | Força bruta de senhas ou criação de contas em massa | Médio | Média | Limite de tentativas por IP e por CPF no Nginx ou na API; atraso progressivo | Proposto |
| AM-005 | Divulgação | Descobrir quais CPFs têm conta pelas mensagens de login ou cadastro | Médio | Alta | Mensagens genéricas; mesmo tempo de resposta nos dois casos | Decidido (UC-001) |
| AM-006 | Adulteração | Duas propostas simultâneas entregam a mesma vaga a dois pacientes | Alto | Média | Índice único parcial; teste de concorrência | Decidido |
| AM-007 | Divulgação | Atendente consulta dados de pacientes de unidades em que não trabalha | Médio | Média | Escopo por unidade, se adotado; auditoria das consultas da equipe | **ABERTO-3** |
| AM-008 | Divulgação | Dados pessoais aparecem em logs ou no corpo dos e-mails | Médio | Alta | Logs sem CPF, nome nem corpo de requisição; e-mail com o mínimo e link para o site | Proposto |
| AM-009 | Divulgação | Segredos (senha do banco, chave de token) vazam pelo repositório | Alto | Média | `.env` no `.gitignore`; varredura de segredos na CI; rotação se vazar | Parcial |
| AM-010 | Adulteração | Injeção de SQL | Alto | Baixa | ORM ou consultas parametrizadas; validação com Pydantic | Decidido |
| AM-011 | Repúdio | Alguém nega ter cancelado ou confirmado | Médio | Baixa | Auditoria append-only com ator, data e IP | Decidido |
| AM-012 | Negação de serviço | Perda da VM ou do disco apaga o banco | Alto | Baixa | Backup fora da VM com restauração testada | Decidido |
| AM-013 | Elevação de privilégio | Paciente envia `papel`, `classificacao_risco` ou `status` no corpo e o sistema aceita (atribuição em massa) | Alto | Média | Schemas de entrada explícitos, sem esses campos; o papel nunca vem do cliente | Proposto |
| AM-014 | Divulgação | A API do paciente expõe posição na fila ou dados de outros pacientes da fila | Médio | Média | Schemas de resposta do paciente sem posição nem dados de terceiros (RN-007) | Decidido |
| AM-015 | Falsificação | E-mail falso imitando a central leva o paciente a uma página de login falsa | Médio | Média | Avisos sempre direcionam para o domínio oficial; o site nunca pede senha por e-mail | Proposto |

## Revisão

Revisar esta tabela quando:
- entrar um ponto de entrada novo (canal, integração, app mobile);
- uma questão em aberto for respondida;
- houver qualquer incidente ([resposta a incidentes](incident-response.md)).
