# 029 — Overbooking por fila como vagas extras

- **Status:** Proposto (depois do MVP)
- **Data:** 2026-10-15

## Contexto

Na reunião de 15/10/2026, a UPE comentou que alguns serviços têm taxa de falta conhecida e compensam com encaixes. O [ADR-004](ADR-004-ocupacao-da-vaga.md) garante, por índice único parcial, que cada vaga tem no máximo um agendamento ativo. Permitir dois agendamentos na mesma vaga quebraria essa garantia.

## Decisão (proposta)

- O overbooking é configurado por fila como um **percentual**.
- Ao gerar as vagas de uma agenda, o sistema cria **vagas extras** (por exemplo, 10% a mais), marcadas como extras, cada uma com o seu próprio agendamento.
- O índice do ADR-004 **não muda**: cada vaga, normal ou extra, continua com no máximo um agendamento ativo.
- Nada disso entra no MVP. Este ADR só registra a direção, sem código nem migração.

## Alternativas consideradas

- **Permitir mais de um agendamento por vaga:** exige trocar o índice único por contagem, com risco de corrida e de perder a garantia do ADR-004.
- **Encaixe manual fora do sistema:** não aparece nos indicadores.

## Consequências

- Quando for implementado: uma coluna de percentual na `fila`, uma marca de vaga extra e a geração das vagas extras na agenda.
- Os indicadores de falta passam a ser a base para calibrar o percentual.
