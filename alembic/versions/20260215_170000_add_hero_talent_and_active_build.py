"""Add hero_talent to builds and active_build_id to threads

Revision ID: c1f0b6a98d42
Revises: 5f2a1c7b9d12
Create Date: 2026-02-15 17:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "c1f0b6a98d42"
down_revision: Union[str, None] = "5f2a1c7b9d12"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("builds", sa.Column("hero_talent", sa.String(length=60), nullable=True))
    op.create_index(op.f("ix_builds_hero_talent"), "builds", ["hero_talent"], unique=False)

    op.add_column("threads", sa.Column("active_build_id", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("threads", "active_build_id")

    op.drop_index(op.f("ix_builds_hero_talent"), table_name="builds")
    op.drop_column("builds", "hero_talent")
