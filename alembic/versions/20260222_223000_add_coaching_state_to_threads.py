"""Add coaching_state to threads

Revision ID: a93c7f5ef321
Revises: d7a1f329b0f1
Create Date: 2026-02-22 22:30:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a93c7f5ef321"
down_revision: Union[str, None] = "d7a1f329b0f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "threads",
        sa.Column("coaching_state", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("threads", "coaching_state")
