# 002 — Web responsivo primeiro, mobile depois

- **Status:** Aceito
- **Data:** 2026-10-12

> **Nota (2026-10-21):** o grupo descartou o app mobile ([ADR-015](ADR-015-app-mobile.md)). O site responsivo, mobile-first, é o único cliente do paciente. As linhas abaixo sobre o app React Native, o push e o segundo cliente ficam como histórico.

## Contexto

O planejamento inicial previa web e app mobile. Com o prazo do MVP em novembro, fazer os dois dividiria a equipe. O paciente acessa principalmente pelo celular, então a experiência mobile não pode ficar de fora.

## Decisão

- O MVP é **só web, com layout responsivo** pensado primeiro para o celular.
- O app React Native entra depois e consome **a mesma API `/api/v1`**, sem um backend específico para ele (BFF).
- Notificações push chegam junto com o app, como mais uma implementação de `CanalNotificacao` ([ADR-010](ADR-010-integracoes-por-interface.md)).

## Consequências

- A API não pode assumir que o cliente é um navegador. Por isso a autenticação já nasce preparada para Bearer, além do cookie ([ADR-003](ADR-003-autenticacao-web.md)).
- Respostas da API devem ser genéricas o suficiente para servir aos dois clientes, sem formatação feita sob medida para uma tela.
