"""Add coach-managed fixture squad selection."""

import sqlalchemy as sa
from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fixture_selections",
        sa.Column(
            "selection_id",
            sa.UUID(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("fixture_id", sa.UUID(), nullable=False),
        sa.Column("player_id", sa.UUID(), nullable=False),
        sa.Column(
            "selected", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column(
            "updated_at",
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
        sa.PrimaryKeyConstraint("selection_id", name="pk_fixture_selections"),
        sa.UniqueConstraint(
            "fixture_id", "player_id", name="uq_fixture_selection_fixture_player"
        ),
    )
    op.create_index(
        "ix_fixture_selections_fixture_id", "fixture_selections", ["fixture_id"]
    )
    op.create_index(
        "ix_fixture_selections_player_id", "fixture_selections", ["player_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_fixture_selections_player_id", table_name="fixture_selections")
    op.drop_index("ix_fixture_selections_fixture_id", table_name="fixture_selections")
    op.drop_table("fixture_selections")
