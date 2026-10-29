"""parties de l'ancien modele archivees

Business games et lobbies créés avant les simulations paramétrées (ADR 0006) : leur spec n'est plus jouable.
Ils sont archivés ou clos, rien n'est supprimé (la spec reste lisible en base).

Revision ID: 5b1d2e7a9c40
Revises: 0c33c0c5931e
Create Date: 2026-10-22 15:10:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "5b1d2e7a9c40"
down_revision: str | None = "0c33c0c5931e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEGACY = "spec IS NULL OR spec->>'kind' IS DISTINCT FROM 'simulation'"


def upgrade() -> None:
    op.execute(f"UPDATE business_games SET status = 'archived' WHERE status <> 'archived' AND ({LEGACY})")
    op.execute(f"UPDATE lobbies SET status = 'closed' WHERE status <> 'closed' AND ({LEGACY})")


def downgrade() -> None:
    pass  # statuts d'origine non conservés ; ces parties restent injouables avec le moteur actuel
