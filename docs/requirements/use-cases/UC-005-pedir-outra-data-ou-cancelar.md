# UC-005 — Pedir outra data ou cancelar

| | |
| --- | --- |
| **Ator principal** | Paciente |
| **Objetivo** | Recusar a data proposta ou desistir do atendimento, liberando a vaga |
| **Requisitos** | RF-013, RF-014, RF-016, RF-018 |
| **Regras** | RN-004, RN-005, RN-010, RN-011, RN-014, RN-016, RN-020 |

## Pré-condições

- Paciente autenticado.
- Existe um agendamento `PROPOSTO` (pedir outra data) ou `PROPOSTO`/`CONFIRMADO` (cancelar) de uma solicitação do próprio paciente.

## Fluxo principal — pedir outra data ("esta data não serve")

Rota: `POST /api/v1/agendamentos/{id}/recusar`. Só para agendamento `PROPOSTO`, dentro do prazo (`expira_em`).

1. Na proposta, o paciente escolhe "Esta data não serve".
2. O sistema explica que ele continua na fila e receberá outra vaga.
3. Numa única transação, o sistema:
   - trava a solicitação e o agendamento;
   - muda o agendamento para `CANCELADO`, motivo `RECUSADO_PELO_PACIENTE`, e grava `respondido_em`;
   - devolve a solicitação para `NA_FILA` e registra o evento `RECUSADA` na linha do tempo;
   - aplica a regra da recusa (abaixo);
   - registra a auditoria e grava o evento `PROPOSTA_RECUSADA` na outbox.
4. A vaga fica livre e volta a ser oferecida ([UC-003](UC-003-propor-vaga.md)), nunca à mesma solicitação.

**Regra da recusa** *(proposta; validar com o grupo e a UPE)*:
- configurável por `RECUSAS_MANTENDO_POSICAO` (padrão 1);
- contam só as recusas **desde a última entrada na fila** (`data_entrada_fila`). Voltar ao fim da fila, por recusa, expiração ou falta, zera a contagem;
- enquanto a contagem for menor que o limite, a recusa **mantém a posição** (`data_entrada_fila` não muda);
- a recusa seguinte manda a solicitação para o **fim da fila** com `reentrar_no_fim_da_fila()` (RN-014). A linha do tempo ganha `RECUSADA` e, logo depois, `REENTROU_NA_FILA`, com o motivo "Você recusou outras datas".

> **Pendência (decisão do grupo e da UPE):** "pedir outra data" com o agendamento já `CONFIRMADO` não está implementado. A rota de recusa só aceita `PROPOSTO`. Por ora, quem já confirmou e precisa de outra data **cancela** (fluxo A1) e abre uma nova solicitação ([UC-002](UC-002-solicitar-atendimento.md)).

## Fluxo alternativo — A1: cancelar ("não vou precisar")

Rota: `POST /api/v1/solicitacoes/{id}/cancelar`, com `motivo_codigo` da lista fechada.

1. O paciente escolhe "Não vou precisar".
2. O sistema pede confirmação, explicando que o pedido será encerrado.
3. O paciente confirma e escolhe o motivo.
4. Numa única transação, o sistema:
   - trava a solicitação e, depois, o agendamento ativo (`PROPOSTO` ou `CONFIRMADO`);
   - confere que o **início da vaga ainda não chegou**;
   - muda o agendamento para `CANCELADO`, motivo `CANCELADO_PELO_PACIENTE`;
   - muda a solicitação para `CANCELADA`, com o `motivo_codigo`, e registra o evento `CANCELADA`;
   - registra a auditoria dos dois e grava o evento `AGENDAMENTO_CANCELADO` na outbox.
5. A vaga fica livre e o Worker a oferece ao próximo da fila (**reaproveitamento**, RN-005), **se ainda couber a janela mínima** para o paciente responder (RN-016). Se não couber, ela aparece no painel de vagas como "livre sem proposta".

> O aviso do cancelamento aparece no site com o detalhe. O e-mail, se houver, usa texto neutro ("Há uma atualização no seu atendimento. Para ver os detalhes, entre na Central.") e não menciona cancelamento (AM-008).

