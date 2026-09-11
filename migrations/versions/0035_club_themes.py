"""Persist club appearance themes."""

import sqlalchemy as sa
from alembic import op

revision = "0035"
down_revision = "0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("clubs", sa.Column("theme", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("clubs", "theme")
