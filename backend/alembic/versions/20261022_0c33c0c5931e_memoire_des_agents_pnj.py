"""memoire des agents PNJ

Revision ID: 0c33c0c5931e
Revises: 0f75076ee120
Create Date: 2026-10-22 11:43:16.306033
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0c33c0c5931e"
down_revision: str | None = "0f75076ee120"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "npc_memories",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("lobby_id", sa.UUID(), nullable=False),
        sa.Column("npc_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("speaker", sa.String(length=120), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("reply", sa.Text(), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["lobby_id"], ["lobbies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_npc_memories_lobby_npc", "npc_memories", ["lobby_id", "npc_id", "id"], unique=False)
    op.create_index(op.f("ix_npc_memories_user_id"), "npc_memories", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_npc_memories_user_id"), table_name="npc_memories")
    op.drop_index("ix_npc_memories_lobby_npc", table_name="npc_memories")
    op.drop_table("npc_memories")
