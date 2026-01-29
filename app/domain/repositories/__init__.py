"""
Repository interfaces (protocols) for domain persistence.
"""

from .message_repository import MessageRepository
from .thread_repository import ThreadRepository

__all__ = ["MessageRepository", "ThreadRepository"]
