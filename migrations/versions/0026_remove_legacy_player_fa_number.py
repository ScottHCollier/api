"""Remove the legacy FA number column superseded by fa_fan_id."""

import sqlalchemy as sa
from alembic import op

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("players", "fa_number")


def downgrade() -> None:
    op.add_column("players", sa.Column("fa_number", sa.String(50), nullable=True))
