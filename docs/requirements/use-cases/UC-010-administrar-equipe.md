# UC-010 — Administrar a equipe

| | |
| --- | --- |
| **Ator principal** | Admin |
| **Objetivo** | Criar as contas da equipe, controlar o acesso e o escopo de cada pessoa e permitir que ela troque a senha temporária |
| **Requisitos** | RF-033, RF-035, RF-036 |
| **Regras** | RN-022, RN-010 |

> **Escopo desta versão.** Este caso de uso detalha a parte **implementada**: contas, senhas, atribuições e suspensão. Unidades, especialidades, filas (protocolo e elegibilidade), agendas e bloqueio de vagas (RF-005 a RF-007 e RF-022) também são do UC-010, mas continuam *propostas* (veja a [API](../../architecture/api-design.md#administração)) e serão detalhadas quando forem implementadas.

## Pré-condições

- Admin autenticado, ativo ([ADR-028](../../decisions/ADR-028-suspensao-de-acesso.md)) e sem senha temporária pendente.
- Toda escrita leva o header `X-CSRF-Token`.

## Fluxo principal — criar uma conta da equipe

1. O admin informa e-mail e papel (`ATENDENTE`, `GESTOR` ou `ADMIN`) (`POST /api/v1/admin/usuarios`). Para um gestor, informa as unidades, ou confirma a visão da central inteira (`confirmar_visao_central: true`).
2. O sistema valida (o domínio exige a confirmação explícita para gestor sem unidade), gera uma senha temporária forte e grava a conta com `senha_temporaria = true`, só com o hash da senha.
3. O sistema grava a auditoria `CRIAR_USUARIO` (papel e unidades, sem senha nem e-mail) e responde `201` com `{id, senha_temporaria}`. **A senha aparece só nesta resposta**; ela nunca vai para log.
4. O admin entrega a senha à pessoa.
5. A pessoa entra com a senha temporária. O login responde `trocar_senha: true` e a API recusa tudo (`403` `troca-de-senha-obrigatoria`), menos `/me`, `/auth/trocar-senha`, `/auth/logout` e `/auth/refresh` (RN-022).
6. A pessoa troca a senha (`POST /api/v1/auth/trocar-senha` com `{senha_atual, senha_nova}`). O sistema grava a nova senha, zera `senha_temporaria`, **revoga as outras sessões**, audita `TROCAR_SENHA` e responde `204`. A partir daí a conta usa a API normalmente.

## Fluxos alternativos

- **A1 — Atribuir filas a um atendente** (`PUT /admin/usuarios/{id}/filas`): substitui as filas; auditoria `ATRIBUIR_FILAS` com antes e depois.
- **A2 — Atribuir unidades a um gestor** (`PUT /admin/usuarios/{id}/unidades`): substitui as unidades. Lista vazia faz o gestor ver a central inteira e exige `confirmar_visao_central: true`; a auditoria marca `visao_central`.
- **A3 — Redefinir a senha** (`POST /admin/usuarios/{id}/redefinir-senha`): só de atendente e gestor. O sistema gera outra senha temporária (devolvida uma vez), **revoga todas as sessões** da conta e liga a troca obrigatória de novo. A senha de um admin é redefinida só pelo terminal do servidor (`python -m app.infra.admin redefinir-senha --email <email>`).
- **A4 — Suspender e reativar** (`POST /admin/usuarios/{id}/suspender` com `{motivo}` e `/reativar`): suspender revoga todas as sessões; a conta nunca é apagada (ADR-028).
- **A5 — Listar** contas da equipe e filas (`GET /admin/usuarios`, `GET /admin/filas`), com filas e unidades atribuídas e `senha_temporaria`, sem nunca trazer hash nem senha.

## Exceções

- **E1 — Papel diferente de ADMIN:** `403`. Sem sessão, `401`. Sem CSRF, `403`. Senha temporária pendente, `403` `troca-de-senha-obrigatoria`.
- **E2 — E-mail já cadastrado:** `409` `email-ja-cadastrado`.
- **E3 — Gestor sem unidade, sem confirmar a visão central:** `409` `visao-central-nao-confirmada`.
- **E4 — Unidade ou fila inexistente na atribuição:** `422`. Papel no corpo, ou campo fora do schema: `422`.
- **E5 — Alvo inadequado:** atribuir fila a quem não é atendente, unidade a quem não é gestor, redefinir senha de admin, suspender paciente, a si mesmo ou o último admin ativo: `409` `operacao-nao-permitida`. Suspender conta já suspensa (ou reativar conta ativa): `409` `transicao-invalida`.
- **E6 — Usuário inexistente:** `404`.
- **E7 — Troca de senha inválida:** nova senha com menos de 10 caracteres, igual à atual, ou senha atual errada: `422`, sem alterar nada. Excesso de erros: `429` com `Retry-After`, sem revogar sessão (AM-020). Conta suspensa durante a sessão: `401`.

## Pós-condições

- Conta criada com `senha_temporaria = true`, ou senha trocada com `senha_temporaria = false`.
- Toda escrita tem uma linha em `auditoria`, com o admin como ator, **sem senha, sem hash e sem e-mail completo**.

## Critérios de aceite


- **Dado** que só o admin administra, **quando** outro papel ou ninguém chama `/admin`, **então** a resposta é `403` ou `401` (`test_rf035_so_admin_acessa_a_administracao`, `test_rf035_sem_sessao_retorna_401`); as rotas antigas de suspensão respondem `404` (`test_rf035_rotas_antigas_de_suspensao_respondem_404`).
- **Dado** a criação de uma conta, **quando** o admin a cria, **então** a senha temporária vem só nesta resposta, sem cache e sem aparecer em log (`test_rf036_cria_conta_com_senha_temporaria_devolvida_uma_vez`, `test_rf036_resposta_da_senha_nao_fica_em_cache`).
- **Dado** um e-mail já cadastrado, **quando** o admin cria a conta, **então** `409` (`test_rf036_email_duplicado_retorna_409`); entradas inválidas, `422` (`test_rf036_criacao_invalida_retorna_422`, `test_rf036_gestor_com_unidade_inexistente_retorna_422`).
- **Dado** um gestor sem unidade, **quando** o admin cria ou atribui sem confirmar, **então** `409`; com a confirmação, o gestor passa a ver a central (`test_rf036_gestor_sem_unidade_exige_confirmar_a_visao_central`, `test_adr025_visao_central_exige_confirmacao_explicita`).
- **Dado** uma conta com senha temporária, **quando** ela faz login, **então** o login traz `trocar_senha: true`; uma conta comum, não (`test_rf036_login_de_senha_temporaria_traz_trocar_senha`, `test_rf036_login_comum_nao_traz_trocar_senha`, `test_rf036_me_traz_trocar_senha_so_com_senha_temporaria`).
- **Dado** a senha temporária, **quando** a conta chama qualquer outra rota, **então** `403` `troca-de-senha-obrigatoria`; `/me`, `refresh` e `logout` continuam funcionando (`test_rf036_senha_temporaria_bloqueia_as_outras_rotas`, `test_rf036_senha_temporaria_ainda_acessa_me_refresh_e_logout`). Toda rota autenticada declara esse `403` no OpenAPI (`test_toda_rota_autenticada_declara_o_403_de_troca_de_senha_obrigatoria`).
- **Dado** a troca de senha, **quando** a pessoa a conclui, **então** o acesso é liberado e as outras sessões caem (`test_rf036_troca_de_senha_libera_o_acesso_e_revoga_as_outras_sessoes`); entrada inválida muda nada (`test_rf036_troca_invalida_retorna_422_e_nao_muda_nada`); sem sessão ou CSRF, é recusada (`test_rf036_trocar_senha_exige_sessao_e_csrf`).
- **Dado** erros repetidos na troca de senha, **quando** o limite é passado, **então** `429` sem revogar nada, e o login não fica bloqueado (`test_am020_erros_na_troca_de_senha_bloqueiam_sem_revogar_nada`, `test_am020_troca_de_senha_bloqueada_nao_bloqueia_o_login`); conta suspensa na sessão recebe `401` (`test_am020_trocar_senha_de_conta_suspensa_durante_a_sessao_retorna_401`).
- **Dado** a redefinição, **quando** o admin redefine a senha de atendente ou gestor, **então** as sessões caem e a troca volta a ser obrigatória; a de admin é `409` (`test_rf036_redefinir_senha_revoga_sessoes_e_exige_nova_troca`, `test_rf036_redefinir_senha_so_de_atendente_e_gestor`).
- **Dado** as atribuições, **quando** o admin as grava, **então** só atendente recebe fila e só gestor recebe unidade, e a lista é substituída; paciente como alvo, `409` (`test_rf035_atribui_filas_so_ao_atendente_e_substitui`, `test_rf035_atribui_unidades_so_ao_gestor`, `test_rf035_atribuicoes_a_paciente_retornam_409`, `test_rf035_papel_no_corpo_da_atribuicao_retorna_422`).
- **Dado** a suspensão sob `/admin`, **quando** o admin suspende uma conta, **então** as sessões caem na hora (`test_adr028_suspender_sob_admin_revoga_sessoes`).
- **Dado** qualquer escrita, **quando** a auditoria é lida, **então** ela nunca guarda senha nem hash (`test_rf036_auditoria_nunca_guarda_senha_nem_hash`).
- **Dado** as listagens, **quando** o admin as consulta, **então** vêm só a equipe, com filtros e atribuições, e as filas com unidade e especialidade (`test_rf035_lista_so_a_equipe_com_filtros_e_atribuicoes`, `test_rf035_lista_filas_com_unidade_e_especialidade`).

## Segurança

- Só ADMIN, em toda a rota (`exige_papel("ADMIN")`); `Cache-Control: no-store` em `/admin/` ([controle de acesso](../../security/access-control.md)).
- A senha temporária é exposta uma única vez e não tem validade (AM-021); a troca é limitada por tentativas (AM-020); a visão da central exige confirmação (AM-022) — veja o [modelo de ameaças](../../security/threat-model.md).
