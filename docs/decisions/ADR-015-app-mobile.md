# 015 — App mobile React Native + push

- **Status:** Descartado
- **Data:** 2026-10-21

## Contexto

O planejamento previa um app React Native depois do MVP, com notificações push como mais uma implementação de `CanalNotificacao` ([ADR-002](ADR-002-web-primeiro.md), [ADR-010](ADR-010-integracoes-por-interface.md)).

## Decisão

Descartado, por decisão do grupo em 2026-10-21. O site responsivo atende o paciente no celular, e o foco é o MVP web. O projeto não terá app nativo nem push.

## Consequências

- O site é **mobile-first**: celular simples, tela pequena e acessibilidade ([PRD](../product/PRD.md), [roadmap](../product/scope-and-roadmap.md)).
- `apps/mobile` não existe e não será criado. RF-027 sai do escopo.
- O Bearer não será ativado ([ADR-003](ADR-003-autenticacao-web.md)).
