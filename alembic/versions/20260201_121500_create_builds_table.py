"""Create builds table

Revision ID: 8b8e3f4c2d1a
Revises: c970e3b310cd
Create Date: 2026-02-01 12:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "8b8e3f4c2d1a"
down_revision: Union[str, None] = "c970e3b310cd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "builds",
        sa.Column("id", sa.String(length=255), nullable=False),
        sa.Column("wow_class", sa.String(length=50), nullable=False),
        sa.Column("wow_spec", sa.String(length=50), nullable=False),
        sa.Column("wow_role", sa.String(length=20), nullable=False),
        sa.Column("environment", sa.String(length=20), nullable=False),
        sa.Column("build_mode", sa.String(length=20), nullable=False),
        sa.Column("scenario", sa.String(length=60), nullable=False),
        sa.Column("source", sa.String(length=120), nullable=True),
        sa.Column("import_code", sa.String(length=1024), nullable=False),
        sa.Column("patch", sa.String(length=30), nullable=True),
        sa.Column("tree_snapshot_id", sa.String(length=120), nullable=True),
        sa.Column("tree_snapshot_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("selected_nodes", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("selections", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_builds_wow_class"), "builds", ["wow_class"], unique=False)
    op.create_index(op.f("ix_builds_wow_spec"), "builds", ["wow_spec"], unique=False)
    op.create_index(op.f("ix_builds_wow_role"), "builds", ["wow_role"], unique=False)
    op.create_index(op.f("ix_builds_environment"), "builds", ["environment"], unique=False)
    op.create_index(op.f("ix_builds_build_mode"), "builds", ["build_mode"], unique=False)
    op.create_index(op.f("ix_builds_scenario"), "builds", ["scenario"], unique=False)
    op.create_index(op.f("ix_builds_import_code"), "builds", ["import_code"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_builds_import_code"), table_name="builds")
    op.drop_index(op.f("ix_builds_scenario"), table_name="builds")
    op.drop_index(op.f("ix_builds_build_mode"), table_name="builds")
    op.drop_index(op.f("ix_builds_environment"), table_name="builds")
    op.drop_index(op.f("ix_builds_wow_role"), table_name="builds")
    op.drop_index(op.f("ix_builds_wow_spec"), table_name="builds")
    op.drop_index(op.f("ix_builds_wow_class"), table_name="builds")
    op.drop_table("builds")
