"""
SQLAlchemy model for Thread.
"""

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.connection import Base


class ThreadModel(Base):
    """SQLAlchemy model for threads table."""

    __tablename__ = "threads"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    wow_class: Mapped[str] = mapped_column(String(50), nullable=False)
    wow_spec: Mapped[str] = mapped_column(String(50), nullable=False)
    wow_role: Mapped[str] = mapped_column(String(20), nullable=False)
    active_build_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    active_build_info: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    coaching_state: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
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
