# 028 — Acesso de profissional é suspenso, nunca apagado

- **Status:** Aceito
- **Data:** 2026-10-15

## Contexto

Profissionais entram de férias, mudam de setor ou são desligados. Apagar a conta quebraria a auditoria, que aponta para o usuário que agiu (`auditoria.ator_usuario_id`), e o histórico das solicitações. Um campo `ativo` sem data também não diz desde quando nem por quê.

## Decisão

- `usuario.ativo` é substituído por `situacao` (`ATIVO` ou `SUSPENSO`), com `suspenso_em` e `motivo_suspensao`.
- O banco exige `suspenso_em` sempre que a situação for `SUSPENSO`.
- Usuário suspenso:
  - não faz login, e a resposta é a mesma mensagem genérica de credenciais inválidas;
  - não renova o refresh token;
  - não tem escopo de equipe ([ADR-025](ADR-025-escopo-por-fila.md)).
- Contas de usuário não são apagadas. As FKs para `usuario` usam `ON DELETE RESTRICT`.

## Ponto único de troca

`pode_autenticar()` em `app/dominio/acesso.py`. O login, o refresh e `usuario_da_sessao` o chamam.

## Alternativas consideradas

- **Apagar a conta:** quebra a auditoria e o histórico.
- **Apagar e anonimizar o ator na auditoria:** perde a rastreabilidade que a auditoria existe para dar (AM-011).
- **Manter `ativo bool`:** não registra quando nem por quê.

## Consequências

- A auditoria continua apontando para quem agiu, mesmo depois do desligamento.
- A tela de administração ganha "suspender" e "reativar". Reativar volta a situação para `ATIVO`; `suspenso_em` e `motivo_suspensao` ficam como registro da última suspensão.
- Uma sessão já aberta precisa ser encerrada quando o usuário é suspenso. Como ficou: suspender revoga todas as sessões de refresh do usuário, e `usuario_da_sessao` relê a situação e a família da sessão a cada requisição, recusando o access token que ainda não venceu (`401`). Regras da rota em [controle de acesso](../security/access-control.md).
