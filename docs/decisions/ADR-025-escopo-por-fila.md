# 025 — Escopo da equipe por fila

- **Status:** Aceito
- **Data:** 2026-10-15
- **Substitui:** [ADR-023](ADR-023-escopo-todas-as-unidades.md)

## Contexto

O [ADR-023](ADR-023-escopo-todas-as-unidades.md) deixou provisoriamente a equipe ver todas as unidades (**ABERTO-3**). Na reunião de 15/10/2026, a UPE respondeu que o atendente trabalha em filas específicas (por exemplo, só a dermatologia do HUOC), enquanto a gestão acompanha um hospital ou a central inteira. Ver todas as filas também facilita o operador "furar a fila" de um conhecido.

## Decisão

- O escopo da equipe é um **conjunto de filas**:
  - **ATENDENTE:** vê e opera só as filas atribuídas a ele em `usuario_fila`. Sem atribuição, não vê nenhuma.
  - **GESTOR:** vê as filas das unidades atribuídas em `usuario_unidade`. Gestor sem nenhuma linha nessa tabela vê a central inteira.
  - **ADMIN:** vê todas as filas.
- Usuário `SUSPENSO` ([ADR-028](ADR-028-suspensao-de-acesso.md)) não tem escopo.
- O escopo vem dos dados, não de configuração: a flag `ESCOPO_POR_UNIDADE` deixa de existir.

## Ponto único de troca

- Regra: `calcular_escopo()` em `app/dominio/acesso.py`. Falha fechada: papel desconhecido, suspenso ou sem atribuição devolve conjunto vazio.
- Dependência da API: `escopo_da_equipe()` em `app/api/deps.py`, que lê as atribuições e devolve os `fila_id` permitidos. Toda rota da equipe filtra por `fila_id IN escopo` dentro da query.

## Alternativas consideradas

- **Manter "todas as unidades":** contraria a resposta da UPE e amplia o risco de favorecimento.
- **Escopo por unidade para todos os papéis:** largo demais para o atendente, que trabalha em filas específicas.
- **Escopo por especialidade:** a mesma especialidade tem filas diferentes, com equipes diferentes ([ADR-027](ADR-027-fila-como-entidade.md)).

## Consequências

- O atendente só enxerga e altera solicitações das suas filas, o que reduz a exposição de dados (AM-007) e o favorecimento (AM-016 no [modelo de ameaças](../security/threat-model.md)).
- A tela de administração precisa atribuir filas a atendentes e unidades a gestores.
- O banco **não** garante que só ATENDENTE apareça em `usuario_fila` nem que só GESTOR apareça em `usuario_unidade`. Por enquanto, o domínio ignora linhas de outros papéis. A futura tela de administração deve validar isso ao gravar.
