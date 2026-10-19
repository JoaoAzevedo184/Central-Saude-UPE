# 027 — A fila é uma entidade própria

- **Status:** Aceito
- **Data:** 2026-10-15

## Contexto

O modelo anterior tratava a fila como "uma especialidade numa unidade" (`unidade_especialidade`). A UPE mostrou que uma especialidade tem várias filas: a dermatologia do HUOC tem uma fila clínica e uma cirúrgica, com pacientes e critérios diferentes. Cada fila também tem público próprio: a laqueadura é para mulheres a partir de 18 anos, e a mamografia de rastreamento, para mulheres a partir de 40.

## Decisão

- A tabela `fila` passa a existir, com:
  - unidade e especialidade;
  - nome, único na unidade;
  - descrição para o paciente (`descricao_paciente`): para que serve e quem pode entrar;
  - regras de elegibilidade: `sexo_elegivel`, `idade_minima` e `idade_maxima` (nulo = sem restrição);
  - prazo de confirmação e tolerância de atraso ([ADR-026](ADR-026-prazos-e-volta-ao-fim-da-fila.md));
  - protocolo de critérios ([ADR-024](ADR-024-protocolo-por-fila.md)).
- A solicitação e a agenda apontam para a fila (`fila_id`), que já define unidade e especialidade. As colunas `especialidade_id` e `unidade_preferida_id` saem da solicitação.
- A tabela `unidade_especialidade` deixa de existir.
- A elegibilidade é verificada por `verificar_elegibilidade()` em `app/dominio/fila/elegibilidade.py`:
  - fila sem restrição aceita qualquer paciente;
  - paciente sem sexo ou sem data de nascimento é inelegível para uma fila que restringe esses dados (falha fechada);
  - a idade é contada em anos completos, na data de hoje em `America/Recife`, com limites inclusivos.

## Alternativas consideradas

- **Manter `unidade_especialidade` com um campo "subtipo":** a fila precisa de critérios, elegibilidade e prazos próprios, o que faria do subtipo uma fila disfarçada.
- **Elegibilidade só na tela:** o servidor precisa recusar a entrada, senão a regra é contornável.

## Consequências

- O paciente escolhe a fila (com a descrição em linguagem simples), e não a unidade ou a especialidade.
- O cadastro do paciente passa a ter `sexo` e `municipio`, só para elegibilidade e direcionamento ([proteção de dados](../security/data-protection.md)).
- A tela de administração cadastra filas, elegibilidade e prazos.
