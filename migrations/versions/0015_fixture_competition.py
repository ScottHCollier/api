"""Add competition to fixtures."""

import sqlalchemy as sa
from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("fixtures", sa.Column("competition", sa.String(200), nullable=True))


def downgrade() -> None:
    op.drop_column("fixtures", "competition")
