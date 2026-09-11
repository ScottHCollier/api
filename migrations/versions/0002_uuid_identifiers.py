"""Use explicit UUID primary keys, preserving records and club relationships.

Downgrade keeps club/team UUIDs as text IDs; original legacy IDs cannot be restored.
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table, key in (("clubs", "club_id"), ("teams", "team_id")):
        op.add_column(
            table,
            sa.Column(
                key,
                sa.UUID(),
                nullable=False,
                server_default=sa.text("gen_random_uuid()"),
            ),
        )
        # Preserve UUIDs if upgrading again after a downgrade to the text schema.
        op.execute(
            sa.text(
                f"UPDATE {table} SET {key} = id::uuid "
                "WHERE id ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
                "[0-9a-f]{4}-[0-9a-f]{12}$'"
            )
        )

    for table in ("club_domains", "teams"):
        op.add_column(table, sa.Column("new_club_id", sa.UUID(), nullable=True))
        op.execute(
            sa.text(
                f"UPDATE {table} AS child SET new_club_id = clubs.club_id "
                "FROM clubs WHERE child.club_id = clubs.id"
            )
        )
        op.drop_constraint(f"fk_{table}_club_id_clubs", table, type_="foreignkey")
        op.drop_index(f"ix_{table}_club_id", table_name=table)
        if table == "teams":
            op.drop_constraint("uq_teams_club_id", "teams", type_="unique")
        op.drop_column(table, "club_id")
        op.alter_column(table, "new_club_id", new_column_name="club_id", nullable=False)
        op.create_index(f"ix_{table}_club_id", table, ["club_id"])

    for table, key in (("clubs", "club_id"), ("teams", "team_id")):
        op.drop_constraint(f"pk_{table}", table, type_="primary")
        op.drop_column(table, "id")
        op.create_primary_key(f"pk_{table}", table, [key])

    op.add_column(
        "club_domains",
        sa.Column(
            "club_domain_id",
            sa.UUID(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
    )
    op.drop_constraint("pk_club_domains", "club_domains", type_="primary")
    op.create_primary_key("pk_club_domains", "club_domains", ["club_domain_id"])
    op.create_unique_constraint(
        "uq_club_domains_hostname", "club_domains", ["hostname"]
    )
    op.create_unique_constraint("uq_teams_club_id", "teams", ["club_id", "name"])
    for table in ("club_domains", "teams"):
        op.create_foreign_key(
            f"fk_{table}_club_id_clubs",
            table,
            "clubs",
            ["club_id"],
            ["club_id"],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    for table in ("club_domains", "teams"):
        op.drop_constraint(f"fk_{table}_club_id_clubs", table, type_="foreignkey")
        op.alter_column(
            table, "club_id", type_=sa.String(64), postgresql_using="club_id::text"
        )
    for table, key, length in (("clubs", "club_id", 64), ("teams", "team_id", 100)):
        op.alter_column(table, key, server_default=None)
        op.alter_column(
            table,
            key,
            new_column_name="id",
            type_=sa.String(length),
            postgresql_using=f"{key}::text",
        )
    op.drop_constraint("pk_club_domains", "club_domains", type_="primary")
    op.drop_column("club_domains", "club_domain_id")
    op.drop_constraint("uq_club_domains_hostname", "club_domains", type_="unique")
    op.create_primary_key("pk_club_domains", "club_domains", ["hostname"])
    for table in ("club_domains", "teams"):
        op.create_foreign_key(
            f"fk_{table}_club_id_clubs",
            table,
            "clubs",
            ["club_id"],
            ["id"],
            ondelete="CASCADE",
        )
