"""Store scores for completed imported fixtures."""

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("fixtures", sa.Column("home_score", sa.Integer(), nullable=True))
    op.add_column("fixtures", sa.Column("away_score", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("fixtures", "away_score")
    op.drop_column("fixtures", "home_score")
