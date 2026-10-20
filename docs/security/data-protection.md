# Proteção de dados

> Este projeto é um protótipo acadêmico e usa **somente dados sintéticos**. As medidas abaixo descrevem como o sistema foi desenhado para tratar dados reais. Elas não substituem uma avaliação jurídica nem um Relatório de Impacto à Proteção de Dados, que seriam necessários antes de qualquer uso real.

## Inventário de dados pessoais

| Dado | Onde | Finalidade | Sensível? | Exibição |
| --- | --- | --- | --- | --- |
| Nome | `paciente` | Identificar o paciente nas telas e avisos | Não | Completo para o próprio paciente; abreviado na fila da equipe |
| CPF | `paciente` | Identificação única e login | Não | Mascarado (`***.482.***-10`) em todas as telas |
| Cartão do SUS | `paciente` | Vínculo com o SUS e com a regulação | Não | Mascarado |
| Data de nascimento | `paciente` | Elegibilidade por idade da fila e critérios de idade do protocolo | Não | Só para o próprio paciente e a equipe |
| Sexo | `paciente` | **Só** a elegibilidade da fila (por exemplo, laqueadura e mamografia). Anulável; sem ele, o paciente fica inelegível só para filas que restringem sexo | Não | Só para o próprio paciente e a equipe |
| Município | `paciente` | **Só** direcionar o paciente para a unidade e as filas adequadas. Anulável | Não | Só para o próprio paciente e a equipe |
| Celular, e-mail | `paciente`, `usuario` | Avisos. O e-mail do paciente é opcional; a equipe usa o e-mail para entrar | Não | Só para o próprio paciente |
| CPF ou e-mail digitado no login, e IP | `tentativa_login` | Limite de tentativas (AM-004). O identificador é guardado só como HMAC-SHA256 com chave do servidor (`LOGIN_HASH_KEY`); nunca em claro | Não | Ninguém pela interface |
| Hash do refresh token e IP | `sessao_refresh` | Sessão renovável e detecção de reuso (ADR-003); o token em si não é guardado | Não | Ninguém pela interface |
| Especialidade solicitada | `solicitacao` | Fila e agendamento | **Sim** (revela condição de saúde) | Paciente e equipe |
| Classificação de risco | `solicitacao` | Ordem da fila | **Sim** | Só a equipe |
| Respostas aos critérios da fila (por exemplo, número de filhos, uso de anticoagulante, prioridade legal) e a nota | `resposta_criterio`, `solicitacao.nota` | Ordem da fila ([ADR-024](../decisions/ADR-024-protocolo-por-fila.md)) | **Sim** | Só a equipe das filas do escopo; o paciente vê as próprias respostas, não os pontos nem a nota |
| Histórico familiar (por exemplo, "mãe ou irmã teve câncer de mama?") | `resposta_criterio` | Critério da fila ([ADR-030](../decisions/ADR-030-historico-familiar-como-criterio.md)) | **Sim** | Igual às demais respostas |
| Motivo do cancelamento | `solicitacao.motivo_cancelamento`, `agendamento.motivo_cancelamento` | Entender por que o pedido ou a proposta foi encerrado; contar recusas (RN-020). Códigos de lista fechada, sem texto livre | Não | Paciente (como rótulo) e equipe |
| Nome do profissional da agenda | `agenda.profissional` | Dizer ao paciente com quem é a consulta ([UC-004](../requirements/use-cases/UC-004-confirmar-proposta.md)) | Não (dado funcional do profissional) | O paciente vê só o da **própria** proposta ou consulta; a equipe, na agenda do dia e no painel de vagas |
| Linha do tempo da solicitação | `historico_solicitacao` | Transparência para o paciente e motivo das mudanças para a equipe | Não (sem posição) | O paciente vê só os eventos com `visivel_paciente = true` |
| Situação da conta da equipe (suspensão, data, motivo) | `usuario` | Controle de acesso ([ADR-028](../decisions/ADR-028-suspensao-de-acesso.md)) | Não | Só o admin |
| IP e ações (inclui login e registro) | `auditoria` | Rastreabilidade e segurança | Não | Só o admin |

