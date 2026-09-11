"""Add club-scoped player payment records."""

import sqlalchemy as sa
from alembic import op

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "payments",
        sa.Column(
            "payment_id",
            sa.UUID(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("club_id", sa.UUID(), nullable=False),
        sa.Column("player_id", sa.UUID(), nullable=False),
        sa.Column("description", sa.String(200), nullable=False),
        sa.Column("amount_pence", sa.Integer(), nullable=False),
        sa.Column(
            "status", sa.String(20), nullable=False, server_default=sa.text("'pending'")
        ),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'paid', 'overdue', 'cancelled')",
            name="ck_payments_status",
        ),
        sa.CheckConstraint("amount_pence > 0", name="ck_payments_amount_positive"),
        sa.ForeignKeyConstraint(["club_id"], ["clubs.club_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["player_id"], ["players.player_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("payment_id"),
    )
    op.create_index("ix_payments_club_id", "payments", ["club_id"])
    op.create_index("ix_payments_player_id", "payments", ["player_id"])


def downgrade() -> None:
    op.drop_index("ix_payments_player_id", table_name="payments")
    op.drop_index("ix_payments_club_id", table_name="payments")
    op.drop_table("payments")
