"""Add matchday attendance tracking."""

import sqlalchemy as sa
from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fixture_attendance",
        sa.Column(
            "attendance_id",
            sa.UUID(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("fixture_id", sa.UUID(), nullable=False),
        sa.Column("player_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("note", sa.String(500), nullable=True),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "status IN ('attended', 'late', 'absent', 'injured')",
            name="ck_fixture_attendance_status",
        ),
        sa.ForeignKeyConstraint(
            ["fixture_id"], ["fixtures.fixture_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["player_id"], ["players.player_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("attendance_id", name="pk_fixture_attendance"),
        sa.UniqueConstraint(
            "fixture_id", "player_id", name="uq_fixture_attendance_fixture_player"
        ),
    )
    op.create_index(
        "ix_fixture_attendance_fixture_id", "fixture_attendance", ["fixture_id"]
    )
    op.create_index(
        "ix_fixture_attendance_player_id", "fixture_attendance", ["player_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_fixture_attendance_player_id", table_name="fixture_attendance")
    op.drop_index("ix_fixture_attendance_fixture_id", table_name="fixture_attendance")
    op.drop_table("fixture_attendance")
