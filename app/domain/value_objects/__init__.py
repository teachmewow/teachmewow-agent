"""
Value objects for the domain layer.
Immutable objects that represent domain concepts.
"""

from .message_role import MessageRole
from .wow_class import WowClass
from .wow_spec import WowSpec

__all__ = ["MessageRole", "WowClass", "WowSpec"]
