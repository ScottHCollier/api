"""Add folders and editable filenames to the image library."""

import sqlalchemy as sa
from alembic import op

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "image_folders",
        sa.Column(
            "folder_id",
            sa.UUID(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("club_id", sa.UUID(), nullable=False),
        sa.Column("parent_id", sa.UUID(), nullable=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["club_id"], ["clubs.club_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["parent_id"], ["image_folders.folder_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("folder_id"),
        sa.UniqueConstraint("club_id", "parent_id", "name"),
    )
    op.create_index("ix_image_folders_club_id", "image_folders", ["club_id"])
    op.create_index("ix_image_folders_parent_id", "image_folders", ["parent_id"])
    op.add_column("image_assets", sa.Column("folder_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_image_assets_folder_id",
        "image_assets",
        "image_folders",
        ["folder_id"],
        ["folder_id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_image_assets_folder_id", "image_assets", ["folder_id"])


def downgrade() -> None:
    op.drop_index("ix_image_assets_folder_id", table_name="image_assets")
    op.drop_constraint("fk_image_assets_folder_id", "image_assets", type_="foreignkey")
    op.drop_column("image_assets", "folder_id")
    op.drop_index("ix_image_folders_parent_id", table_name="image_folders")
    op.drop_index("ix_image_folders_club_id", table_name="image_folders")
    op.drop_table("image_folders")
