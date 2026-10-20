# UC-001 — Cadastrar paciente

| | |
| --- | --- |
| **Ator principal** | Paciente (ainda sem conta) |
| **Objetivo** | Criar uma conta para acompanhar e responder aos agendamentos |
| **Requisitos** | RF-001, RF-002 |
| **Regras** | RN-009 |

## Pré-condições

- O paciente tem CPF e cartão do SUS.

## Fluxo principal

1. O paciente abre "Criar conta".
2. O sistema exibe o formulário e o termo de consentimento com a versão vigente (`TERMO_VERSAO_ATUAL`). Campos:
   - nome, CPF e cartão do SUS (CNS), obrigatórios; o CNS tem o dígito verificador validado (definitivo e provisório);
   - data de nascimento, telefone e município, obrigatórios;
   - sexo, opcional (`FEMININO` ou `MASCULINO`);
   - e-mail, opcional;
   - senha, com no mínimo 10 caracteres.
3. O paciente preenche os dados, marca o consentimento obrigatório para agendamento e, se quiser, o consentimento opcional para lembretes por e-mail. O lembrete por e-mail só é aceito se o e-mail foi informado.
4. O sistema valida os dados.
5. O sistema cria o usuário com papel `PACIENTE`, o paciente e os consentimentos marcados, registrando a versão do termo e a data.
6. O sistema registra a ação na auditoria e inicia a sessão.
7. O paciente é levado a "Meus atendimentos".

## Fluxos alternativos

- **A1 — Sem consentimento de lembretes:** no passo 3, o paciente não marca o opcional. A conta é criada só com o consentimento `AGENDAMENTO`; o paciente recebe avisos no site, mas não lembretes por e-mail.

## Exceções

- **E1 — Consentimento obrigatório desmarcado:** o sistema não cria a conta e explica que, sem ele, não é possível agendar.
- **E2 — CPF ou cartão do SUS inválido:** o sistema indica o campo com erro em texto. O mesmo vale para data de nascimento no futuro ou acima de 130 anos e para versão do termo diferente da vigente (`422`).
- **E3 — CPF, cartão do SUS ou e-mail já cadastrado:** o sistema responde `409` com a mensagem única "Não foi possível concluir o cadastro. Se você já tem conta, entre com seu CPF.", sem dizer qual dado repetiu.
- **E4 — Senha fraca:** o sistema informa o critério mínimo (10 caracteres).
- **E5 — Muitas tentativas:** o limite de registros por IP foi atingido; `429` com `Retry-After`.

## Pós-condições

- Usuário, paciente e consentimentos gravados; auditoria registrada; sessão iniciada.

## Critérios de aceite

- **Dado** um formulário válido com o consentimento obrigatório marcado, **quando** o paciente envia, **então** a conta é criada com um consentimento `AGENDAMENTO` vigente e a versão do termo registrada.
  A resposta é `201` e a sessão já fica iniciada (cookies).
- **Dado** o consentimento obrigatório desmarcado, **quando** o paciente envia, **então** nenhum registro é criado e a resposta é `422`.
- **Dado** CPF inválido, CNS inválido, senha curta, data de nascimento no futuro ou acima de 130 anos, ou versão do termo diferente da vigente, **quando** o paciente envia, **então** a resposta é `422` e nada é criado.
- **Dado** um corpo com campo não previsto (`papel`, `situacao`, `classificacao_risco`...), **quando** o paciente envia, **então** a resposta é `422` (AM-013).
- **Dado** o lembrete por e-mail marcado sem e-mail, **quando** o paciente envia, **então** a resposta é `422`.
- **Dado** um CPF, CNS ou e-mail já cadastrado, **quando** alguém tenta cadastrar de novo, **então** a resposta é `409` com a mesma mensagem para os três casos, nenhum registro é criado e nenhum evento vai para a `outbox`.
- **Dado** o limite de registros por IP atingido, **quando** chega mais um, **então** a resposta é `429`.
- **Dado** o cadastro concluído, **quando** se consulta o banco, **então** a auditoria tem a ação `REGISTRO` e a senha só existe como hash Argon2id.

### Critérios de aceite de entrada e sessão (RF-002)

O login, a renovação e a saída não têm caso de uso próprio; seus critérios ficam aqui.

- **Dado** um paciente, **quando** entra com CPF e senha, **então** a resposta é `{papel, expira_em}`, sem token no corpo, e os cookies da sessão são definidos. Um membro da equipe entra com e-mail; o paciente não entra por e-mail.
- **Dado** identificador inexistente, senha errada ou conta suspensa, **quando** alguém tenta entrar, **então** a resposta é `401` com corpo idêntico nos três casos.
- **Dado** o limite de falhas por IP ou por identificador atingido, **quando** chega mais uma tentativa, **então** a resposta é `429`, mesmo com a senha certa.
- **Dado** um login bem-sucedido, **quando** se consulta a auditoria, **então** há a ação `LOGIN`.
- **Dado** um refresh token válido, **quando** a sessão é renovada, **então** o token é trocado por outro da mesma família e o antigo é revogado.
- **Dado** um refresh token já substituído, **quando** é reapresentado depois da tolerância de 10 s, **então** a resposta é `401` e a família inteira é revogada.
- **Dado** um refresh token substituído há menos de 10 s, **quando** é reapresentado (duas abas), **então** a renovação vale e a família não é revogada.
- **Dado** um refresh token vencido, **quando** é usado, **então** a resposta é `401`.
- **Dado** a sessão encerrada no logout, **quando** o access token ainda não venceu e é usado, **então** a resposta é `401`.
- **Dado** o logout, **quando** ele é chamado (com ou sem sessão), **então** a resposta é `204` e os cookies são apagados.
- **Dado** uma escrita sem o header `X-CSRF-Token` igual ao cookie, **quando** chega, **então** a resposta é `403`.

## Segurança

- Mensagens genéricas para não permitir descobrir quais CPFs têm conta (AM-005 no [modelo de ameaças](../../security/threat-model.md)).
- Limite de tentativas no registro, por IP, e no login, por IP e por identificador (AM-004).
- O corpo do registro recusa campos não previstos (AM-013). Contrato da API: [api-design.md](../../architecture/api-design.md).
