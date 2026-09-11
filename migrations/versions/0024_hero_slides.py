"""Add configurable three-slide public hero content."""

import sqlalchemy as sa
from alembic import op

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hero_slides",
        sa.Column(
            "slide_id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("club_id", sa.UUID(), nullable=False),
        sa.Column("image_id", sa.UUID(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column(
            "eyebrow",
            sa.String(100),
            server_default=sa.text("'ONE CLUB. EVERYONE COUNTS.'"),
            nullable=False,
        ),
        sa.Column(
            "title",
            sa.String(300),
            server_default=sa.text("'More than a football club.'"),
            nullable=False,
        ),
        sa.Column("body", sa.String(500), server_default=sa.text("''"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["club_id"], ["clubs.club_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["image_id"], ["image_assets.image_id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("slide_id"),
        sa.UniqueConstraint("club_id", "position"),
    )
    op.create_index("ix_hero_slides_club_id", "hero_slides", ["club_id"])


def downgrade() -> None:
    op.drop_index("ix_hero_slides_club_id", table_name="hero_slides")
    op.drop_table("hero_slides")
