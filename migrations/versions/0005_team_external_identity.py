"""Store external team identities for fixture providers."""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("teams", sa.Column("external_provider", sa.String(50)))
    op.add_column("teams", sa.Column("external_id", sa.String(100)))
    op.add_column("teams", sa.Column("external_name", sa.String(200)))
    op.add_column("teams", sa.Column("external_url", sa.String(2048)))
    op.create_unique_constraint(
        "uq_teams_external_provider_id",
        "teams",
        ["external_provider", "external_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_teams_external_provider_id", "teams", type_="unique")
    op.drop_column("teams", "external_url")
    op.drop_column("teams", "external_name")
    op.drop_column("teams", "external_id")
    op.drop_column("teams", "external_provider")
