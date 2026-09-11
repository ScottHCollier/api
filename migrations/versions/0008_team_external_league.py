"""Store the Full-Time league identity used to resolve the current season."""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("teams", sa.Column("external_league_id", sa.String(100)))


def downgrade() -> None:
    op.drop_column("teams", "external_league_id")
