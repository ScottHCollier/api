"""Add private club document metadata."""

import sqlalchemy as sa
from alembic import op

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "club_documents",
        sa.Column(
            "document_id",
            sa.UUID(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("club_id", sa.UUID(), nullable=False),
        sa.Column("player_id", sa.UUID(), nullable=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("object_key", sa.String(1024), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["club_id"], ["clubs.club_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["player_id"], ["players.player_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("document_id"),
        sa.UniqueConstraint("object_key"),
    )
    op.create_index("ix_club_documents_club_id", "club_documents", ["club_id"])
    op.create_index("ix_club_documents_player_id", "club_documents", ["player_id"])


def downgrade() -> None:
    op.drop_index("ix_club_documents_player_id", table_name="club_documents")
    op.drop_index("ix_club_documents_club_id", table_name="club_documents")
    op.drop_table("club_documents")
