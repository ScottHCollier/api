"""Store the vertical image position for each hero slide."""

import sqlalchemy as sa
from alembic import op

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "hero_slides",
        sa.Column(
            "image_position",
            sa.String(20),
            server_default=sa.text("'center'"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("hero_slides", "image_position")
