"""Add public club contact details."""

import sqlalchemy as sa
from alembic import op

revision = "0032"
down_revision = "0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("clubs", sa.Column("contact_email", sa.String(320), nullable=True))
    op.add_column("clubs", sa.Column("contact_phone", sa.String(50), nullable=True))
    op.add_column("clubs", sa.Column("contact_address", sa.String(500), nullable=True))
    op.add_column("clubs", sa.Column("contact_description", sa.String(1000), nullable=True))
    op.add_column("clubs", sa.Column("instagram_url", sa.String(2048), nullable=True))
    op.add_column("clubs", sa.Column("facebook_url", sa.String(2048), nullable=True))


def downgrade() -> None:
    op.drop_column("clubs", "facebook_url")
    op.drop_column("clubs", "instagram_url")
    op.drop_column("clubs", "contact_description")
    op.drop_column("clubs", "contact_address")
    op.drop_column("clubs", "contact_phone")
    op.drop_column("clubs", "contact_email")
