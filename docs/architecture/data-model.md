# Modelo de dados

PostgreSQL. Identificadores `uuid`; datas e horas como `timestamptz` ([ADR-008](../decisions/ADR-008-datas-e-fuso.md)). Campos marcados com **ABERTO-n** dependem de [decisões em aberto](../requirements/open-questions.md).

```mermaid
erDiagram
  USUARIO ||--o| PACIENTE : "conta de"
  USUARIO ||--o{ AUDITORIA : "ator"
  USUARIO ||--o{ NOTIFICACAO : "destinatario"
  USUARIO ||--o{ USUARIO_UNIDADE : "ABERTO-3 lotacao"
  UNIDADE ||--o{ USUARIO_UNIDADE : "ABERTO-3"
  PACIENTE ||--o{ CONSENTIMENTO : "concede"
  PACIENTE ||--o{ SOLICITACAO : "faz"
  UNIDADE ||--o{ UNIDADE_ESPECIALIDADE : "oferece"
  ESPECIALIDADE ||--o{ UNIDADE_ESPECIALIDADE : "ofertada em"
  UNIDADE_ESPECIALIDADE ||--o{ AGENDA : "organiza"
  AGENDA ||--o{ VAGA : "gera"
  ESPECIALIDADE ||--o{ SOLICITACAO : "pedida em"
  UNIDADE |o--o{ SOLICITACAO : "preferida"
  SOLICITACAO ||--o{ AGENDAMENTO : "recebe propostas"
  VAGA ||--o{ AGENDAMENTO : "ocupada por"
  USUARIO |o--o{ AGENDAMENTO : "ABERTO-1 propos"
  SOLICITACAO |o--o{ NOTIFICACAO : "sobre"
  AGENDAMENTO |o--o{ NOTIFICACAO : "sobre"

  USUARIO {
    uuid id PK
    text email UK
    text senha_hash
    enum papel "PACIENTE ATENDENTE GESTOR ADMIN"
    bool ativo
    timestamptz criado_em
  }
  PACIENTE {
    uuid id PK
    uuid usuario_id FK, UK
    text nome
    text cpf UK "mascarado na interface"
    text cns UK "cartao do SUS"
    date data_nascimento
    text telefone
  }
  CONSENTIMENTO {
    uuid id PK
    uuid paciente_id FK
    enum finalidade "AGENDAMENTO LEMBRETE_EMAIL"
    text versao_termo
    timestamptz concedido_em
    timestamptz revogado_em "nulo = vigente"
  }
  USUARIO_UNIDADE {
    uuid usuario_id PK, FK "ABERTO-3 so existe se o escopo for por unidade"
    uuid unidade_id PK, FK
  }
  UNIDADE {
    uuid id PK
    text sigla UK
    text nome
    text endereco
  }
  ESPECIALIDADE {
    uuid id PK
    text nome UK
  }
  UNIDADE_ESPECIALIDADE {
    uuid id PK
    uuid unidade_id FK
    uuid especialidade_id FK
    int prazo_resposta_horas
    bool ativa
  }
  AGENDA {
    uuid id PK
    uuid unidade_especialidade_id FK
    text profissional
    smallint_array dias_semana
    time hora_inicio
    time hora_fim
    int duracao_min
    date vigencia_inicio
    date vigencia_fim
    bool ativa
  }
  VAGA {
    uuid id PK
    uuid agenda_id FK
    timestamptz inicio "UK junto com agenda_id"
    timestamptz fim
    enum status_admin "ATIVA BLOQUEADA"
  }
  SOLICITACAO {
    uuid id PK
    uuid paciente_id FK
    uuid especialidade_id FK
    uuid unidade_preferida_id FK "nulo = qualquer unidade; ver ABERTO-3"
    enum classificacao_risco "vem da regulacao"
    enum prioridade_legal "retrato no momento do pedido"
    enum turno_preferido
    text origem_encaminhamento
    date data_pedido
    enum status "EM_ANALISE NA_FILA EM_PROPOSTA AGENDADA ATENDIDA CANCELADA"
    timestamptz criada_em
  }
  AGENDAMENTO {
    uuid id PK
    uuid solicitacao_id FK
    uuid vaga_id FK
    enum status "PROPOSTO CONFIRMADO CANCELADO EXPIRADO REALIZADO FALTOU"
    uuid proposto_por_usuario_id FK "ABERTO-1 nulo = automatico"
    timestamptz proposto_em
    timestamptz expira_em "ABERTO-1 regra de antecedencia"
    timestamptz respondido_em
    text motivo_cancelamento
  }
  REGRA_PRIORIDADE {
    uuid id PK
    smallint ordem
    enum criterio "CLASSIFICACAO_RISCO PRIORIDADE_LEGAL DATA_PEDIDO; ABERTO-2 AGING"
    jsonb parametros
    bool simulada
    bool ativa
    timestamptz vigente_desde
  }
  NOTIFICACAO {
    uuid id PK
    uuid usuario_id FK
    uuid solicitacao_id FK "opcional"
    uuid agendamento_id FK "opcional"
    enum canal "IN_APP EMAIL"
    text tipo
    text titulo
    text corpo
    enum status_envio "PENDENTE ENVIADA FALHOU"
    int tentativas
    timestamptz lida_em
    timestamptz criada_em
  }
  OUTBOX {
    uuid id PK
    text tipo_evento
    text agregado_tipo
    uuid agregado_id
    jsonb payload
    enum status "PENDENTE PROCESSADO FALHOU"
    int tentativas
    timestamptz proximo_retry_em
    timestamptz criado_em
    timestamptz processado_em
  }
  AUDITORIA {
    uuid id PK
    uuid ator_usuario_id FK "nulo = sistema ou Worker"
    text acao
    text entidade
    uuid entidade_id
    jsonb dados_antes "minimizado"
    jsonb dados_depois "minimizado"
    inet ip
    timestamptz ocorrido_em
  }
```

