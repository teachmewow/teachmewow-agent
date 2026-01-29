"""
Tool: get_spec_info

Returns information about a WoW specialization.
Currently returns mock data - to be implemented with real data source.
"""

from langchain_core.tools import tool


@tool
def get_spec_info(spec_name: str) -> str:
    """
    Get information about a World of Warcraft specialization.

    Args:
        spec_name: Name of the specialization (e.g., "Arms", "Fury", "Holy")

    Returns:
        Information about the specialization including role, key abilities, and tips.
    """
    # Mock implementation - to be replaced with real data source
    spec_data = {
        "arms": {
            "class": "Warrior",
            "role": "DPS",
            "description": "A battle-hardened master of weapons, using military tactics and powerful strikes.",
            "key_abilities": ["Mortal Strike", "Colossus Smash", "Execute", "Bladestorm"],
            "tips": [
                "Maintain Colossus Smash debuff for maximum damage",
                "Use Execute during execute phase for massive damage",
                "Save Bladestorm for AoE situations",
            ],
        },
        "fury": {
            "class": "Warrior",
            "role": "DPS",
            "description": "A berserker who dual-wields weapons and thrives on rage and bloodlust.",
            "key_abilities": ["Rampage", "Raging Blow", "Bloodthirst", "Execute"],
            "tips": [
                "Keep Enrage uptime as high as possible",
                "Use Rampage to maintain Enrage",
                "Raging Blow is your filler ability",
            ],
        },
        "holy": {
            "class": "Paladin/Priest",
            "role": "Healer",
            "description": "A divine healer who uses the power of the Light to mend wounds.",
            "key_abilities": ["Flash of Light", "Holy Light", "Holy Shock", "Lay on Hands"],
            "tips": [
                "Use Holy Shock on cooldown for Infusion of Light procs",
                "Save Lay on Hands for emergencies",
                "Position yourself to maximize Beacon healing",
            ],
        },
    }

    spec_key = spec_name.lower()
    if spec_key in spec_data:
        data = spec_data[spec_key]
        return f"""
Specialization: {spec_name}
Class: {data['class']}
Role: {data['role']}
Description: {data['description']}

Key Abilities:
{chr(10).join(f'- {ability}' for ability in data['key_abilities'])}

Tips:
{chr(10).join(f'- {tip}' for tip in data['tips'])}
"""

    return f"No information found for specialization: {spec_name}. Please check the name and try again."
