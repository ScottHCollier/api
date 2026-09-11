"""Remove imported fixtures from the 2025/26 season."""

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            DELETE FROM fixtures
            WHERE external_provider = 'fa_full_time'
              AND starts_at >= '2025-07-01T00:00:00+00:00'
              AND starts_at < '2026-07-01T00:00:00+00:00'
            """
        )
    )


def downgrade() -> None:
    # Deleted source rows cannot be reconstructed by a downgrade.
    pass
