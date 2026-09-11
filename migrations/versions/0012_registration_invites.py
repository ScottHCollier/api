"""Add single-use parent registration invitations."""

import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "registration_invites",
        sa.Column(
            "invite_id",
            sa.UUID(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("registration_id", sa.UUID(), nullable=False),
        sa.Column("invited_email", sa.String(320), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["registration_id"],
            ["player_registrations.registration_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("invite_id", name="pk_registration_invites"),
        sa.UniqueConstraint(
            "registration_id", name="uq_registration_invites_registration_id"
        ),
        sa.UniqueConstraint("token_hash", name="uq_registration_invites_token_hash"),
    )
    op.create_index(
        "ix_registration_invites_token_hash", "registration_invites", ["token_hash"]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_registration_invites_token_hash", table_name="registration_invites"
    )
    op.drop_table("registration_invites")
