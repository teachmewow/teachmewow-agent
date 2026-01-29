"""
World of Warcraft specialization enum.
"""

from enum import StrEnum


class WowSpec(StrEnum):
    """World of Warcraft specializations."""

    # Warrior
    ARMS = "arms"
    FURY = "fury"
    PROTECTION_WARRIOR = "protection-warrior"

    # Paladin
    HOLY_PALADIN = "holy-paladin"
    PROTECTION_PALADIN = "protection-paladin"
    RETRIBUTION = "retribution"

    # Hunter
    BEAST_MASTERY = "beast-mastery"
    MARKSMANSHIP = "marksmanship"
    SURVIVAL = "survival"

    # Rogue
    ASSASSINATION = "assassination"
    OUTLAW = "outlaw"
    SUBTLETY = "subtlety"

    # Priest
    DISCIPLINE = "discipline"
    HOLY_PRIEST = "holy-priest"
    SHADOW = "shadow"

    # Death Knight
    BLOOD = "blood"
    FROST_DK = "frost-dk"
    UNHOLY = "unholy"

    # Shaman
    ELEMENTAL = "elemental"
    ENHANCEMENT = "enhancement"
    RESTORATION_SHAMAN = "restoration-shaman"

    # Mage
    ARCANE = "arcane"
    FIRE = "fire"
    FROST_MAGE = "frost-mage"

    # Warlock
    AFFLICTION = "affliction"
    DEMONOLOGY = "demonology"
    DESTRUCTION = "destruction"

    # Monk
    BREWMASTER = "brewmaster"
    MISTWEAVER = "mistweaver"
    WINDWALKER = "windwalker"

    # Druid
    BALANCE = "balance"
    FERAL = "feral"
    GUARDIAN = "guardian"
    RESTORATION_DRUID = "restoration-druid"

    # Demon Hunter
    HAVOC = "havoc"
    VENGEANCE = "vengeance"

    # Evoker
    DEVASTATION = "devastation"
    PRESERVATION = "preservation"
    AUGMENTATION = "augmentation"
