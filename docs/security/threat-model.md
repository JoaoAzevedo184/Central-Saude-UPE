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
| `POST /auth/registro`, `POST /auth/login` | Qualquer pessoa na internet; sem CSRF, limitados por IP e por identificador (AM-004) |
| `POST /auth/refresh`, `POST /auth/logout` | Quem tem o cookie `refresh_token`; exigem CSRF |
| `POST /auth/trocar-senha` | Quem tem uma sessão (inclusive de senha temporária); exige CSRF e conta no limite de tentativas (AM-020) |
| Rotas `/admin/*` | Só ADMIN; devolvem senha temporária na resposta (AM-021) |
| Terminal do servidor: `python -m app.infra.admin`, `python -m app.infra.seed` | Quem tem acesso à VM (SSH) |
| Rotas do paciente com ID (`/agendamentos/{id}`, `/solicitacoes/{id}`) | Pacientes autenticados |
| Rotas da equipe (fila, validação, agenda do dia, presença, painel de vagas, indicadores, auditoria) | Atendentes, gestores e admins; os indicadores, só gestores e admins (AM-025) |
| Worker (geração de vagas, matching, expiração) | Ninguém de fora; roda sozinho contra o banco |
| E-mails enviados | Quem tiver acesso à caixa de entrada do paciente |
| SSH na VM, repositório no GitHub | Integrantes da equipe |

## Ameaças

