from pydantic import BaseModel, Field
from typing import Dict, List, Optional
from datetime import datetime, timezone
import uuid


class AbilityScores(BaseModel):
    strength: int = 10
    dexterity: int = 10
    constitution: int = 10
    intelligence: int = 10
    wisdom: int = 10
    charisma: int = 10


class Item(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str = ""
    quantity: int = 1
    weight: float = 0.0
    value: int = 0  # in copper pieces


class Character(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    player_id: str
    player_name: str
    name: str
    race: str
    class_name: str
    background: str = ""
    level: int = 1
    abilities: AbilityScores = Field(default_factory=AbilityScores)
    max_hp: int = 10
    current_hp: int = 10
    temp_hp: int = 0
    armor_class: int = 10
    speed: int = 30
    proficiency_bonus: int = 2
    skills: Dict[str, bool] = Field(default_factory=dict)
    inventory: List[Item] = Field(default_factory=list)
    actions: List[str] = Field(default_factory=list)
    known_spells: List[str] = Field(default_factory=list)
    spell_slots: Dict[int, int] = Field(default_factory=dict)
    conditions: List[str] = Field(default_factory=list)
    xp: int = 0
    backstory: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


SKILL_ABILITY_MAP: Dict[str, str] = {
    "athletics": "strength",
    "acrobatics": "dexterity",
    "sleight_of_hand": "dexterity",
    "stealth": "dexterity",
    "arcana": "intelligence",
    "history": "intelligence",
    "investigation": "intelligence",
    "nature": "intelligence",
    "religion": "intelligence",
    "animal_handling": "wisdom",
    "insight": "wisdom",
    "medicine": "wisdom",
    "perception": "wisdom",
    "survival": "wisdom",
    "deception": "charisma",
    "intimidation": "charisma",
    "performance": "charisma",
    "persuasion": "charisma",
}

RACES = [
    "Human", "Elf", "Dwarf", "Halfling", "Gnome",
    "Half-Elf", "Half-Orc", "Tiefling", "Dragonborn",
]

CLASSES = [
    "Barbarian", "Bard", "Cleric", "Druid", "Fighter",
    "Monk", "Paladin", "Ranger", "Rogue", "Sorcerer",
    "Warlock", "Wizard",
]

BACKGROUNDS = [
    "Acolyte", "Charlatan", "Criminal", "Entertainer",
    "Folk Hero", "Guild Artisan", "Hermit", "Noble",
    "Outlander", "Sage", "Sailor", "Soldier", "Urchin",
]
