"""Track fixture import outcomes per linked team."""

import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fixture_import_runs",
        sa.Column(
            "import_run_id",
            sa.UUID(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("club_id", sa.UUID(), nullable=False),
        sa.Column("team_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_count", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column(
            "updated_count", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column("error", sa.String(500), nullable=True),
        sa.ForeignKeyConstraint(["club_id"], ["clubs.club_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.team_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("import_run_id", name="pk_fixture_import_runs"),
    )
    op.create_index(
        "ix_fixture_import_runs_club_id", "fixture_import_runs", ["club_id"]
    )
    op.create_index(
        "ix_fixture_import_runs_team_id", "fixture_import_runs", ["team_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_fixture_import_runs_team_id", table_name="fixture_import_runs")
    op.drop_index("ix_fixture_import_runs_club_id", table_name="fixture_import_runs")
    op.drop_table("fixture_import_runs")