| ID | STRIDE | Ameaça | Impacto | Prob. | Mitigação | Situação |
| --- | --- | --- | --- | --- | --- | --- |
| AM-001 | Divulgação | Paciente troca o ID na URL e vê ou altera o agendamento de outra pessoa (IDOR) | Alto | Alta | Toda consulta da área do paciente filtra pelo paciente da sessão; recurso alheio responde `404`; teste de acesso negado por rota | Decidido |
| AM-002 | Falsificação | Site malicioso dispara uma ação usando o cookie do paciente (CSRF) | Alto | Média | `SameSite` no cookie + double-submit: o header `X-CSRF-Token` tem de ser igual ao cookie `csrf_token`, em todo `POST`, `PUT`, `PATCH` e `DELETE` (menos registro e login). **Premissa:** não existem subdomínios não confiáveis, porque o valor não é assinado e um subdomínio hostil poderia plantar o cookie | Implementado |
| AM-003 | Falsificação | Script injetado rouba a sessão (XSS), ou o refresh token é roubado de outra forma | Alto | Média | Tokens em cookie `httpOnly`; escape automático do frontend; `Content-Security-Policy`. Refresh token com **rotação e detecção de reuso**: reapresentar um token já substituído revoga a família inteira. O access token leva o `sid` (família) e cai na hora com o logout, o reuso ou a suspensão. **Tolerância de 10 s** (`REFRESH_TOLERANCIA_S`) para duas abas renovarem juntas sem contar como reuso, aceita **uma única vez por token** (`sessao_refresh.reapresentado_em`): a segunda reapresentação revoga a família | Implementado; CSP proposta |
| AM-004 | Negação de serviço / Falsificação | Força bruta de senhas ou criação de contas em massa | Médio | Média | Login limitado por IP e por identificador: `LOGIN_MAX_TENTATIVAS=5` falhas em `LOGIN_JANELA_MIN=15` min, com bloqueio temporário de 15 min (`429` com `Retry-After`). Registro limitado por IP: `REGISTRO_MAX_TENTATIVAS=20` na mesma janela. Identificador guardado só como HMAC-SHA256 | Implementado |
| AM-005 | Divulgação | Descobrir quais CPFs têm conta pelas mensagens de login ou cadastro | Médio | Alta | Login responde igual (mesmo corpo) para inexistente, senha errada e suspenso, com hash fictício para igualar o tempo; o paciente não entra por e-mail. Registro: `409` genérico para CPF, cartão do SUS ou e-mail duplicado | Implementado (UC-001); enumeração de CPF pelo `409` do registro é risco aceito, mitigado pelo limite de registro por IP |
| AM-006 | Adulteração | Duas propostas simultâneas entregam a mesma vaga a dois pacientes | Alto | Média | Índice único parcial; teste de concorrência | Decidido |
| AM-007 | Divulgação | Atendente consulta dados de pacientes de filas em que não trabalha | Médio | Média | Escopo por fila via `escopo_da_equipe()`, aplicado dentro da query; recurso fora do escopo responde `404`; auditoria das consultas da equipe (`CONSULTAR_PAINEL`, `CONSULTAR_SOLICITACAO`) | Implementado ([ADR-025](../decisions/ADR-025-escopo-por-fila.md)) |
| AM-008 | Divulgação | Dados pessoais aparecem em logs ou no corpo dos e-mails | Médio | Alta | Logs sem CPF, nome nem corpo de requisição; e-mail com o mínimo e link para o site: assunto fixo, só prazo ou data e hora, sem nome, CPF, especialidade, unidade, profissional, fila, nota nem risco. Falta, cancelamento e prazo expirado nunca aparecem no e-mail (texto neutro: "Há uma atualização no seu atendimento. Para ver os detalhes, entre na Central."); o detalhe fica só no aviso do site. Teste de conteúdo proíbe "compareceu", "falta", "cancel" e "fila". O log do envio leva só IDs e o tipo do erro, nunca o endereço nem o corpo. Rotas de solicitações e da equipe: logs só com IDs (teste de log sem nome nem CPF) | Implementado: logs e e-mails (migração 0006) |
| AM-009 | Divulgação | Segredos (senha do banco, chave de token) vazam pelo repositório | Alto | Média | `.env*` (menos `.env.example`) no `.gitignore`, para cópias como `.env (recovered)` nunca entrarem no Git; varredura de segredos na CI; rotação se vazar. Em produção, a API não sobe com o `JWT_SECRET_KEY` ou o `LOGIN_HASH_KEY` de exemplo, com segredo de menos de 32 caracteres, com as duas chaves iguais ou com `COOKIE_SECURE=false`. `APP_ENV` é obrigatório, sem padrão: um ambiente esquecido não sobe como `development` e escapa dessas checagens; valor fora de `development`, `test` e `production` impede a inicialização | Parcial |
| AM-010 | Adulteração | Injeção de SQL | Alto | Baixa | ORM ou consultas parametrizadas; validação com Pydantic | Decidido |
| AM-011 | Repúdio | Alguém nega ter cancelado ou confirmado | Médio | Baixa | Auditoria append-only com ator, data e IP | Decidido |
| AM-012 | Negação de serviço | Perda da VM ou do disco apaga o banco | Alto | Baixa | Backup fora da VM com restauração testada | Decidido |
| AM-013 | Elevação de privilégio | Paciente envia `papel`, `classificacao_risco` ou `status` no corpo e o sistema aceita (atribuição em massa) | Alto | Média | Schemas de entrada explícitos, sem esses campos; o papel nunca vem do cliente. No registro, `extra="forbid"` recusa campo não previsto com `422` | Implementado no registro, nas solicitações do paciente e nas rotas `/equipe`; demais rotas conforme forem criadas |
| AM-014 | Divulgação | A API do paciente expõe posição na fila, tamanho da fila, nota ou dados de outros pacientes, inclusive pela linha do tempo | Médio | Média | Schemas de resposta do paciente sem posição, tamanho, nota nem dados de terceiros (RN-007); a posição é calculada na consulta e nunca gravada; `historico_solicitacao` não guarda posição e o paciente vê só eventos com `visivel_paciente = true`; os motivos de volta à fila são textos fixos, sem número | Implementado nas rotas do paciente, inclusive a linha do tempo só com a data, sem hora (mantido pela UPE em 15/10/2026, [ADR-007](../decisions/ADR-007-paciente-ve-status.md)) |
| AM-015 | Falsificação | E-mail falso imitando a central leva o paciente a uma página de login falsa | Médio | Média | Avisos sempre direcionam para o domínio oficial; o site nunca pede senha por e-mail. O link dos e-mails vem de `APP_URL_PUBLICA`; em produção a API não sobe se ela não for `https://` e pública | Implementado |
| AM-016 | Adulteração / Elevação de privilégio | Operador "fura a fila" de um conhecido: reclassifica o risco, altera respostas de critérios, marca falta indevida em outro paciente ou mexe em filas que não são suas | Alto | Média | Escopo por fila: o atendente só opera as filas atribuídas ([ADR-025](../decisions/ADR-025-escopo-por-fila.md)); ordem calculada só pelo domínio (`ordenar_fila()`), sem campo de posição editável; nota e pontos calculados no servidor; falta só depois da tolerância (RN-013); reclassificação e falta registradas em `historico_solicitacao` e na auditoria append-only, com o ator | Decidido |
| AM-017 | Elevação de privilégio | Profissional desligado ou de férias continua acessando o sistema | Médio | Média | Suspensão em vez de exclusão: usuário `SUSPENSO` não faz login, não renova o refresh token e não tem escopo ([ADR-028](../decisions/ADR-028-suspensao-de-acesso.md)) | Implementado: suspender revoga todas as sessões e `usuario_da_sessao` recusa o access token na próxima requisição |
| AM-018 | Adulteração | Corrida na proposta (detalha AM-006 para o matching automático): dois Workers (ou um Worker e um cancelamento) entregam a mesma vaga a dois pacientes ou duas vagas à mesma solicitação | Alto | Média | Índices únicos parciais de RN-001 e RN-002 são a garantia final; vaga e solicitação escolhida travadas com `FOR UPDATE SKIP LOCKED`; conflito descarta só aquela vaga; a mesma ordem de travas em todos os caminhos (vaga, solicitação, agendamento). Teste: `test_adr004_rn002_propor_vagas_concorrente_nao_duplica` | Implementado |
| AM-019 | Adulteração | Paciente confirma ou recusa depois do prazo, aproveitando que o Worker ainda não expirou a proposta, e "segura" a vaga | Médio | Média | O prazo é conferido na própria rota com o `Relogio` (`409` `proposta-expirada`); confirmação e expiração travam o mesmo agendamento e só uma vence. Testes: `test_uc004_um_segundo_depois_do_prazo_responde_409_sem_o_job`, `test_uc004_uc006_confirmacao_e_expiracao_simultaneas_so_uma_vence` | Implementado |
| AM-020 | Falsificação / Elevação de privilégio | Quem tem uma sessão aberta (computador compartilhado, token roubado) tenta descobrir a senha atual testando valores em `POST /auth/trocar-senha`, sem o limite do login | Alto | Média | A troca de senha conta as falhas no mesmo limite do login (`tentativa_login.tipo = 'TROCA_SENHA'`, `LOGIN_MAX_TENTATIVAS=5` em `LOGIN_JANELA_MIN=15` min), por usuário e por IP; o excesso responde `429` com `Retry-After` **sem revogar sessão**. A rota trava o usuário com `FOR UPDATE`, então tentativas paralelas não passam do limite nem enxergam estado velho. Senha atual errada responde `422` no campo, sem dizer mais nada. A troca bem-sucedida revoga as outras sessões do usuário e é auditada (`TROCAR_SENHA`), sem a senha | Mitigado (implementado, migração 0007) |
| AM-021 | Divulgação | Senha temporária (criada ou redefinida pelo admin, ou pelo terminal) é vista por quem não deveria: tela do admin, resposta da API, histórico do terminal ou mensagem passada à pessoa | Médio | Média | Gerada com `secrets` (16 caracteres, ~96 bits), exibida **uma única vez**, gravada só como hash e nunca em log nem em auditoria; `Cache-Control: no-store` em `/admin/`; a conta só consegue trocar a senha (`403` em todo o resto, RN-022); a redefinição revoga as sessões. A senha **não tem validade**: quem a obtiver antes da pessoa pode trocá-la e assumir a conta | Risco aceito: sem validade; a pessoa precisa trocar no primeiro acesso e o admin vê `senha_temporaria = true` na listagem para cobrar |
| AM-022 | Elevação de privilégio | Gestor criado ou editado sem unidades passa a ver a central inteira (todos os hospitais) por esquecimento de preencher o campo | Médio | Média | Sem unidades, o domínio exige `confirmar_visao_central: true` (`verificar_atribuicao_de_unidades`), senão `409` `visao-central-nao-confirmada`; a auditoria de `ATRIBUIR_UNIDADES` marca `visao_central`; o seed da demonstração confirma de forma explícita ao criar o gestor da central | Implementado |
| AM-023 | Adulteração | Trava do seed contornada: o seed em production recusa o banco que tem paciente fora das faixas de CPF reservadas ao seed (`9000xxxxx`, `9100000xx` e o CPF da paciente de desenvolvimento); um cadastro real com CPF numa faixa dessas passaria como "do seed" | Médio | Baixa | A trava tem duas chaves (`DEMO_SEED_PERMITIDO=true` no `.env` e `--confirmo-banco-de-demonstracao`), e o banco de demonstração nunca recebe cadastro real. Bloquear a faixa no `/auth/registro` mudaria o registro e foi descartado | Risco aceito: faixa de CPF forjável |
| AM-024 | Elevação de privilégio | `DEMO_SEED_PERMITIDO=true` esquecida ligada depois da carga: o seed volta a poder rodar em production | Médio | Média | Roteiro da carga manda desligar a variável e subir a API de novo ([README](../../README.md#dados-da-demonstração)). Mesmo ligada, o seed ainda exige a flag, recusa banco com paciente fora do seed e, na reexecução, não troca nenhuma senha nem recria dados | Risco aceito, com procedimento: desligar depois da carga |
| AM-025 | Negação de serviço | Gestor (ou sessão roubada) repete `GET /equipe/indicadores` com período de 366 dias e sobrecarrega o banco | Médio | Média | Um número fixo de consultas agregadas (sem N+1); cada consulta com `statement_timeout` (`INDICADORES_TIMEOUT_S`, padrão 5 s) e `jit = off`; passou do tempo → `503` `consulta-demorada` com `Retry-After: 30`, nunca `500` nem detalhe do banco; só GESTOR e ADMIN. O limite de requisições por usuário fica no Nginx da VM (`limit_req`), não na API | Parcial: timeout implementado; limite no Nginx *(proposta; `infra/nginx` ainda não existe no repositório)* |

## Riscos aceitos e premissas da autenticação

| Item | Risco | Por que aceitamos |
| --- | --- | --- |
| Bloqueio por CPF (AM-004) | Quem sabe o CPF de outra pessoa pode travar o login dela por 15 min | Alternativa seria não limitar por identificador; o bloqueio é curto e não revela se a conta existe |
| Bloqueio por IP (AM-004) | Atrás de NAT (por exemplo, a recepção do hospital), usuários legítimos dividem o limite | O limite de registro é maior (20) por esse motivo |
| Contagem não atômica (AM-004) | Requisições paralelas passam um pouco do limite | Risco baixo: o excesso é de poucas tentativas |
| IP do cliente (AM-004) | O limite por IP só vale se o IP for confiável | O nginx tem IP fixo (`172.30.0.10`) e a API só confia no `X-Forwarded-For` vindo dele (`--forwarded-allow-ips`). O nginx precisa usar `proxy_set_header X-Forwarded-For $remote_addr`, para descartar o valor enviado pelo cliente |
| Tolerância do refresh (AM-003) | Quem tem o token no momento do roubo pode, nos 10 s da tolerância, renovar e ganhar uma cadeia própria na mesma família | Apontado na revisão de segurança. O uso da tolerância é registrado no log e vale uma única reapresentação por token: o ladrão ganha no máximo uma cadeia, e uma segunda reapresentação revoga a família. Restringir também por IP: *(proposta)* |
| CSRF double-submit (AM-002) | Valor não assinado: um subdomínio não confiável poderia plantar o cookie | Premissa: não existem subdomínios não confiáveis |
| Enumeração de CPF no registro (AM-005) | O `409` genérico ainda revela que existe um cadastro com algum dos três dados | Limite de registro por IP |
| Senha temporária sem validade (AM-021) | Quem ler a senha antes da pessoa assume a conta até ela trocar | Protótipo com poucas contas; o admin vê quem ainda não trocou (`senha_temporaria` na listagem). Validade da senha temporária é evolução possível |
| Faixa de CPF do seed (AM-023) | Um CPF real dentro das faixas reservadas passaria na trava do seed | O seed só roda em banco de demonstração, com duas chaves; mudar o registro para barrar a faixa foi descartado |
| `DEMO_SEED_PERMITIDO` esquecida (AM-024) | O seed poderia rodar de novo em production | Desligar a variável faz parte do roteiro da carga; a reexecução não troca senha |
| Banco de desenvolvimento promovido a demonstração | Contas do seed de desenvolvimento têm a senha comum, conhecida. Rodar o seed em production sobre esse banco **não** troca as senhas | O seed avisa (`redefinir-senha`) e o roteiro manda rodar o seed num banco novo ou redefinir cada conta |

## Revisão

Revisar esta tabela quando:
- entrar um ponto de entrada novo (canal, integração);
- uma questão em aberto for respondida;
- houver qualquer incidente ([resposta a incidentes](incident-response.md)).
