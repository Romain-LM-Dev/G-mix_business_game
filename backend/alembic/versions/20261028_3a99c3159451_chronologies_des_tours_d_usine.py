"""chronologies des tours d'usine

Table lobby_timelines (ADR 0007, annexe §4) : la chronologie d'un tour du pack « usine », rangée par `advance`
hors de lobbies.state. Aucune ligne existante ne change de sens : pas de migration de données.

Revision ID: 3a99c3159451
Revises: 5b1d2e7a9c40
Create Date: 2026-10-28 23:59:13.250750
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "3a99c3159451"
down_revision: str | None = "5b1d2e7a9c40"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "lobby_timelines",
        sa.Column("lobby_id", sa.UUID(), nullable=False),
        sa.Column("week", sa.SmallInteger(), autoincrement=False, nullable=False),
        sa.Column("timeline", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["lobby_id"], ["lobbies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("lobby_id", "week"),
    )


def downgrade() -> None:
    op.drop_table("lobby_timelines")  # les rejeux 3D des tours passés sont perdus ; états de partie intacts
