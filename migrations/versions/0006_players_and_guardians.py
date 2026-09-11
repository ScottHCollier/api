"""Add club-scoped youth players and parent/guardian links."""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "players",
        sa.Column(
            "player_id",
            sa.UUID(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("club_id", sa.UUID(), nullable=False),
        sa.Column("team_id", sa.UUID(), nullable=True),
        sa.Column("legal_first_name", sa.String(100), nullable=False),
        sa.Column("legal_last_name", sa.String(100), nullable=False),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("fa_number", sa.String(50), nullable=True),
        sa.Column(
            "registration_status",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column(
            "consent_status",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.ForeignKeyConstraint(["club_id"], ["clubs.club_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.team_id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("player_id", name="pk_players"),
    )
    op.create_index("ix_players_club_id", "players", ["club_id"])
    op.create_index("ix_players_team_id", "players", ["team_id"])
    op.create_table(
        "player_guardians",
        sa.Column(
            "player_guardian_id",
            sa.UUID(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("player_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["player_id"], ["players.player_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("player_guardian_id", name="pk_player_guardians"),
        sa.UniqueConstraint(
            "player_id", "user_id", name="uq_player_guardians_player_user"
        ),
    )
    op.create_index("ix_player_guardians_player_id", "player_guardians", ["player_id"])
    op.create_index("ix_player_guardians_user_id", "player_guardians", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_player_guardians_user_id", table_name="player_guardians")
    op.drop_index("ix_player_guardians_player_id", table_name="player_guardians")
    op.drop_table("player_guardians")
    op.drop_index("ix_players_team_id", table_name="players")
    op.drop_index("ix_players_club_id", table_name="players")
    op.drop_table("players")