> O cancelamento sem proposta (`EM_ANALISE` e `NA_FILA`) usa a mesma rota e está em [UC-002](UC-002-solicitar-atendimento.md); nesse caso a outbox recebe `SOLICITACAO_CANCELADA`.

## Exceções

- **E1 — Agendamento já em estado final** (expirado, cancelado, realizado): `409` `/problemas/transicao-invalida`.
- **E2 — Recurso de outro paciente:** `404`.
- **E3 — Cancelamento depois do início da vaga:** `409` `/problemas/transicao-invalida`, e nada muda. Antes do início, o cancelamento pelo site é sempre aceito; não há antecedência mínima.
- **E4 — Recusa depois do prazo:** `409` `/problemas/proposta-expirada`, mesmo antes de o Worker expirar a proposta.
- **E5 — Solicitação `EM_PROPOSTA` ou `AGENDADA` sem agendamento ativo** (estado inconsistente): `409`, e nada muda.

## Pós-condições

- Outra data: agendamento `CANCELADO`, solicitação `NA_FILA` (na mesma posição ou no fim da fila), vaga livre.
- Cancelar: agendamento `CANCELADO`, solicitação `CANCELADA`, vaga livre.

## Critérios de aceite

- **Dado** a primeira recusa de uma proposta, **quando** o paciente pede outra data, **então** o agendamento fica `CANCELADO` com `RECUSADO_PELO_PACIENTE`, a solicitação volta para `NA_FILA` e a posição no painel não muda (`test_uc005_primeira_recusa_mantem_a_posicao`).
- **Dado** uma segunda recusa desde a entrada na fila, **quando** o paciente pede outra data, **então** a solicitação vai para o fim da fila com o motivo visível (`test_uc005_segunda_recusa_manda_para_o_fim`).
- **Dado** recusa, recusa (fim da fila) e recusa, **quando** a terceira acontece, **então** ela mantém a posição, porque a contagem zerou na volta ao fim (`test_uc005_recusa_conta_so_desde_a_ultima_entrada_na_fila`).
- **Dado** eventos no mesmo instante, **quando** se lê a linha do tempo, **então** `RECUSADA` aparece antes de `REENTROU_NA_FILA` (`test_uc005_linha_do_tempo_recusada_antes_de_reentrou`).
- **Dado** uma recusa, **quando** o Worker propõe de novo, **então** a mesma vaga nunca volta para a mesma solicitação (`test_uc003_nunca_reoferece_a_mesma_vaga_depois_de_recusa`).
- **Dado** uma proposta vencida, **quando** o paciente recusa, **então** a resposta é `409` (`test_uc005_recusar_depois_do_prazo_responde_409`).
- **Dado** uma proposta, **quando** o paciente cancela, **então** o agendamento fica `CANCELADO` e a solicitação `CANCELADA` (`test_uc005_cancelar_com_proposta_pendente`).
- **Dado** o paciente A com consulta confirmada, **quando** A cancela, **então** o Worker oferece a mesma vaga ao paciente B, sem atualizar a tabela de vagas (`test_uc005_rn005_reaproveitamento_cancelada_vai_para_o_proximo`).
- **Dado** uma consulta cujo início já chegou, **quando** o paciente cancela, **então** a resposta é `409` e nada muda (`test_uc005_cancelar_depois_do_inicio_da_vaga_responde_409`).
- **Dado** uma proposta de outro paciente, **quando** alguém tenta recusar pelo ID, **então** a resposta é `404` (`test_am001_confirmar_ou_recusar_proposta_de_outro_paciente_responde_404`).

## Segurança

- Verificação de dono dentro da query em toda rota com ID (AM-001 no [modelo de ameaças](../../security/threat-model.md)).
- Header CSRF obrigatório (AM-002, `test_am002_confirmar_ou_recusar_sem_csrf_responde_403`).
- O motivo do cancelamento é código de lista fechada, sem texto livre ([proteção de dados](../../security/data-protection.md)).
