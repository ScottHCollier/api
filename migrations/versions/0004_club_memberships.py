"""Add user memberships and roles for clubs."""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "club_memberships",
        sa.Column(
            "membership_id",
            sa.UUID(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("club_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.CheckConstraint(
            "role IN ('member', 'coach', 'admin', 'owner')",
            name="ck_club_memberships_role",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["club_id"], ["clubs.club_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("membership_id", name="pk_club_memberships"),
        sa.UniqueConstraint("user_id", "club_id", name="uq_club_memberships_user_club"),
    )
    op.create_index("ix_club_memberships_user_id", "club_memberships", ["user_id"])
    op.create_index("ix_club_memberships_club_id", "club_memberships", ["club_id"])


def downgrade() -> None:
    op.drop_index("ix_club_memberships_club_id", table_name="club_memberships")
    op.drop_index("ix_club_memberships_user_id", table_name="club_memberships")
    op.drop_table("club_memberships")
