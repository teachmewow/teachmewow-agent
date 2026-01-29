"""
World of Warcraft class enum.
"""

from enum import StrEnum


class WowClass(StrEnum):
    """World of Warcraft playable classes."""

    WARRIOR = "warrior"
    PALADIN = "paladin"
    HUNTER = "hunter"
    ROGUE = "rogue"
    PRIEST = "priest"
    DEATH_KNIGHT = "death-knight"
    SHAMAN = "shaman"
    MAGE = "mage"
    WARLOCK = "warlock"
    MONK = "monk"
    DRUID = "druid"
    DEMON_HUNTER = "demon-hunter"
    EVOKER = "evoker"
