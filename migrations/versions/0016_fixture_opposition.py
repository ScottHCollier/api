"""Store structured opposition details for fixtures."""

import sqlalchemy as sa
from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("fixtures", sa.Column("opposition", sa.String(200), nullable=True))
    op.add_column("fixtures", sa.Column("is_home", sa.Boolean(), nullable=True))
    op.execute(
        sa.text(
            """
            UPDATE fixtures AS f
            SET opposition = CASE
                    WHEN position(
                        lower(coalesce(t.external_name, t.name)) IN
                        lower(split_part(f.title, ' vs. ', 1))
                    ) > 0
                        THEN trim(split_part(f.title, ' vs. ', 2))
                    WHEN position(
                        lower(coalesce(t.external_name, t.name)) IN
                        lower(split_part(f.title, ' vs. ', 2))
                    ) > 0
                        THEN trim(split_part(f.title, ' vs. ', 1))
                END,
                is_home = CASE
                    WHEN position(
                        lower(coalesce(t.external_name, t.name)) IN
                        lower(split_part(f.title, ' vs. ', 1))
                    ) > 0
                        THEN true
                    WHEN position(
                        lower(coalesce(t.external_name, t.name)) IN
                        lower(split_part(f.title, ' vs. ', 2))
                    ) > 0
                        THEN false
                END
            FROM teams AS t
            WHERE f.team_id = t.team_id
              AND f.external_provider = 'fa_full_time'
              AND position(' vs. ' IN f.title) > 0
            """
        )
    )


def downgrade() -> None:
    op.drop_column("fixtures", "is_home")
    op.drop_column("fixtures", "opposition")
