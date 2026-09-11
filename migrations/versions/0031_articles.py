"""Add publishable club news articles."""

import sqlalchemy as sa
from alembic import op

revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "articles",
        sa.Column("article_id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("club_id", sa.UUID(), sa.ForeignKey("clubs.club_id", ondelete="CASCADE"), nullable=False),
        sa.Column("image_id", sa.UUID(), sa.ForeignKey("image_assets.image_id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("body", sa.String(10000), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_articles_club_id", "articles", ["club_id"])
    op.create_index("ix_articles_published_at", "articles", ["published_at"])


def downgrade() -> None:
    op.drop_index("ix_articles_published_at", table_name="articles")
    op.drop_index("ix_articles_club_id", table_name="articles")
    op.drop_table("articles")
