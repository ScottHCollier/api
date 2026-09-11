"""Add an append-only audit event log."""

import sqlalchemy as sa
from alembic import op

revision = "0037"
down_revision = "0036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_events",
        sa.Column("audit_event_id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("actor_user_id", sa.UUID(), nullable=True),
        sa.Column("club_id", sa.UUID(), nullable=True),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("entity_id", sa.UUID(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.user_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["club_id"], ["clubs.club_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("audit_event_id"),
    )
    op.create_index("ix_audit_events_club_created_at", "audit_events", ["club_id", "created_at"])
    op.create_index("ix_audit_events_actor_created_at", "audit_events", ["actor_user_id", "created_at"])
    op.create_index("ix_audit_events_created_at", "audit_events", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_audit_events_created_at", table_name="audit_events")
    op.drop_index("ix_audit_events_actor_created_at", table_name="audit_events")
    op.drop_index("ix_audit_events_club_created_at", table_name="audit_events")
    op.drop_table("audit_events")
