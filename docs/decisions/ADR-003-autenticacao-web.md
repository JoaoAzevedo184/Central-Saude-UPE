# 003 — Autenticação web com cookie e proteção CSRF

- **Status:** Aceito
- **Data:** 2026-10-12

## Contexto

O sistema lida com dados de saúde. Guardar tokens em `localStorage` deixa o token acessível a qualquer script injetado na página (XSS). Ao mesmo tempo, o app mobile futuro não usa cookies de navegador.

## Decisão

- O **refresh token** vai num cookie `httpOnly`, `Secure` e `SameSite`, inacessível ao JavaScript da página.
- Toda requisição que altera estado envia um **header customizado** (`X-CSRF-Token`), que outro site não consegue forjar.
- O serviço de tokens é escrito para aceitar também `Authorization: Bearer`, que será habilitado quando o mobile entrar ([ADR-002](ADR-002-web-primeiro.md)).

## Detalhes de implementação

Não mudam a decisão; registram como ficou. Rotas, cookies e códigos de erro: [API](../architecture/api-design.md).

- **Access token** em cookie `httpOnly` (JWT HS256, 15 min). Nenhum token vai no corpo da resposta.
- **Refresh token** opaco, guardado só como hash SHA-256, com **rotação por família**: cada renovação revoga o token usado e emite outro. Reapresentar um token já substituído indica roubo e revoga a família inteira. Há uma **tolerância de 10 s** (`REFRESH_TOLERANCIA_S`) para duas abas renovarem juntas.
- **Claim `sid`** (a família) no access token: logout, reuso do refresh e suspensão ([ADR-028](ADR-028-suspensao-de-acesso.md)) cortam o acesso na hora, sem esperar o token vencer.
- **CSRF por double-submit:** o header `X-CSRF-Token` tem de ser igual ao cookie `csrf_token`. O valor não é assinado, então a premissa é não existirem subdomínios não confiáveis (AM-002).
- **Senhas** com Argon2id.
- **Login** por CPF (paciente) ou e-mail (equipe).
- **Bearer:** o serviço de tokens já aceita o token fora de cookie, mas a API ainda não lê `Authorization: Bearer`; entra com o mobile.

## Consequências

- Frontend e API precisam estar no mesmo site (garantido pelo Nginx servindo ambos, [ADR-012](ADR-012-implantacao.md)), senão o cookie não é enviado.
- Testes de integração precisam cobrir: requisição sem header CSRF é rejeitada, refresh com cookie expirado é rejeitado, logout invalida o refresh token.
