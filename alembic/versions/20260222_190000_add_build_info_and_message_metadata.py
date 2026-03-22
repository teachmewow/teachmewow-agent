"""Add active_build_info to threads and response_metadata to messages

Revision ID: d7a1f329b0f1
Revises: c1f0b6a98d42
Create Date: 2026-02-22 19:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "d7a1f329b0f1"
down_revision: Union[str, None] = "c1f0b6a98d42"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "threads",
        sa.Column("active_build_info", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "messages",
        sa.Column("response_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("messages", "response_metadata")
    op.drop_column("threads", "active_build_info")