O sistema **não** guarda diagnóstico, prontuário, resultados de exames nem qualquer dado clínico além do necessário para agendar.

## Princípios aplicados

- **Minimização:** cada campo só existe se um fluxo usa. Campos novos com dado pessoal precisam aparecer nesta tabela no mesmo pull request. `sexo` e `municipio` servem só à elegibilidade e ao direcionamento; não entram em indicadores nem em e-mails.
- **Minimização nas solicitações:**
  - o motivo do cancelamento pelo paciente é um **código fechado**, sem texto livre, que poderia trazer dado de saúde ou de terceiros;
  - a linha do tempo do paciente mostra **só o dia** (fuso `America/Recife`), sem hora: a hora de `ENTROU_NA_FILA` revelaria a `data_entrada_fila` e a ordem de chegada;
  - o motivo da reclassificação (texto livre da equipe) **não aparece no painel**, só no detalhe, que é auditado.
- **Auditoria das leituras da equipe** (`CONSULTAR_PAINEL`, `CONSULTAR_SOLICITACAO`, `CONSULTAR_AGENDAMENTOS`, `CONSULTAR_VAGAS`) guarda ator, entidade e filtros, sem nome, CPF nem respostas dos critérios. A agenda do dia mostra o nome abreviado e não traz CPF.
- **Sem dados de terceiros:** o histórico familiar é guardado só como a resposta do paciente ao critério. O sistema nunca cadastra parentes, nunca liga o cadastro de um paciente ao de outro e nunca guarda nome, CPF ou qualquer dado pessoal dos parentes ([ADR-030](../decisions/ADR-030-historico-familiar-como-criterio.md)).
- **Consentimento por finalidade:** `AGENDAMENTO` (obrigatório para usar o serviço) e `LEMBRETE_EMAIL` (opcional), com versão do termo e data; revogável a qualquer momento (RN-009).
- **Mascaramento:** CPF e cartão do SUS mascarados nas interfaces e nas respostas da API, exceto para o próprio titular quando necessário.
- **Separação de visão:** o paciente não vê nada sobre outros pacientes, nem a posição, o tamanho da fila, a nota ou os pontos (RN-007). A equipe vê só as filas do seu escopo ([ADR-025](../decisions/ADR-025-escopo-por-fila.md)).
- **E-mails mínimos:** o e-mail avisa que há uma novidade e leva ao site; não contém especialidade, classificação nem CPF *(proposta)*.
- **Logs sem dados pessoais:** os logs da aplicação usam IDs, nunca nome, CPF ou corpo de requisição. Erros inesperados (API e Worker) registram só o tipo da exceção e o SQLSTATE, porque a mensagem do Postgres pode repetir valores, como um CPF duplicado.
- **Auditoria minimizada:** `dados_antes` e `dados_depois` guardam só os campos alterados de estado, não cópias completas do registro.

## Retenção *(a definir com a UPE)*

| Dado | Proposta para discussão |
| --- | --- |
| Conta e solicitações ativas | Enquanto o paciente usar o serviço |
| Solicitações encerradas | Prazo definido pela política da instituição |
| Auditoria | Prazo definido pela política da instituição |
| `tentativa_login` | 24 horas *(proposta)* |
| `sessao_refresh` | Até vencer *(proposta)* |

O job `limpar_dados_de_autenticacao` do Worker apaga as duas tabelas conforme a proposta acima e roda de hora em hora (`WORKER_INTERVALO_RETENCAO_S`).
| Backups | Rotação com a última cópia diária de 7 dias *(exemplo)* |

## Direitos do titular

O MVP cobre consultar os próprios dados, revogar consentimentos e acompanhar o uso dos dados (status e avisos). Exportação e exclusão de conta ficam registradas como evolução futura.

## Dados sintéticos

- O script de carga (seed) gera nomes, CPFs válidos porém fictícios e históricos plausíveis.
- Nenhum print, apresentação ou relatório usa dados de pessoas reais, incluindo os próprios integrantes.
