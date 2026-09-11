"""Add public team introductions."""

import sqlalchemy as sa
from alembic import op

revision = "0034"
down_revision = "0033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("teams", sa.Column("description", sa.String(1000), server_default=sa.text("''"), nullable=False))


def downgrade() -> None:
    op.drop_column("teams", "description")
