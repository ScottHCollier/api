"""Add club fixtures and player availability responses."""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fixtures",
        sa.Column(
            "fixture_id",
            sa.UUID(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("club_id", sa.UUID(), nullable=False),
        sa.Column("team_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("venue", sa.String(200), nullable=False),
        sa.Column("external_provider", sa.String(50), nullable=True),
        sa.Column("external_id", sa.String(100), nullable=True),
        sa.ForeignKeyConstraint(["club_id"], ["clubs.club_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.team_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("fixture_id", name="pk_fixtures"),
        sa.UniqueConstraint(
            "external_provider", "external_id", name="uq_fixtures_external_provider_id"
        ),
    )
    op.create_index("ix_fixtures_club_id", "fixtures", ["club_id"])
    op.create_index("ix_fixtures_team_id", "fixtures", ["team_id"])
    op.create_table(
        "availability",
        sa.Column(
            "availability_id",
            sa.UUID(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("fixture_id", sa.UUID(), nullable=False),
        sa.Column("player_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("note", sa.String(500), nullable=True),
        sa.Column(
            "responded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["fixture_id"], ["fixtures.fixture_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["player_id"], ["players.player_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("availability_id", name="pk_availability"),
        sa.UniqueConstraint(
            "fixture_id", "player_id", name="uq_availability_fixture_player"
        ),
        sa.CheckConstraint(
            "status IN ('available', 'maybe', 'unavailable')",
            name="ck_availability_status",
        ),
    )
    op.create_index("ix_availability_fixture_id", "availability", ["fixture_id"])
    op.create_index("ix_availability_player_id", "availability", ["player_id"])


def downgrade() -> None:
    op.drop_index("ix_availability_player_id", table_name="availability")
    op.drop_index("ix_availability_fixture_id", table_name="availability")
    op.drop_table("availability")
    op.drop_index("ix_fixtures_team_id", table_name="fixtures")
    op.drop_index("ix_fixtures_club_id", table_name="fixtures")
    op.drop_table("fixtures")
