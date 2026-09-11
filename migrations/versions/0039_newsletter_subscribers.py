"""Add per-club newsletter consent records."""

import sqlalchemy as sa
from alembic import op

revision = "0039"
down_revision = "0038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "newsletter_subscribers",
        sa.Column("subscriber_id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("club_id", sa.UUID(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("status", sa.String(length=20), server_default=sa.text("'active'"), nullable=False),
        sa.Column("consented_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("unsubscribed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["club_id"], ["clubs.club_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("subscriber_id"),
        sa.UniqueConstraint("club_id", "email"),
    )
    op.create_index("ix_newsletter_subscribers_club_id", "newsletter_subscribers", ["club_id"])
    op.create_index("ix_newsletter_subscribers_email", "newsletter_subscribers", ["email"])


def downgrade() -> None:
    op.drop_index("ix_newsletter_subscribers_email", table_name="newsletter_subscribers")
    op.drop_index("ix_newsletter_subscribers_club_id", table_name="newsletter_subscribers")
    op.drop_table("newsletter_subscribers")
