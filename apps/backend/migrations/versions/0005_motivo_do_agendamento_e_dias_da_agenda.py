"""motivo do cancelamento do agendamento como código; dias da semana da agenda em ISO

`agendamento.motivo_cancelamento` era texto livre: passa a ser código de lista fechada, só em
agendamento `CANCELADO`. A contagem de recusas (UC-005) depende de `RECUSADO_PELO_PACIENTE`.
`CANCELADO_PELA_EQUIPE` e `VAGA_BLOQUEADA` ficam reservados. Até aqui nenhum caminho criava
agendamento, então não há texto livre a normalizar antes do CHECK.

`agenda.dias_semana` usa ISO 8601: 1 = segunda ... 7 = domingo, sem lista vazia.

`historico_solicitacao.seq` desempata eventos gravados no mesmo instante (`RECUSADA` e
`REENTROU_NA_FILA`): a linha do tempo é ordenada por `(ocorrido_em, seq)`. As linhas que já
existem recebem números ao adicionar a coluna (sem UPDATE, então o gatilho append-only não
dispara).

Sem índice novo: `ix_agendamento_expiracao` (0002) atende a expiração, e
`uq_vaga_agenda_inicio` (0002) já é um índice em `(agenda_id, inicio)`.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-19 22:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


MOTIVOS = (
    "'RECUSADO_PELO_PACIENTE', 'CANCELADO_PELO_PACIENTE', 'CANCELADO_PELA_EQUIPE', 'VAGA_BLOQUEADA'"
)


def upgrade() -> None:
    op.add_column(
        "historico_solicitacao",
        sa.Column("seq", sa.BigInteger(), sa.Identity(always=True), nullable=False),
    )
    op.create_check_constraint(
        op.f("ck_agendamento_motivo_cancelamento"),
        "agendamento",
        f"motivo_cancelamento IN ({MOTIVOS})",
    )
    op.create_check_constraint(
        op.f("ck_agendamento_motivo_so_se_cancelado"),
        "agendamento",
        "motivo_cancelamento IS NULL OR status = 'CANCELADO'",
    )
    op.create_check_constraint(
        op.f("ck_agenda_dias_semana_iso"),
        "agenda",
        "cardinality(dias_semana) > 0 AND dias_semana <@ ARRAY[1,2,3,4,5,6,7]::smallint[]",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_agenda_dias_semana_iso"), "agenda", type_="check")
    op.drop_constraint(op.f("ck_agendamento_motivo_so_se_cancelado"), "agendamento", type_="check")
    op.drop_constraint(op.f("ck_agendamento_motivo_cancelamento"), "agendamento", type_="check")
    op.drop_column("historico_solicitacao", "seq")
