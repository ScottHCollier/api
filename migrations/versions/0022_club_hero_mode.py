"""Add the public club hero display mode."""

import sqlalchemy as sa
from alembic import op

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "clubs",
        sa.Column(
            "hero_mode",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'current'"),
        ),
    )


def downgrade() -> None:
    op.drop_column("clubs", "hero_mode")
