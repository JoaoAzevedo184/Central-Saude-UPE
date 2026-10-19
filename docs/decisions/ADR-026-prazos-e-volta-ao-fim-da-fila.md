# 026 — Prazo de confirmação, tolerância de atraso e volta ao fim da fila

- **Status:** Aceito
- **Data:** 2026-10-15

## Contexto

Faltavam três respostas da UPE: quanto tempo o paciente tem para confirmar uma vaga, quanto atraso é tolerado no dia da consulta e o que acontece com a solicitação depois de uma falta (**ABERTO-4**). Na reunião de 15/10/2026, a UPE definiu as três.

## Decisão

- **Prazo de confirmação:** o paciente tem até **2 dias** (48 horas) para confirmar a vaga proposta. O prazo é configurável por fila (`fila.prazo_confirmacao_horas`, padrão 48).
- **Proposta sem confirmação:** a proposta expira e a solicitação volta para o **fim da fila**.
- **Tolerância de atraso:** no dia da consulta, o paciente pode chegar até **1 hora** depois do horário (`fila.tolerancia_atraso_min`, padrão 60). Depois disso, a equipe pode registrar `FALTOU`, e a solicitação volta para o **fim da fila**.
- **Fim da fila** significa uma nova hora de chegada: `data_entrada_fila` recebe o horário atual. A solicitação mantém o risco e a nota, então só fica atrás de quem tem o mesmo risco e a mesma nota.
- O paciente recebe o **motivo** da volta ("você não confirmou a vaga no prazo", "você não compareceu à consulta"), nunca a posição ([ADR-007](ADR-007-paciente-ve-status.md)).

## Ponto único de troca

Funções em `app/dominio/`:

- `calcular_expira_em()` (`agendamento/prazos.py`): o menor entre o prazo da fila e o horário da vaga menos a antecedência mínima (RN-008). Ver também a janela mínima do [ADR-021](ADR-021-matching-automatico.md).
- `pode_marcar_falta()` (`agendamento/prazos.py`): a falta só pode ser registrada depois de `inicio da vaga + tolerância`.
- `reentrar_no_fim_da_fila()` (`solicitacao.py`): volta para `NA_FILA` com nova `data_entrada_fila` e gera o evento `REENTROU_NA_FILA`, visível ao paciente. Os motivos e os textos são uma lista fechada, sem texto livre.

## Alternativas consideradas

- **Manter a posição original depois da expiração ou da falta:** quem não responde ocuparia o topo da fila indefinidamente.
- **Encerrar a solicitação na falta:** obrigaria um novo encaminhamento; a UPE preferiu que o paciente volte para o fim da fila.
- **Limite de faltas:** a UPE não pediu. Fica fora.

## Consequências

- O prazo e a tolerância mudam por fila, sem deploy.
- A linha do tempo do paciente (`historico_solicitacao`) registra a volta à fila com o motivo.
- O job de expiração (UC-006) e o registro de falta (UC-008) usam essas funções.
