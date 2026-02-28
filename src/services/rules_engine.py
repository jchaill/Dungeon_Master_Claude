from typing import Dict

from ..models.character import SKILL_ABILITY_MAP


CLASS_HIT_DICE: Dict[str, int] = {
    "Barbarian": 12,
    "Fighter": 10,
    "Paladin": 10,
    "Ranger": 10,
    "Bard": 8,
    "Cleric": 8,
    "Druid": 8,
    "Monk": 8,
    "Rogue": 8,
    "Warlock": 8,
    "Sorcerer": 6,
    "Wizard": 6,
}

ARMOR_AC: Dict[str, int] = {
    "none": 10,
    "leather": 11,
    "studded leather": 12,
    "hide": 12,
    "chain shirt": 13,
    "scale mail": 14,
    "breastplate": 14,
    "half plate": 15,
    "ring mail": 14,
    "chain mail": 16,
    "splint": 17,
    "plate": 18,
    "shield": 2,  # bonus
}


def ability_modifier(score: int) -> int:
    return (score - 10) // 2


def proficiency_bonus(level: int) -> int:
    return (level - 1) // 4 + 2


def get_class_hit_die(class_name: str) -> int:
    return CLASS_HIT_DICE.get(class_name, 8)


def calculate_hp(class_name: str, level: int, con_mod: int) -> int:
    hit_die = get_class_hit_die(class_name)
    # Level 1: max hit die + con modifier
    # Levels 2+: average (hit_die / 2 + 1) + con modifier per level
    if level == 1:
        return max(1, hit_die + con_mod)
    average_per_level = hit_die // 2 + 1
    return max(level, hit_die + con_mod + (level - 1) * (average_per_level + con_mod))


def calculate_ac(dex_mod: int, armor: str = "none", shield: bool = False) -> int:
    armor = armor.lower()
    if armor in ("none", ""):
        base_ac = 10 + dex_mod
    elif armor in ("leather", "studded leather"):
        base_ac = ARMOR_AC[armor] + dex_mod
    elif armor in ("hide", "chain shirt", "scale mail", "breastplate"):
        base_ac = ARMOR_AC[armor] + min(dex_mod, 2)
    elif armor in ("half plate",):
        base_ac = ARMOR_AC[armor] + min(dex_mod, 2)
    else:
        # Heavy armor — no dex bonus
        base_ac = ARMOR_AC.get(armor, 10)
    if shield:
        base_ac += 2
    return base_ac


def skill_check_modifier(
    skill: str,
    abilities: dict,
    proficiencies: dict,
    prof_bonus: int,
) -> int:
    ability = SKILL_ABILITY_MAP.get(skill.lower().replace(" ", "_"), "dexterity")
    score = abilities.get(ability, 10)
    mod = ability_modifier(score)
    if proficiencies.get(skill, False):
        mod += prof_bonus
    return mod


def xp_for_level(level: int) -> int:
    thresholds = [0, 300, 900, 2700, 6500, 14000, 23000, 34000, 48000, 64000,
                  85000, 100000, 120000, 140000, 165000, 195000, 225000, 265000, 305000, 355000]
    if 1 <= level <= 20:
        return thresholds[level - 1]
    return 0
