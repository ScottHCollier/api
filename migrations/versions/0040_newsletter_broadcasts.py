"""Add Resend segment configuration and newsletter broadcasts."""

import sqlalchemy as sa
from alembic import op

revision = "0040"
down_revision = "0039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("clubs", sa.Column("resend_segment_id", sa.String(length=100), nullable=True))
    op.create_table(
        "newsletter_broadcasts",
        sa.Column("broadcast_id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("club_id", sa.UUID(), nullable=False),
        sa.Column("created_by_user_id", sa.UUID(), nullable=True),
        sa.Column("resend_id", sa.String(length=100), nullable=False),
        sa.Column("subject", sa.String(length=300), nullable=False),
        sa.Column("status", sa.String(length=30), server_default=sa.text("'draft'"), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["club_id"], ["clubs.club_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.user_id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("broadcast_id"),
        sa.UniqueConstraint("resend_id"),
    )
    op.create_index("ix_newsletter_broadcasts_club_id", "newsletter_broadcasts", ["club_id"])
    op.create_index("ix_newsletter_broadcasts_created_by_user_id", "newsletter_broadcasts", ["created_by_user_id"])


def downgrade() -> None:
    op.drop_index("ix_newsletter_broadcasts_created_by_user_id", table_name="newsletter_broadcasts")
    op.drop_index("ix_newsletter_broadcasts_club_id", table_name="newsletter_broadcasts")
    op.drop_table("newsletter_broadcasts")
    op.drop_column("clubs", "resend_segment_id")
