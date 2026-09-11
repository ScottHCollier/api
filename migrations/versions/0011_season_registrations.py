"""Add seasons and per-season player registrations."""

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "seasons",
        sa.Column(
            "season_id",
            sa.UUID(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("club_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(20), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=False),
        sa.Column(
            "is_current", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.ForeignKeyConstraint(["club_id"], ["clubs.club_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("season_id", name="pk_seasons"),
        sa.UniqueConstraint("club_id", "name", name="uq_seasons_club_id"),
    )
    op.create_index("ix_seasons_club_id", "seasons", ["club_id"])
    op.create_table(
        "player_registrations",
        sa.Column(
            "registration_id",
            sa.UUID(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("season_id", sa.UUID(), nullable=False),
        sa.Column("player_id", sa.UUID(), nullable=False),
        sa.Column(
            "status", sa.String(20), nullable=False, server_default=sa.text("'pending'")
        ),
        sa.Column(
            "consent_status",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'invited', 'complete')",
            name="ck_player_registrations_status",
        ),
        sa.CheckConstraint(
            "consent_status IN ('pending', 'complete')",
            name="ck_player_registrations_consent_status",
        ),
        sa.ForeignKeyConstraint(
            ["season_id"], ["seasons.season_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["player_id"], ["players.player_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("registration_id", name="pk_player_registrations"),
        sa.UniqueConstraint(
            "season_id", "player_id", name="uq_player_registrations_season_id"
        ),
    )
    op.create_index(
        "ix_player_registrations_season_id", "player_registrations", ["season_id"]
    )
    op.create_index(
        "ix_player_registrations_player_id", "player_registrations", ["player_id"]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_player_registrations_player_id", table_name="player_registrations"
    )
    op.drop_index(
        "ix_player_registrations_season_id", table_name="player_registrations"
    )
    op.drop_table("player_registrations")
    op.drop_index("ix_seasons_club_id", table_name="seasons")
    op.drop_table("seasons")