## Restrições

```sql
-- RN-001 / ADR-004: a ocupação da vaga é derivada do agendamento ativo
CREATE UNIQUE INDEX ux_agendamento_vaga_ativa
  ON agendamento (vaga_id)
  WHERE status IN ('PROPOSTO', 'CONFIRMADO');

-- RN-002: no máximo uma proposta ou confirmação ativa por solicitação
CREATE UNIQUE INDEX ux_agendamento_solicitacao_ativa
  ON agendamento (solicitacao_id)
  WHERE status IN ('PROPOSTO', 'CONFIRMADO');

-- Vagas sem duplicata na mesma agenda
ALTER TABLE vaga ADD CONSTRAINT uq_vaga_agenda_inicio UNIQUE (agenda_id, inicio);

-- Uma oferta por unidade e especialidade
ALTER TABLE unidade_especialidade
  ADD CONSTRAINT uq_unidade_especialidade UNIQUE (unidade_id, especialidade_id);

-- Um consentimento vigente por paciente e finalidade
CREATE UNIQUE INDEX ux_consentimento_vigente
  ON consentimento (paciente_id, finalidade)
  WHERE revogado_em IS NULL;

-- Worker: busca eficiente de eventos pendentes e propostas a expirar
CREATE INDEX ix_outbox_pendente ON outbox (proximo_retry_em) WHERE status = 'PENDENTE';
CREATE INDEX ix_agendamento_expiracao ON agendamento (expira_em) WHERE status = 'PROPOSTO';
```

## Observações

- **Vaga livre** = `status_admin = 'ATIVA'` e nenhum agendamento ativo apontando para ela. A tabela `vaga` não guarda "ocupada", para não existir estado duplicado que possa divergir.
- **Prioridade legal** é gravada na solicitação no momento do pedido, para a ordem da fila continuar auditável mesmo que os dados do paciente mudem.
- **Notificação** pode se referir a uma solicitação, a um agendamento ou a nenhum dos dois (avisos de conta).
- **Auditoria** é append-only: a aplicação nunca faz `UPDATE` nem `DELETE` nessa tabela.
- **Outbox** é gravada na mesma transação da mudança de estado e consumida pelo Worker com `FOR UPDATE SKIP LOCKED`.
- Se houver aging (**ABERTO-2**), a ordem da fila passa a depender do tempo e é calculada na consulta, não gravada.
