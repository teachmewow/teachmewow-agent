"""
World of Warcraft specialization enum.

Values use WoW-canonical names matching the manifest and database.
Ambiguous specs (frost, holy, protection, restoration) are disambiguated
by querying with (class, spec) as a composite key — the spec value alone
may not be unique across classes.

See CLAUDE.md "Spec naming convention" for the full rationale.
"""

from enum import StrEnum


class WowSpec(StrEnum):
    """World of Warcraft specializations — WoW-canonical names."""

    # Warrior
    ARMS = "arms"
    FURY = "fury"
    PROTECTION = "protection"

    # Paladin
    HOLY = "holy"
    RETRIBUTION = "retribution"
    # protection — reuses PROTECTION (same WoW name, disambiguated by class)

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
    SHADOW = "shadow"
    # holy — reuses HOLY

    # Death Knight
    BLOOD = "blood"
    FROST = "frost"
    UNHOLY = "unholy"

    # Shaman
    ELEMENTAL = "elemental"
    ENHANCEMENT = "enhancement"
    RESTORATION = "restoration"

    # Mage
    ARCANE = "arcane"
    FIRE = "fire"
    # frost — reuses FROST

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
    # restoration — reuses RESTORATION

    # Demon Hunter
    HAVOC = "havoc"
    VENGEANCE = "vengeance"
    DEVOURER = "devourer"

    # Evoker
    DEVASTATION = "devastation"
    PRESERVATION = "preservation"
    AUGMENTATION = "augmentation"
