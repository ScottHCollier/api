"""Add article drafts and scheduling."""

import sqlalchemy as sa
from alembic import op

revision = "0033"
down_revision = "0032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("articles", sa.Column("status", sa.String(20), server_default=sa.text("'published'"), nullable=False))
    op.add_column("articles", sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_articles_status", "articles", ["status"])


def downgrade() -> None:
    op.drop_index("ix_articles_status", table_name="articles")
    op.drop_column("articles", "scheduled_at")
    op.drop_column("articles", "status")
