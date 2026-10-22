"""comptes, parametres de generation, etat de partie

Revision ID: fd6a38c328ae
Revises: 19a0c7875155
Create Date: 2026-10-21 23:54:35.404404
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "fd6a38c328ae"
down_revision: str | None = "19a0c7875155"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EMPTY_JSON = sa.text("'{}'::jsonb")


def upgrade() -> None:
    op.add_column("business_games", sa.Column("params", postgresql.JSONB(), server_default=EMPTY_JSON, nullable=False))
    op.add_column("business_games", sa.Column("review", postgresql.JSONB(), server_default=EMPTY_JSON, nullable=False))
    op.add_column("lobbies", sa.Column("state", postgresql.JSONB(), server_default=EMPTY_JSON, nullable=False))
    op.add_column("users", sa.Column("username", sa.String(length=64), nullable=False))
    op.add_column(
        "users", sa.Column("must_change_password", sa.Boolean(), server_default=sa.text("false"), nullable=False)
    )
    op.add_column("users", sa.Column("created_by", sa.UUID(), nullable=True))
    op.alter_column("users", "email", existing_type=sa.VARCHAR(length=320), nullable=True)
    op.create_index("ix_users_created_by", "users", ["created_by"], unique=False)
    op.create_unique_constraint("uq_users_username", "users", ["username"])
    op.create_foreign_key("fk_users_created_by", "users", "users", ["created_by"], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    op.drop_constraint("fk_users_created_by", "users", type_="foreignkey")
    op.drop_constraint("uq_users_username", "users", type_="unique")
    op.drop_index("ix_users_created_by", table_name="users")
    op.alter_column("users", "email", existing_type=sa.VARCHAR(length=320), nullable=False)
    op.drop_column("users", "created_by")
    op.drop_column("users", "must_change_password")
    op.drop_column("users", "username")
    op.drop_column("lobbies", "state")
    op.drop_column("business_games", "review")
    op.drop_column("business_games", "params")
