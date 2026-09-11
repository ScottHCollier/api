"""Create clubs, registered domains and teams."""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "clubs",
        sa.Column("id", sa.String(64), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("badge_url", sa.String(2048), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_clubs"),
        sa.UniqueConstraint("slug", name="uq_clubs_slug"),
    )
    op.create_table(
        "club_domains",
        sa.Column("hostname", sa.String(253), nullable=False),
        sa.Column("club_id", sa.String(64), nullable=False),
        sa.ForeignKeyConstraint(
            ["club_id"],
            ["clubs.id"],
            name="fk_club_domains_club_id_clubs",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("hostname", name="pk_club_domains"),
    )
    op.create_index("ix_club_domains_club_id", "club_domains", ["club_id"])
    op.create_table(
        "teams",
        sa.Column("id", sa.String(100), nullable=False),
        sa.Column("club_id", sa.String(64), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.ForeignKeyConstraint(
            ["club_id"],
            ["clubs.id"],
            name="fk_teams_club_id_clubs",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_teams"),
        sa.UniqueConstraint("club_id", "name", name="uq_teams_club_id"),
    )
    op.create_index("ix_teams_club_id", "teams", ["club_id"])


def downgrade() -> None:
    op.drop_index("ix_teams_club_id", table_name="teams")
    op.drop_table("teams")
    op.drop_index("ix_club_domains_club_id", table_name="club_domains")
    op.drop_table("club_domains")
    op.drop_table("clubs")
