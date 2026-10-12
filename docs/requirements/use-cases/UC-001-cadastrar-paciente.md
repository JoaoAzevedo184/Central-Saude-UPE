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
2. O sistema exibe o formulário (nome, CPF, cartão do SUS, data de nascimento, celular, e-mail opcional, senha) e o termo de consentimento com a versão vigente.
3. O paciente preenche os dados, marca o consentimento obrigatório para agendamento e, se quiser, o consentimento opcional para lembretes por e-mail.
4. O sistema valida os dados.
5. O sistema cria o usuário com papel `PACIENTE`, o paciente e os consentimentos marcados, registrando a versão do termo e a data.
6. O sistema registra a ação na auditoria e inicia a sessão.
7. O paciente é levado a "Meus atendimentos".

## Fluxos alternativos

- **A1 — Sem consentimento de lembretes:** no passo 3, o paciente não marca o opcional. A conta é criada só com o consentimento `AGENDAMENTO`; o paciente recebe avisos no site, mas não lembretes por e-mail.

## Exceções

- **E1 — Consentimento obrigatório desmarcado:** o sistema não cria a conta e explica que, sem ele, não é possível agendar.
- **E2 — CPF ou cartão do SUS inválido:** o sistema indica o campo com erro em texto.
- **E3 — CPF ou cartão do SUS já cadastrado:** o sistema mostra uma mensagem genérica ("não foi possível concluir o cadastro; se você já tem conta, entre ou recupere a senha"), sem confirmar que o documento existe.
- **E4 — Senha fraca:** o sistema informa o critério mínimo.

## Pós-condições

- Usuário, paciente e consentimentos gravados; auditoria registrada; sessão iniciada.

## Critérios de aceite

- **Dado** um formulário válido com o consentimento obrigatório marcado, **quando** o paciente envia, **então** a conta é criada com um consentimento `AGENDAMENTO` vigente e a versão do termo registrada.
- **Dado** o consentimento obrigatório desmarcado, **quando** o paciente envia, **então** nenhum registro é criado e a resposta é `422`.
- **Dado** um CPF já cadastrado, **quando** alguém tenta cadastrar de novo, **então** a mensagem não revela que o CPF existe.
- **Dado** o cadastro concluído, **quando** se consulta o banco, **então** a senha só existe como hash.

## Segurança

- Mensagens genéricas para não permitir descobrir quais CPFs têm conta (AM-005 no [modelo de ameaças](../../security/threat-model.md)).
- Limite de tentativas no endpoint de registro (AM-004).
