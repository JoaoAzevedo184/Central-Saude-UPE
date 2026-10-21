# UC-003 — Propor vaga

| | |
| --- | --- |
| **Ator principal** | Sistema (Worker) ([ADR-021](../../decisions/ADR-021-matching-automatico.md)); Atendente em fase futura |
| **Objetivo** | Oferecer uma vaga livre ao próximo paciente elegível da fila |
| **Requisitos** | RF-010, RF-011, RF-016, RF-018, RF-031, RF-032 |
| **Regras** | RN-001, RN-002, RN-003, RN-005, RN-008, RN-010, RN-011, RN-012, RN-015, RN-016, RN-019 |

A proposta é automática e segue a ordem da fila (ADR-021, confirmado pela UPE em 15/10/2026). Os passos da proposta manual pelo atendente ficam marcados como futuros.

## Gatilho

- Uma vaga é criada, desbloqueada ou liberada por cancelamento ou expiração.
- *(Futuro — proposta manual)* O atendente decide propor uma vaga a partir da fila.

## Pré-condições

- Existe pelo menos uma vaga `ATIVA` sem agendamento ativo.
- Existe pelo menos uma solicitação `NA_FILA` na fila da agenda da vaga.

## Fluxo principal

1. *(Automático)* O Worker identifica a vaga livre. *(Futuro — proposta manual)* O atendente abre uma fila do seu escopo e escolhe a vaga.
2. O sistema ordena as solicitações `NA_FILA` da fila da vaga com `ordenar_fila()`: risco, nota e hora de chegada (RN-015).
3. *(Automático)* O sistema escolhe a primeira. *(Futuro — proposta manual)* O atendente escolhe uma solicitação; o sistema mostra a posição dela na ordem calculada.
4. O sistema calcula `expira_em` com `calcular_expira_em()`: o menor entre agora + prazo de confirmação da fila (RN-012) e o horário da vaga menos a antecedência mínima (RN-008).
5. O sistema verifica que sobra pelo menos a janela mínima para o paciente responder (RN-016).
6. Numa única transação, o sistema cria o agendamento `PROPOSTO`, muda a solicitação para `EM_PROPOSTA`, registra o evento `PROPOSTA_ENVIADA` na linha do tempo, a auditoria e o evento na outbox.
7. O Worker processa o evento e avisa o paciente no site e por e-mail.

## Fluxos alternativos

- **A1 — Janela menor que a mínima (RN-016):** no passo 5, `calcular_expira_em()` devolve "não propor", e o sistema não propõe aquela vaga para ninguém da fila. A vaga fica livre e aparece no painel de vagas da equipe como `LIVRE_SEM_PROPOSTA` (candidata a encaixe manual futuro).
- **A2 — Nenhuma solicitação compatível:** a vaga continua livre.
- **A3 — Preferência de turno (RN-019):** se a vaga não bate com o turno preferido do paciente, o sistema passa para a próxima solicitação. Vaga com início antes de 12h (hora de Recife) é `MANHA`; a partir de 12h, `TARDE`; `QUALQUER` aceita as duas.
- **A4 — Vaga já recebida antes:** a mesma vaga nunca é reoferecida à mesma solicitação, depois de recusa ou expiração; o sistema passa para a próxima.
- **A5 — Teto de candidatas:** cada vaga olha só as 50 primeiras solicitações compatíveis da fila (`CANDIDATAS_POR_VAGA`). Se todas já tiverem recebido aquela vaga, ela fica sem proposta nesta rodada e o Worker registra um aviso no log (só o ID da vaga), uma vez por vaga em cada processo do Worker.

## Exceções

- **E1 — Vaga ocupada por outra transação ao mesmo tempo:** o índice único rejeita a inserção. O sistema descarta a tentativa (automático) ou, na proposta manual futura, responde `409` e nada é gravado.
- **E2 — Solicitação já tem agendamento ativo:** o índice único de RN-002 rejeita a inserção, com o mesmo tratamento de E1.

## Pós-condições

- Agendamento `PROPOSTO` com `expira_em`, solicitação `EM_PROPOSTA`, auditoria e evento de aviso gravados.

## Implementação

Job `propor_vagas` do Worker, só com `MATCHING_AUTOMATICO=true`, a cada `WORKER_INTERVALO_MATCHING_S` (padrão 60 s). A escolha vive em `propor_vaga()` (domínio). O job trava a vaga com `SKIP LOCKED`, lê as candidatas sem trava e trava só a escolhida, também com `SKIP LOCKED`; se ela estiver travada por outro Worker, passa para a próxima da ordem e revalida no domínio. Cada vaga é uma transação; conflito nos índices únicos descarta só aquela vaga. As vagas vêm do job `gerar_vagas` (a cada `WORKER_INTERVALO_VAGAS_S`, `VAGAS_HORIZONTE_DIAS` dias à frente).

## Critérios de aceite

- **Dado** uma vaga livre e duas solicitações na fila da vaga, **quando** a vaga é proposta, **então** vai para a primeira na ordem risco → nota → hora de chegada (`test_uc003_propoe_ao_primeiro_na_ordem_da_fila`).
- **Dado** duas solicitações com o mesmo risco e a mesma nota, **quando** a vaga é proposta, **então** vai para a que chegou antes à fila.
- **Dado** duas propostas simultâneas para a mesma vaga, **quando** ambas tentam gravar, **então** exatamente uma é criada (`test_adr004_rn002_propor_vagas_concorrente_nao_duplica`).
- **Dado** uma vaga para a qual o prazo calculado deixa menos de `PROPOSTA_JANELA_MINIMA_HORAS` para o paciente responder, **quando** se tenta propor, **então** nenhuma proposta é criada e a vaga aparece como "vaga sem proposta" (`test_rn016_janela_curta_nao_propoe`, `test_rn016_painel_de_vagas_destaca_livre_sem_proposta`).
- **Dado** uma vaga distante, **quando** é proposta, **então** `expira_em` = agora + `prazo_confirmacao_horas` da fila (padrão 48 horas).
- **Dado** uma vaga de tarde, **quando** a vaga é proposta, **então** a solicitação que prefere manhã é pulada (`test_uc003_respeita_o_turno`).
- **Dado** uma solicitação `EM_ANALISE`, **quando** o Worker propõe, **então** ela não recebe vaga (`test_uc003_nao_propoe_para_solicitacao_em_analise`).
- **Dado** as primeiras candidatas que já receberam a vaga, **quando** o teto é atingido, **então** o aviso sai uma vez, sem dado pessoal (`test_uc003_teto_de_candidatas_registra_aviso_sem_dado_pessoal`).
- **Dado** uma proposta criada, **quando** o Worker processa a outbox, **então** o paciente tem um aviso no site e um e-mail na fila de envio.

## Segurança

- *(Futuro — proposta manual)* Só Atendente, nas filas do seu escopo (`escopo_da_equipe()`, [ADR-025](../../decisions/ADR-025-escopo-por-fila.md), [controle de acesso](../../security/access-control.md)).
- A posição na fila e o motivo da última mudança de posição são mostrados à equipe, nunca ao paciente (RN-007).

Diagrama: [atividades da fila](../../architecture/diagrams/activity-queue.md).
