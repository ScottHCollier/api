"""Add retry metadata to fixture import jobs."""

import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "fixture_import_runs",
        sa.Column(
            "attempt_count", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
    )
    op.add_column(
        "fixture_import_runs",
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("fixture_import_runs", "next_attempt_at")
    op.drop_column("fixture_import_runs", "attempt_count")
