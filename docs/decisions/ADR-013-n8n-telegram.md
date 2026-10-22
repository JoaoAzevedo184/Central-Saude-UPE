# 013 — n8n + Telegram como canal de aviso

- **Status:** Descartado
- **Data:** 2026-10-21

## Contexto

O plano previa o Telegram, via n8n, como nova implementação de `CanalNotificacao` ([ADR-010](ADR-010-integracoes-por-interface.md)), depois do fluxo de e-mail estável.

## Decisão

Descartado. A UPE informou em 2026-10-15 que os pacientes não usam Telegram. Os avisos ficam no site e por e-mail.

## Consequências

- `CanalNotificacao` continua como interface; só existem o aviso no site e o e-mail (SMTP).
- RF-026 sai do escopo ([requisitos funcionais](../requirements/functional-requirements.md)).
