"""Store league standings imported from FA Full-Time."""

import sqlalchemy as sa
from alembic import op

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "league_standings",
        sa.Column(
            "standing_id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("team_id", sa.UUID(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("team_name", sa.String(200), nullable=False),
        sa.Column("played", sa.Integer(), nullable=False),
        sa.Column("goal_difference", sa.Integer(), nullable=False),
        sa.Column("points", sa.Integer(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["team_id"], ["teams.team_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("standing_id"),
        sa.UniqueConstraint("team_id", "position"),
    )
    op.create_index("ix_league_standings_team_id", "league_standings", ["team_id"])


def downgrade() -> None:
    op.drop_index("ix_league_standings_team_id", table_name="league_standings")
    op.drop_table("league_standings")
