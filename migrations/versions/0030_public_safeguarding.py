"""Add public safeguarding contacts and document visibility."""

import sqlalchemy as sa
from alembic import op

revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "clubs", sa.Column("safeguarding_contact_name", sa.String(200), nullable=True)
    )
    op.add_column(
        "clubs", sa.Column("safeguarding_contact_email", sa.String(320), nullable=True)
    )
    op.add_column(
        "clubs", sa.Column("safeguarding_contact_phone", sa.String(50), nullable=True)
    )
    op.add_column(
        "club_documents",
        sa.Column(
            "is_public", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
    )


def downgrade() -> None:
    op.drop_column("club_documents", "is_public")
    op.drop_column("clubs", "safeguarding_contact_phone")
    op.drop_column("clubs", "safeguarding_contact_email")
    op.drop_column("clubs", "safeguarding_contact_name")
