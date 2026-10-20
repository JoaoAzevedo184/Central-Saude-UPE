"""uma solicitação ativa por paciente e fila (RN-018); índices do paciente e do painel

`ux_solicitacao_ativa_por_fila` impede uma segunda solicitação aberta do mesmo paciente na
mesma fila; depois de `ATENDIDA` ou `CANCELADA`, uma nova é permitida. `ix_solicitacao_paciente_id`
atende "Minhas solicitações", inclusive as encerradas, que o índice único parcial não cobre.
`ix_solicitacao_fila_id_status` atende as contagens por status e o filtro do painel.
`solicitacao.motivo_cancelamento` guarda o motivo do cancelamento pelo paciente como código de
lista fechada, sem texto livre (minimização, docs/security/data-protection.md).

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-19 21:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


MOTIVOS = "'NAO_PRECISO_MAIS', 'CONSEGUI_EM_OUTRO_LUGAR', 'DIFICULDADE_DE_DESLOCAMENTO', " + (
    "'CONFLITO_DE_HORARIO', 'OUTRO'"
)


def upgrade() -> None:
    op.add_column("solicitacao", sa.Column("motivo_cancelamento", sa.Text(), nullable=True))
    op.create_check_constraint(
        op.f("ck_solicitacao_motivo_cancelamento"),
        "solicitacao",
        f"motivo_cancelamento IN ({MOTIVOS})",
    )
    op.create_check_constraint(
        op.f("ck_solicitacao_motivo_so_se_cancelada"),
        "solicitacao",
        "motivo_cancelamento IS NULL OR status = 'CANCELADA'",
    )
    op.create_index(
        "ux_solicitacao_ativa_por_fila",
        "solicitacao",
        ["paciente_id", "fila_id"],
        unique=True,
        postgresql_where=sa.text("status NOT IN ('ATENDIDA', 'CANCELADA')"),
    )
    op.create_index("ix_solicitacao_paciente_id", "solicitacao", ["paciente_id"], unique=False)
    op.create_index(
        "ix_solicitacao_fila_id_status", "solicitacao", ["fila_id", "status"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_solicitacao_fila_id_status", table_name="solicitacao")
    op.drop_index("ix_solicitacao_paciente_id", table_name="solicitacao")
    op.drop_index("ux_solicitacao_ativa_por_fila", table_name="solicitacao")
    op.drop_constraint(op.f("ck_solicitacao_motivo_so_se_cancelada"), "solicitacao", type_="check")
    op.drop_constraint(op.f("ck_solicitacao_motivo_cancelamento"), "solicitacao", type_="check")
    op.drop_column("solicitacao", "motivo_cancelamento")
