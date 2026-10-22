"""spec figée du lobby

Revision ID: 0f75076ee120
Revises: fd6a38c328ae
Create Date: 2026-10-22 00:09:07.864762
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0f75076ee120"
down_revision: str | None = "fd6a38c328ae"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("lobbies", sa.Column("spec", postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column("lobbies", "spec")
