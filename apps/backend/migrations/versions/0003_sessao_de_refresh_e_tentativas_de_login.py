"""sessão de refresh e tentativas de login (ADR-003, AM-004); e-mail do usuário anulável

`sessao_refresh` guarda só o hash SHA-256 do refresh token, com a família para detectar
reuso. `tentativa_login` alimenta o limite de tentativas de login e de registro, sem o
identificador em claro. `usuario.email` fica anulável: o e-mail do paciente é opcional (UC-001).

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-19 20:13:01.537854
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tentativa_login",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tipo", sa.Text(), nullable=False),
        sa.Column("identificador_hash", sa.Text(), nullable=True),
        sa.Column("ip", postgresql.INET(), nullable=True),
        sa.Column("sucesso", sa.Boolean(), nullable=False),
        sa.Column("ocorrido_em", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "tipo = 'REGISTRO' OR identificador_hash IS NOT NULL",
            name=op.f("ck_tentativa_login_login_identificado"),
        ),
        sa.CheckConstraint("tipo IN ('LOGIN', 'REGISTRO')", name=op.f("ck_tentativa_login_tipo")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tentativa_login")),
    )
    op.create_index(
        "ix_tentativa_login_identificador_hash_ocorrido_em",
        "tentativa_login",
        ["identificador_hash", "ocorrido_em"],
        unique=False,
    )
    op.create_index(
        "ix_tentativa_login_ip_ocorrido_em", "tentativa_login", ["ip", "ocorrido_em"], unique=False
    )
    op.create_table(
        "sessao_refresh",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("usuario_id", sa.Uuid(), nullable=False),
        sa.Column("familia_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column(
            "criado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("expira_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revogado_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("substituido_por_id", sa.Uuid(), nullable=True),
        sa.Column("reapresentado_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ip", postgresql.INET(), nullable=True),
        sa.ForeignKeyConstraint(
            ["substituido_por_id"],
            ["sessao_refresh.id"],
            name=op.f("fk_sessao_refresh_substituido_por_id_sessao_refresh"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["usuario_id"],
            ["usuario.id"],
            name=op.f("fk_sessao_refresh_usuario_id_usuario"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sessao_refresh")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_sessao_refresh_token_hash")),
    )
    op.create_index(
        op.f("ix_sessao_refresh_familia_id"), "sessao_refresh", ["familia_id"], unique=False
    )
    op.create_index(
        op.f("ix_sessao_refresh_usuario_id"), "sessao_refresh", ["usuario_id"], unique=False
    )
    op.alter_column("usuario", "email", existing_type=sa.TEXT(), nullable=True)


def downgrade() -> None:
    # Falha se já houver paciente sem e-mail: não há valor para inventar.
    op.alter_column("usuario", "email", existing_type=sa.TEXT(), nullable=False)
    op.drop_index(op.f("ix_sessao_refresh_usuario_id"), table_name="sessao_refresh")
    op.drop_index(op.f("ix_sessao_refresh_familia_id"), table_name="sessao_refresh")
    op.drop_table("sessao_refresh")
    op.drop_index("ix_tentativa_login_ip_ocorrido_em", table_name="tentativa_login")
    op.drop_index("ix_tentativa_login_identificador_hash_ocorrido_em", table_name="tentativa_login")
    op.drop_table("tentativa_login")
