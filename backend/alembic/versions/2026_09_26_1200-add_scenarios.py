"""Add forecast correction scenarios.

Revision ID: 2026_09_26_1200
Revises: a22c501118b2
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "2026_09_26_1200"
down_revision: Union[str, Sequence[str], None] = "a22c501118b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "scenarios",
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("factor", sa.String(length=64), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("routes", sa.ARRAY(sa.Integer()), nullable=True),
        sa.Column("date_from", sa.Date(), nullable=False),
        sa.Column("date_to", sa.Date(), nullable=False),
        sa.Column("days", sa.String(length=16), nullable=False),
        sa.Column("hour_from", sa.Integer(), nullable=True),
        sa.Column("hour_to", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("comment", sa.String(length=2000), nullable=True),
        sa.Column("source_url", sa.String(length=2048), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_scenarios_created_by_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scenarios")),
    )
    op.create_index(op.f("ix_scenarios_active"), "scenarios", ["active"])
    op.create_index(op.f("ix_scenarios_date_from"), "scenarios", ["date_from"])
    op.create_index(op.f("ix_scenarios_date_to"), "scenarios", ["date_to"])


def downgrade() -> None:
    op.drop_index(op.f("ix_scenarios_date_to"), table_name="scenarios")
    op.drop_index(op.f("ix_scenarios_date_from"), table_name="scenarios")
    op.drop_index(op.f("ix_scenarios_active"), table_name="scenarios")
    op.drop_table("scenarios")