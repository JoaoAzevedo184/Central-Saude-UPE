# Proteção de dados

> Este projeto é um protótipo acadêmico e usa **somente dados sintéticos**. As medidas abaixo descrevem como o sistema foi desenhado para tratar dados reais. Elas não substituem uma avaliação jurídica nem um Relatório de Impacto à Proteção de Dados, que seriam necessários antes de qualquer uso real.

## Inventário de dados pessoais

| Dado | Onde | Finalidade | Sensível? | Exibição |
| --- | --- | --- | --- | --- |
| Nome | `paciente` | Identificar o paciente nas telas e avisos | Não | Completo para o próprio paciente; abreviado na fila da equipe |
| CPF | `paciente` | Identificação única e login | Não | Mascarado (`***.482.***-10`) em todas as telas |
| Cartão do SUS | `paciente` | Vínculo com o SUS e com a regulação | Não | Mascarado |
| Data de nascimento | `paciente` | Prioridade legal por idade | Não | Só para o próprio paciente e a equipe |
| Celular, e-mail | `paciente`, `usuario` | Avisos | Não | Só para o próprio paciente |
| Especialidade solicitada | `solicitacao` | Fila e agendamento | **Sim** (revela condição de saúde) | Paciente e equipe |
| Classificação de risco | `solicitacao` | Ordem da fila | **Sim** | Só a equipe |
| Prioridade legal (gestação, deficiência, idade) | `solicitacao` | Ordem da fila | **Sim** | Só a equipe |
| IP e ações | `auditoria` | Rastreabilidade e segurança | Não | Só o admin |

O sistema **não** guarda diagnóstico, prontuário, resultados de exames nem qualquer dado clínico além do necessário para agendar.

## Princípios aplicados

- **Minimização:** cada campo só existe se um fluxo usa. Campos novos com dado pessoal precisam aparecer nesta tabela no mesmo pull request.
- **Consentimento por finalidade:** `AGENDAMENTO` (obrigatório para usar o serviço) e `LEMBRETE_EMAIL` (opcional), com versão do termo e data; revogável a qualquer momento (RN-009).
- **Mascaramento:** CPF e cartão do SUS mascarados nas interfaces e nas respostas da API, exceto para o próprio titular quando necessário.
- **Separação de visão:** o paciente não vê nada sobre outros pacientes, nem a posição na fila (RN-007).
- **E-mails mínimos:** o e-mail avisa que há uma novidade e leva ao site; não contém especialidade, classificação nem CPF *(proposta)*.
- **Logs sem dados pessoais:** os logs da aplicação usam IDs, nunca nome, CPF ou corpo de requisição.
- **Auditoria minimizada:** `dados_antes` e `dados_depois` guardam só os campos alterados de estado, não cópias completas do registro.

## Retenção *(a definir com a UPE)*

| Dado | Proposta para discussão |
| --- | --- |
| Conta e solicitações ativas | Enquanto o paciente usar o serviço |
| Solicitações encerradas | Prazo definido pela política da instituição |
| Auditoria | Prazo definido pela política da instituição |
| Backups | Rotação com a última cópia diária de 7 dias *(exemplo)* |

## Direitos do titular

O MVP cobre consultar os próprios dados, revogar consentimentos e acompanhar o uso dos dados (status e avisos). Exportação e exclusão de conta ficam registradas como evolução futura.

## Dados sintéticos

- O script de carga (seed) gera nomes, CPFs válidos porém fictícios e históricos plausíveis.
- Nenhum print, apresentação ou relatório usa dados de pessoas reais, incluindo os próprios integrantes.
