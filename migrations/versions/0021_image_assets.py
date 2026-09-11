"""Add image asset storage metadata and club image selection."""

import sqlalchemy as sa
from alembic import op

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "image_assets",
        sa.Column(
            "image_id",
            sa.UUID(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("club_id", sa.UUID(), nullable=False),
        sa.Column("original_key", sa.String(1024), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=True),
        sa.Column("original_mime_type", sa.String(100), nullable=False),
        sa.Column("original_size_bytes", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("alt_text", sa.String(500), nullable=True),
        sa.Column("focal_x", sa.Float(), nullable=True),
        sa.Column("focal_y", sa.Float(), nullable=True),
        sa.Column(
            "processing_status",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("thumb_key", sa.String(1024), nullable=True),
        sa.Column("card_key", sa.String(1024), nullable=True),
        sa.Column("hero_key", sa.String(1024), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["club_id"], ["clubs.club_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("image_id"),
        sa.UniqueConstraint("original_key"),
    )
    op.create_index("ix_image_assets_club_id", "image_assets", ["club_id"])

    op.create_table(
        "club_images",
        sa.Column(
            "club_image_id",
            sa.UUID(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("club_id", sa.UUID(), nullable=False),
        sa.Column("image_id", sa.UUID(), nullable=False),
        sa.Column(
            "is_primary", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column(
            "position", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.ForeignKeyConstraint(["club_id"], ["clubs.club_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["image_id"], ["image_assets.image_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("club_image_id"),
        sa.UniqueConstraint("club_id", "image_id", name="uq_club_images_club_image"),
    )
    op.create_index("ix_club_images_club_id", "club_images", ["club_id"])
    op.create_index("ix_club_images_image_id", "club_images", ["image_id"])
    op.create_index(
        "uq_club_images_one_primary",
        "club_images",
        ["club_id"],
        unique=True,
        postgresql_where=sa.text("is_primary"),
    )


def downgrade() -> None:
    op.drop_index("uq_club_images_one_primary", table_name="club_images")
    op.drop_index("ix_club_images_image_id", table_name="club_images")
    op.drop_index("ix_club_images_club_id", table_name="club_images")
    op.drop_table("club_images")
    op.drop_index("ix_image_assets_club_id", table_name="image_assets")
    op.drop_table("image_assets")
