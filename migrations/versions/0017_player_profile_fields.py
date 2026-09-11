"""Add player profile, contact, FA and renewal fields."""

import sqlalchemy as sa
from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("players", sa.Column("position", sa.String(50), nullable=True))
    op.add_column("players", sa.Column("email", sa.String(320), nullable=True))
    op.add_column("players", sa.Column("phone", sa.String(50), nullable=True))
    op.add_column("players", sa.Column("guardian_name", sa.String(200), nullable=True))
    op.add_column("players", sa.Column("guardian_email", sa.String(320), nullable=True))
    op.add_column("players", sa.Column("guardian_phone", sa.String(50), nullable=True))
    op.add_column("players", sa.Column("fa_fan_id", sa.String(50), nullable=True))
    op.add_column(
        "players",
        sa.Column(
            "auto_renew_next_season",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "players",
        sa.Column(
            "homegrown_player",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column("players", sa.Column("notes", sa.String(2000), nullable=True))


def downgrade() -> None:
    for column in (
        "notes",
        "homegrown_player",
        "auto_renew_next_season",
        "fa_fan_id",
        "guardian_phone",
        "guardian_email",
        "guardian_name",
        "phone",
        "email",
        "position",
    ):
        op.drop_column("players", column)
