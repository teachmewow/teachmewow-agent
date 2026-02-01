"""
SQLAlchemy model for Build.
"""

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.connection import Base


class BuildModel(Base):
    """SQLAlchemy model for builds table."""

    __tablename__ = "builds"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    wow_class: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    wow_spec: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    wow_role: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    environment: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    build_mode: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    scenario: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(120), nullable=True)
    import_code: Mapped[str] = mapped_column(String(1024), nullable=False)
    patch: Mapped[str | None] = mapped_column(String(30), nullable=True)
    tree_snapshot_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    tree_snapshot_ids: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    selected_nodes: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    selections: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    tree_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    tree_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
