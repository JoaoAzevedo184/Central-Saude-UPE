"""senha temporária, momento da confirmação e limite da troca de senha

- `usuario.senha_temporaria`: a conta criada ou redefinida pelo ADMIN só consegue trocar a
  senha (e sair, renovar a sessão e ler `/me`) até definir a própria.
- `agendamento.confirmado_em`: quando a proposta foi confirmada. `respondido_em` não serve:
  o cancelamento de uma proposta também o preenche, e os indicadores precisam separar a
  confirmação cancelada da proposta cancelada antes de responder.
  Para linhas antigas, o valor vem de `respondido_em` (CONFIRMADO, REALIZADO e FALTOU) e é
  aproximado: a confirmação cancelada depois fica sem valor, porque o banco não guardou o
  momento dela.
- `tentativa_login.tipo` ganha `TROCA_SENHA` (AM-020): mesmo limite do login na troca de senha.

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-24 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "usuario",
        sa.Column(
            "senha_temporaria", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
    )
    op.add_column(
        "agendamento", sa.Column("confirmado_em", sa.DateTime(timezone=True), nullable=True)
    )
    op.execute(
        "UPDATE agendamento SET confirmado_em = respondido_em "
        "WHERE status IN ('CONFIRMADO', 'REALIZADO', 'FALTOU')"
    )
    op.drop_constraint(op.f("ck_tentativa_login_tipo"), "tentativa_login", type_="check")
    op.create_check_constraint(
        op.f("ck_tentativa_login_tipo"),
        "tentativa_login",
        "tipo IN ('LOGIN', 'REGISTRO', 'TROCA_SENHA')",
    )


def downgrade() -> None:
    op.execute("DELETE FROM tentativa_login WHERE tipo = 'TROCA_SENHA'")
    op.drop_constraint(op.f("ck_tentativa_login_tipo"), "tentativa_login", type_="check")
    op.create_check_constraint(
        op.f("ck_tentativa_login_tipo"), "tentativa_login", "tipo IN ('LOGIN', 'REGISTRO')"
    )
    op.drop_column("agendamento", "confirmado_em")
    op.drop_column("usuario", "senha_temporaria")
