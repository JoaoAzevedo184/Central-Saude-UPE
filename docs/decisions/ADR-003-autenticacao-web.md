# 003 — Autenticação web com cookie e proteção CSRF

- **Status:** Aceito
- **Data:** 2026-10-12

## Contexto

O sistema lida com dados de saúde. Guardar tokens em `localStorage` deixa o token acessível a qualquer script injetado na página (XSS). Ao mesmo tempo, o app mobile futuro não usa cookies de navegador.

## Decisão

- O **refresh token** vai num cookie `httpOnly`, `Secure` e `SameSite`, inacessível ao JavaScript da página.
- Toda requisição que altera estado envia um **header customizado** (`X-CSRF-Token`), que outro site não consegue forjar.
- O serviço de tokens é escrito para aceitar também `Authorization: Bearer`, que será habilitado quando o mobile entrar ([ADR-002](ADR-002-web-primeiro.md)).

## Consequências

- Frontend e API precisam estar no mesmo site (garantido pelo Nginx servindo ambos, [ADR-012](ADR-012-implantacao.md)), senão o cookie não é enviado.
- Testes de integração precisam cobrir: requisição sem header CSRF é rejeitada, refresh com cookie expirado é rejeitado, logout invalida o refresh token.
