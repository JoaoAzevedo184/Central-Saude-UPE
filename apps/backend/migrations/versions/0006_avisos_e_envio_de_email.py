"""avisos: consumo da outbox, envio de e-mail com novas tentativas e lembrete

`notificacao.outbox_id` liga o aviso ao evento que o criou. `uq_notificacao_outbox_usuario_canal`
torna o consumo idempotente (ADR-006): reprocessar o mesmo evento não duplica avisos. O
lembrete não vem da outbox (`outbox_id` nulo, sem colisão nesse índice); fica um por
agendamento e canal em `ux_notificacao_lembrete`.

`proximo_retry_em` e `enviada_em` servem ao job `enviar_emails`. `CANCELADA` cobre o lembrete
cujo agendamento deixou de estar confirmado antes do envio.

Índices:
- `ix_notificacao_email_pendente`: o job de e-mail filtra `canal = 'EMAIL'`,
  `status_envio = 'PENDENTE'` e `proximo_retry_em` vencido; o status fica no predicado.
- `ix_notificacao_avisos_usuario`: lista e contagem dos avisos do site do usuário, mais
  recentes primeiro.

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-20 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("notificacao", sa.Column("outbox_id", sa.Uuid(), nullable=True))
    op.add_column(
        "notificacao", sa.Column("proximo_retry_em", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("notificacao", sa.Column("enviada_em", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key(
        op.f("fk_notificacao_outbox_id_outbox"),
        "notificacao",
        "outbox",
        ["outbox_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.drop_constraint(op.f("ck_notificacao_status_envio"), "notificacao", type_="check")
    op.create_check_constraint(
        op.f("ck_notificacao_status_envio"),
        "notificacao",
        "status_envio IN ('PENDENTE', 'ENVIADA', 'FALHOU', 'CANCELADA')",
    )
    op.create_unique_constraint(
        op.f("uq_notificacao_outbox_usuario_canal"),
        "notificacao",
        ["outbox_id", "usuario_id", "canal"],
    )
    op.create_index(
        "ux_notificacao_lembrete",
        "notificacao",
        ["agendamento_id", "tipo", "canal"],
        unique=True,
        postgresql_where=sa.text("tipo = 'LEMBRETE'"),
    )
    op.create_index(
        "ix_notificacao_email_pendente",
        "notificacao",
        ["canal", "proximo_retry_em"],
        postgresql_where=sa.text("status_envio = 'PENDENTE'"),
    )
    op.create_index(
        "ix_notificacao_avisos_usuario",
        "notificacao",
        ["usuario_id", sa.text("criada_em DESC")],
        postgresql_where=sa.text("canal = 'IN_APP'"),
    )


def downgrade() -> None:
    op.drop_index("ix_notificacao_avisos_usuario", table_name="notificacao")
    op.drop_index("ix_notificacao_email_pendente", table_name="notificacao")
    op.drop_index("ux_notificacao_lembrete", table_name="notificacao")
    op.drop_constraint(op.f("uq_notificacao_outbox_usuario_canal"), "notificacao", type_="unique")
    op.drop_constraint(op.f("ck_notificacao_status_envio"), "notificacao", type_="check")
    # CANCELADA deixa de existir: vira FALHOU para o CHECK antigo aceitar as linhas.
    op.execute("UPDATE notificacao SET status_envio = 'FALHOU' WHERE status_envio = 'CANCELADA'")
    op.create_check_constraint(
        op.f("ck_notificacao_status_envio"),
        "notificacao",
        "status_envio IN ('PENDENTE', 'ENVIADA', 'FALHOU')",
    )
    op.drop_constraint(op.f("fk_notificacao_outbox_id_outbox"), "notificacao", type_="foreignkey")
    op.drop_column("notificacao", "enviada_em")
    op.drop_column("notificacao", "proximo_retry_em")
    op.drop_column("notificacao", "outbox_id")
