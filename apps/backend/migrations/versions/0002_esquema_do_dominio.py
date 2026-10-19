"""esquema do domínio (data-model.md), já com as decisões da UPE de 15/10/2026

Filas com protocolo próprio (ADR-024, ADR-027), escopo por fila (ADR-025), usuário suspenso
(ADR-028) e histórico da solicitação. Sem `regra_prioridade` nem `unidade_especialidade`.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-19 19:08:28.997833
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABELAS_APPEND_ONLY = ("auditoria", "historico_solicitacao")


def upgrade() -> None:
    op.create_table(
        "especialidade",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("nome", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_especialidade")),
        sa.UniqueConstraint("nome", name=op.f("uq_especialidade_nome")),
    )
    op.create_table(
        "outbox",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tipo_evento", sa.Text(), nullable=False),
        sa.Column("agregado_tipo", sa.Text(), nullable=False),
        sa.Column("agregado_id", sa.Uuid(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.Text(), server_default="PENDENTE", nullable=False),
        sa.Column("tentativas", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "proximo_retry_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "criado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("processado_em", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('PENDENTE', 'PROCESSADO', 'FALHOU')", name=op.f("ck_outbox_status")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_outbox")),
    )
    op.create_index(
        "ix_outbox_pendente",
        "outbox",
        ["proximo_retry_em"],
        unique=False,
        postgresql_where=sa.text("status = 'PENDENTE'"),
    )
    op.create_table(
        "unidade",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("sigla", sa.Text(), nullable=False),
        sa.Column("nome", sa.Text(), nullable=False),
        sa.Column("endereco", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_unidade")),
        sa.UniqueConstraint("sigla", name=op.f("uq_unidade_sigla")),
    )
    op.create_table(
        "usuario",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("senha_hash", sa.Text(), nullable=False),
        sa.Column("papel", sa.Text(), nullable=False),
        sa.Column("situacao", sa.Text(), server_default="ATIVO", nullable=False),
        sa.Column("suspenso_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("motivo_suspensao", sa.Text(), nullable=True),
        sa.Column(
            "criado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.CheckConstraint(
            "papel IN ('PACIENTE', 'ATENDENTE', 'GESTOR', 'ADMIN')", name=op.f("ck_usuario_papel")
        ),
        sa.CheckConstraint(
            "situacao = 'ATIVO' OR suspenso_em IS NOT NULL",
            name=op.f("ck_usuario_suspensao_datada"),
        ),
        sa.CheckConstraint("situacao IN ('ATIVO', 'SUSPENSO')", name=op.f("ck_usuario_situacao")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_usuario")),
        sa.UniqueConstraint("email", name=op.f("uq_usuario_email")),
    )
    op.create_table(
        "auditoria",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("ator_usuario_id", sa.Uuid(), nullable=True),
        sa.Column("acao", sa.Text(), nullable=False),
        sa.Column("entidade", sa.Text(), nullable=False),
        sa.Column("entidade_id", sa.Uuid(), nullable=False),
        sa.Column("dados_antes", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("dados_depois", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("ip", postgresql.INET(), nullable=True),
        sa.Column(
            "ocorrido_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["ator_usuario_id"],
            ["usuario.id"],
            name=op.f("fk_auditoria_ator_usuario_id_usuario"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auditoria")),
    )
    op.create_table(
        "fila",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("unidade_id", sa.Uuid(), nullable=False),
        sa.Column("especialidade_id", sa.Uuid(), nullable=False),
        sa.Column("nome", sa.Text(), nullable=False),
        sa.Column("descricao_paciente", sa.Text(), nullable=False),
        sa.Column("sexo_elegivel", sa.Text(), nullable=True),
        sa.Column("idade_minima", sa.SmallInteger(), nullable=True),
        sa.Column("idade_maxima", sa.SmallInteger(), nullable=True),
        sa.Column("prazo_confirmacao_horas", sa.Integer(), server_default="48", nullable=False),
        sa.Column("tolerancia_atraso_min", sa.Integer(), server_default="60", nullable=False),
        sa.Column("ativa", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.CheckConstraint(
            "sexo_elegivel IN ('FEMININO', 'MASCULINO')", name=op.f("ck_fila_sexo_elegivel")
        ),
        sa.CheckConstraint(
            "idade_minima IS NULL OR idade_maxima IS NULL OR idade_minima <= idade_maxima",
            name=op.f("ck_fila_faixa_etaria"),
        ),
        sa.CheckConstraint(
            "prazo_confirmacao_horas > 0", name=op.f("ck_fila_prazo_confirmacao_positivo")
        ),
        sa.CheckConstraint(
            "tolerancia_atraso_min >= 0", name=op.f("ck_fila_tolerancia_nao_negativa")
        ),
        sa.ForeignKeyConstraint(
            ["especialidade_id"],
            ["especialidade.id"],
            name=op.f("fk_fila_especialidade_id_especialidade"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["unidade_id"],
            ["unidade.id"],
            name=op.f("fk_fila_unidade_id_unidade"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_fila")),
        sa.UniqueConstraint("unidade_id", "nome", name="uq_fila_unidade_nome"),
    )
    op.create_table(
        "paciente",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("usuario_id", sa.Uuid(), nullable=False),
        sa.Column("nome", sa.Text(), nullable=False),
        sa.Column("cpf", sa.Text(), nullable=False),
        sa.Column("cns", sa.Text(), nullable=True),
        sa.Column("data_nascimento", sa.Date(), nullable=False),
        sa.Column("telefone", sa.Text(), nullable=True),
        sa.Column("sexo", sa.Text(), nullable=True),
        sa.Column("municipio", sa.Text(), nullable=True),
        sa.CheckConstraint("cpf ~ '^[0-9]{11}$'", name=op.f("ck_paciente_cpf_formato")),
        sa.CheckConstraint("sexo IN ('FEMININO', 'MASCULINO')", name=op.f("ck_paciente_sexo")),
        sa.ForeignKeyConstraint(
            ["usuario_id"],
            ["usuario.id"],
            name=op.f("fk_paciente_usuario_id_usuario"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_paciente")),
        sa.UniqueConstraint("cns", name=op.f("uq_paciente_cns")),
        sa.UniqueConstraint("cpf", name=op.f("uq_paciente_cpf")),
        sa.UniqueConstraint("usuario_id", name=op.f("uq_paciente_usuario_id")),
    )
    op.create_table(
        "usuario_unidade",
        sa.Column("usuario_id", sa.Uuid(), nullable=False),
        sa.Column("unidade_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["unidade_id"],
            ["unidade.id"],
            name=op.f("fk_usuario_unidade_unidade_id_unidade"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["usuario_id"],
            ["usuario.id"],
            name=op.f("fk_usuario_unidade_usuario_id_usuario"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("usuario_id", "unidade_id", name=op.f("pk_usuario_unidade")),
    )
    op.create_table(
        "agenda",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("fila_id", sa.Uuid(), nullable=False),
        sa.Column("profissional", sa.Text(), nullable=False),
        sa.Column("dias_semana", sa.ARRAY(sa.SmallInteger()), nullable=False),
        sa.Column("hora_inicio", sa.Time(), nullable=False),
        sa.Column("hora_fim", sa.Time(), nullable=False),
        sa.Column("duracao_min", sa.Integer(), nullable=False),
        sa.Column("vigencia_inicio", sa.Date(), nullable=False),
        sa.Column("vigencia_fim", sa.Date(), nullable=True),
        sa.Column("ativa", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.CheckConstraint("duracao_min > 0", name=op.f("ck_agenda_duracao_positiva")),
        sa.CheckConstraint("hora_inicio < hora_fim", name=op.f("ck_agenda_horario")),
        sa.CheckConstraint(
            "vigencia_fim IS NULL OR vigencia_inicio <= vigencia_fim",
            name=op.f("ck_agenda_vigencia"),
        ),
        sa.ForeignKeyConstraint(
            ["fila_id"], ["fila.id"], name=op.f("fk_agenda_fila_id_fila"), ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agenda")),
    )
    op.create_table(
        "consentimento",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("paciente_id", sa.Uuid(), nullable=False),
        sa.Column("finalidade", sa.Text(), nullable=False),
        sa.Column("versao_termo", sa.Text(), nullable=False),
        sa.Column(
            "concedido_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("revogado_em", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "finalidade IN ('AGENDAMENTO', 'LEMBRETE_EMAIL')",
            name=op.f("ck_consentimento_finalidade"),
        ),
        sa.ForeignKeyConstraint(
            ["paciente_id"],
            ["paciente.id"],
            name=op.f("fk_consentimento_paciente_id_paciente"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_consentimento")),
    )
    op.create_index(
        "ux_consentimento_vigente",
        "consentimento",
        ["paciente_id", "finalidade"],
        unique=True,
        postgresql_where=sa.text("revogado_em IS NULL"),
    )
    op.create_table(
        "criterio_fila",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("fila_id", sa.Uuid(), nullable=False),
        sa.Column("codigo", sa.Text(), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=False),
        sa.Column("tipo", sa.Text(), nullable=False),
        sa.Column("peso", sa.Integer(), nullable=False),
        sa.Column(
            "parametros",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column("origem", sa.Text(), nullable=False),
        sa.Column("simulado", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("ativo", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.CheckConstraint(
            "origem IN ('PACIENTE', 'REGULACAO', 'EQUIPE')", name=op.f("ck_criterio_fila_origem")
        ),
        sa.CheckConstraint(
            "tipo IN ('SIM_NAO', 'NUMERO', 'OPCAO')", name=op.f("ck_criterio_fila_tipo")
        ),
        sa.CheckConstraint("peso >= 0", name=op.f("ck_criterio_fila_peso_nao_negativo")),
        sa.ForeignKeyConstraint(
            ["fila_id"],
            ["fila.id"],
            name=op.f("fk_criterio_fila_fila_id_fila"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_criterio_fila")),
        sa.UniqueConstraint("fila_id", "codigo", name="uq_criterio_fila_codigo"),
        # Alvo da FK composta de resposta_criterio: o critério é da mesma fila da solicitação.
        sa.UniqueConstraint("id", "fila_id", name="uq_criterio_fila_id_fila"),
    )
    op.create_table(
        "solicitacao",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("paciente_id", sa.Uuid(), nullable=False),
        sa.Column("fila_id", sa.Uuid(), nullable=False),
        sa.Column("classificacao_risco", sa.Text(), nullable=True),
        sa.Column("turno_preferido", sa.Text(), server_default="QUALQUER", nullable=False),
        sa.Column("origem_encaminhamento", sa.Text(), nullable=True),
        sa.Column("data_pedido", sa.Date(), nullable=False),
        sa.Column("status", sa.Text(), server_default="EM_ANALISE", nullable=False),
        sa.Column("nota", sa.Integer(), server_default="0", nullable=False),
        sa.Column("data_entrada_fila", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "criada_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.CheckConstraint(
            "classificacao_risco IN ('VERMELHO', 'AMARELO', 'VERDE')",
            name=op.f("ck_solicitacao_classificacao_risco"),
        ),
        sa.CheckConstraint(
            "status <> 'NA_FILA' OR data_entrada_fila IS NOT NULL",
            name=op.f("ck_solicitacao_na_fila_com_entrada"),
        ),
        sa.CheckConstraint(
            "status IN ('EM_ANALISE', 'CANCELADA') OR classificacao_risco IS NOT NULL",
            name=op.f("ck_solicitacao_classificada"),
        ),
        sa.CheckConstraint(
            "status IN ('EM_ANALISE', 'NA_FILA', 'EM_PROPOSTA', 'AGENDADA', 'ATENDIDA', "
            "'CANCELADA')",
            name=op.f("ck_solicitacao_status"),
        ),
        sa.CheckConstraint(
            "turno_preferido IN ('MANHA', 'TARDE', 'QUALQUER')",
            name=op.f("ck_solicitacao_turno_preferido"),
        ),
        sa.ForeignKeyConstraint(
            ["fila_id"], ["fila.id"], name=op.f("fk_solicitacao_fila_id_fila"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["paciente_id"],
            ["paciente.id"],
            name=op.f("fk_solicitacao_paciente_id_paciente"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_solicitacao")),
        sa.UniqueConstraint("id", "fila_id", name="uq_solicitacao_id_fila"),
    )
    op.create_index(
        "ix_solicitacao_fila_ordem",
        "solicitacao",
        ["fila_id", "data_entrada_fila"],
        unique=False,
        postgresql_where=sa.text("status = 'NA_FILA'"),
    )
    op.create_table(
        "usuario_fila",
        sa.Column("usuario_id", sa.Uuid(), nullable=False),
        sa.Column("fila_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["fila_id"], ["fila.id"], name=op.f("fk_usuario_fila_fila_id_fila"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["usuario_id"],
            ["usuario.id"],
            name=op.f("fk_usuario_fila_usuario_id_usuario"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("usuario_id", "fila_id", name=op.f("pk_usuario_fila")),
    )
    op.create_table(
        "historico_solicitacao",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("solicitacao_id", sa.Uuid(), nullable=False),
        sa.Column("tipo", sa.Text(), nullable=False),
        sa.Column("status_anterior", sa.Text(), nullable=True),
        sa.Column("status_novo", sa.Text(), nullable=True),
        sa.Column("motivo", sa.Text(), nullable=True),
        sa.Column("visivel_paciente", sa.Boolean(), nullable=False),
        sa.Column("ator_usuario_id", sa.Uuid(), nullable=True),
        sa.Column(
            "ocorrido_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "tipo IN ('CRIADA', 'CLASSIFICADA', 'ENTROU_NA_FILA', 'PROPOSTA_ENVIADA', "
            "'CONFIRMADA', 'RECUSADA', 'PROPOSTA_EXPIRADA', 'FALTOU', 'ATENDIDA', 'CANCELADA', "
            "'REENTROU_NA_FILA', 'RECLASSIFICADA')",
            name=op.f("ck_historico_solicitacao_tipo"),
        ),
        sa.ForeignKeyConstraint(
            ["ator_usuario_id"],
            ["usuario.id"],
            name=op.f("fk_historico_solicitacao_ator_usuario_id_usuario"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["solicitacao_id"],
            ["solicitacao.id"],
            name=op.f("fk_historico_solicitacao_solicitacao_id_solicitacao"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_historico_solicitacao")),
    )
    op.create_index(
        op.f("ix_historico_solicitacao_solicitacao_id"),
        "historico_solicitacao",
        ["solicitacao_id"],
        unique=False,
    )
    op.create_table(
        "resposta_criterio",
        sa.Column("solicitacao_id", sa.Uuid(), nullable=False),
        sa.Column("criterio_id", sa.Uuid(), nullable=False),
        sa.Column("fila_id", sa.Uuid(), nullable=False),
        sa.Column("valor", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("pontos", sa.Integer(), nullable=False),
        sa.Column("respondido_por_usuario_id", sa.Uuid(), nullable=True),
        sa.Column(
            "respondido_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        # FKs compostas: solicitação e critério precisam ser da mesma fila. Trocar a fila de
        # uma solicitação que já tem respostas é bloqueado (ON UPDATE RESTRICT).
        sa.ForeignKeyConstraint(
            ["criterio_id", "fila_id"],
            ["criterio_fila.id", "criterio_fila.fila_id"],
            name=op.f("fk_resposta_criterio_criterio_id_criterio_fila"),
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["respondido_por_usuario_id"],
            ["usuario.id"],
            name=op.f("fk_resposta_criterio_respondido_por_usuario_id_usuario"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["solicitacao_id", "fila_id"],
            ["solicitacao.id", "solicitacao.fila_id"],
            name=op.f("fk_resposta_criterio_solicitacao_id_solicitacao"),
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("solicitacao_id", "criterio_id", name=op.f("pk_resposta_criterio")),
    )
    op.create_table(
        "vaga",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("agenda_id", sa.Uuid(), nullable=False),
        sa.Column("inicio", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fim", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status_admin", sa.Text(), server_default="ATIVA", nullable=False),
        sa.CheckConstraint(
            "status_admin IN ('ATIVA', 'BLOQUEADA')", name=op.f("ck_vaga_status_admin")
        ),
        sa.CheckConstraint("inicio < fim", name=op.f("ck_vaga_intervalo")),
        sa.ForeignKeyConstraint(
            ["agenda_id"], ["agenda.id"], name=op.f("fk_vaga_agenda_id_agenda"), ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_vaga")),
        sa.UniqueConstraint("agenda_id", "inicio", name="uq_vaga_agenda_inicio"),
    )
    op.create_table(
        "agendamento",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("solicitacao_id", sa.Uuid(), nullable=False),
        sa.Column("vaga_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.Text(), server_default="PROPOSTO", nullable=False),
        sa.Column("proposto_por_usuario_id", sa.Uuid(), nullable=True),
        sa.Column(
            "proposto_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expira_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("respondido_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("motivo_cancelamento", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "status IN ('PROPOSTO', 'CONFIRMADO', 'CANCELADO', 'EXPIRADO', 'REALIZADO', 'FALTOU')",
            name=op.f("ck_agendamento_status"),
        ),
        sa.CheckConstraint(
            "expira_em > proposto_em", name=op.f("ck_agendamento_expira_depois_de_propor")
        ),
        sa.ForeignKeyConstraint(
            ["proposto_por_usuario_id"],
            ["usuario.id"],
            name=op.f("fk_agendamento_proposto_por_usuario_id_usuario"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["solicitacao_id"],
            ["solicitacao.id"],
            name=op.f("fk_agendamento_solicitacao_id_solicitacao"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["vaga_id"], ["vaga.id"], name=op.f("fk_agendamento_vaga_id_vaga"), ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agendamento")),
    )
    op.create_index(
        "ix_agendamento_expiracao",
        "agendamento",
        ["expira_em"],
        unique=False,
        postgresql_where=sa.text("status = 'PROPOSTO'"),
    )
    op.create_index(
        "ux_agendamento_solicitacao_ativa",
        "agendamento",
        ["solicitacao_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('PROPOSTO', 'CONFIRMADO')"),
    )
    op.create_index(
        "ux_agendamento_vaga_ativa",
        "agendamento",
        ["vaga_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('PROPOSTO', 'CONFIRMADO')"),
    )
    op.create_table(
        "notificacao",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("usuario_id", sa.Uuid(), nullable=False),
        sa.Column("solicitacao_id", sa.Uuid(), nullable=True),
        sa.Column("agendamento_id", sa.Uuid(), nullable=True),
        sa.Column("canal", sa.Text(), nullable=False),
        sa.Column("tipo", sa.Text(), nullable=False),
        sa.Column("titulo", sa.Text(), nullable=False),
        sa.Column("corpo", sa.Text(), nullable=False),
        sa.Column("status_envio", sa.Text(), server_default="PENDENTE", nullable=False),
        sa.Column("tentativas", sa.Integer(), server_default="0", nullable=False),
        sa.Column("lida_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "criada_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.CheckConstraint("canal IN ('IN_APP', 'EMAIL')", name=op.f("ck_notificacao_canal")),
        sa.CheckConstraint(
            "status_envio IN ('PENDENTE', 'ENVIADA', 'FALHOU')",
            name=op.f("ck_notificacao_status_envio"),
        ),
        sa.ForeignKeyConstraint(
            ["agendamento_id"],
            ["agendamento.id"],
            name=op.f("fk_notificacao_agendamento_id_agendamento"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["solicitacao_id"],
            ["solicitacao.id"],
            name=op.f("fk_notificacao_solicitacao_id_solicitacao"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["usuario_id"],
            ["usuario.id"],
            name=op.f("fk_notificacao_usuario_id_usuario"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notificacao")),
    )

    # Auditoria e histórico são append-only: nem a aplicação nem um operador alteram o passado.
    op.execute(
        """
        CREATE FUNCTION impedir_alteracao() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'tabela % é append-only', TG_TABLE_NAME
                USING ERRCODE = 'restrict_violation';
        END;
        $$
        """
    )
    for tabela in TABELAS_APPEND_ONLY:
        op.execute(
            f"CREATE TRIGGER {tabela}_append_only BEFORE UPDATE OR DELETE ON {tabela} "
            "FOR EACH ROW EXECUTE FUNCTION impedir_alteracao()"
        )
        op.execute(
            f"CREATE TRIGGER {tabela}_sem_truncate BEFORE TRUNCATE ON {tabela} "
            "FOR EACH STATEMENT EXECUTE FUNCTION impedir_alteracao()"
        )


def downgrade() -> None:
    for tabela in TABELAS_APPEND_ONLY:
        op.execute(f"DROP TRIGGER {tabela}_sem_truncate ON {tabela}")
        op.execute(f"DROP TRIGGER {tabela}_append_only ON {tabela}")
    op.execute("DROP FUNCTION impedir_alteracao()")
    op.drop_table("notificacao")
    op.drop_index(
        "ux_agendamento_vaga_ativa",
        table_name="agendamento",
        postgresql_where=sa.text("status IN ('PROPOSTO', 'CONFIRMADO')"),
    )
    op.drop_index(
        "ux_agendamento_solicitacao_ativa",
        table_name="agendamento",
        postgresql_where=sa.text("status IN ('PROPOSTO', 'CONFIRMADO')"),
    )
    op.drop_index(
        "ix_agendamento_expiracao",
        table_name="agendamento",
        postgresql_where=sa.text("status = 'PROPOSTO'"),
    )
    op.drop_table("agendamento")
    op.drop_table("vaga")
    op.drop_table("resposta_criterio")
    op.drop_index(
        op.f("ix_historico_solicitacao_solicitacao_id"), table_name="historico_solicitacao"
    )
    op.drop_table("historico_solicitacao")
    op.drop_table("usuario_fila")
    op.drop_index(
        "ix_solicitacao_fila_ordem",
        table_name="solicitacao",
        postgresql_where=sa.text("status = 'NA_FILA'"),
    )
    op.drop_table("solicitacao")
    op.drop_table("criterio_fila")
    op.drop_index(
        "ux_consentimento_vigente",
        table_name="consentimento",
        postgresql_where=sa.text("revogado_em IS NULL"),
    )
    op.drop_table("consentimento")
    op.drop_table("agenda")
    op.drop_table("usuario_unidade")
    op.drop_table("paciente")
    op.drop_table("fila")
    op.drop_table("auditoria")
    op.drop_table("usuario")
    op.drop_table("unidade")
    op.drop_index(
        "ix_outbox_pendente", table_name="outbox", postgresql_where=sa.text("status = 'PENDENTE'")
    )
    op.drop_table("outbox")
    op.drop_table("especialidade")
