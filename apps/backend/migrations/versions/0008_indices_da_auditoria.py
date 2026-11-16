"""índices da consulta da auditoria (RF-023)

- `(entidade, entidade_id, ocorrido_em DESC)`: trilha de uma solicitação ou agendamento.
- `(ocorrido_em DESC)`: lista geral e filtros por período.
- `agendamento(solicitacao_id)`, não parcial: a trilha de uma solicitação inclui os
  agendamentos dela, encerrados também. Os índices parciais existentes só cobrem os ativos.

Só índices: a `auditoria` continua append-only (gatilho da 0002).

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-16 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_auditoria_entidade_ocorrido_em",
        "auditoria",
        ["entidade", "entidade_id", sa.text("ocorrido_em DESC")],
    )
    op.create_index("ix_auditoria_ocorrido_em", "auditoria", [sa.text("ocorrido_em DESC")])
    op.create_index("ix_agendamento_solicitacao_id", "agendamento", ["solicitacao_id"])


def downgrade() -> None:
    op.drop_index("ix_agendamento_solicitacao_id", table_name="agendamento")
    op.drop_index("ix_auditoria_ocorrido_em", table_name="auditoria")
    op.drop_index("ix_auditoria_entidade_ocorrido_em", table_name="auditoria")
