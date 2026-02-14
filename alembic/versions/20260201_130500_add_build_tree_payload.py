"""Add tree snapshot/payload to builds

Revision ID: 5f2a1c7b9d12
Revises: 8b8e3f4c2d1a
Create Date: 2026-02-01 13:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "5f2a1c7b9d12"
down_revision: Union[str, None] = "8b8e3f4c2d1a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "builds",
        sa.Column("tree_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "builds",
        sa.Column("tree_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("builds", "tree_payload")
    op.drop_column("builds", "tree_snapshot")
