from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from ..services.dice_roller import roll
from ..utils.logger import logger


@dataclass
class CombatantEntry:
    id: str
    name: str
    initiative: int
    hp: int
    max_hp: int
    is_player: bool
    conditions: List[str] = field(default_factory=list)


class CombatManager:
    def __init__(self, campaign_id: str):
        self.campaign_id = campaign_id
        self.combatants: List[CombatantEntry] = []
        self.current_index: int = 0
        self.round_number: int = 0
        self.is_active: bool = False

    def start_combat(self, participants: List[dict]) -> List[CombatantEntry]:
        """
        participants: list of dicts with keys: id, name, dex_modifier, hp, max_hp, is_player
        Returns sorted initiative order.
        """
        self.combatants = []
        for p in participants:
            initiative_roll = roll("d20")
            initiative = initiative_roll.total + p.get("dex_modifier", 0)
            entry = CombatantEntry(
                id=p["id"],
                name=p["name"],
                initiative=initiative,
                hp=p.get("hp", 10),
                max_hp=p.get("max_hp", 10),
                is_player=p.get("is_player", True),
            )
            self.combatants.append(entry)
            logger.debug(f"Initiative roll for {p['name']}: {initiative_roll.total} + {p.get('dex_modifier', 0)} = {initiative}")

        # Sort by initiative descending, ties broken by dex modifier
        self.combatants.sort(key=lambda c: c.initiative, reverse=True)
        self.current_index = 0
        self.round_number = 1
        self.is_active = True
        logger.info(f"Combat started for campaign {self.campaign_id} with {len(self.combatants)} combatants")
        return self.combatants

    def current_combatant(self) -> Optional[CombatantEntry]:
        if not self.combatants or not self.is_active:
            return None
        return self.combatants[self.current_index]

    def next_turn(self) -> Tuple[CombatantEntry, bool]:
        """Advance to the next combatant. Returns (next_combatant, new_round)."""
        if not self.is_active:
            raise ValueError("Combat is not active")
        self.current_index = (self.current_index + 1) % len(self.combatants)
        new_round = self.current_index == 0
        if new_round:
            self.round_number += 1
            logger.info(f"Round {self.round_number} started")
        return self.combatants[self.current_index], new_round

    def apply_damage(self, combatant_id: str, damage: int) -> CombatantEntry:
        for c in self.combatants:
            if c.id == combatant_id:
                c.hp = max(0, c.hp - damage)
                if c.hp == 0:
                    c.conditions.append("unconscious")
                return c
        raise ValueError(f"Combatant {combatant_id} not found")

    def apply_healing(self, combatant_id: str, amount: int) -> CombatantEntry:
        for c in self.combatants:
            if c.id == combatant_id:
                c.hp = min(c.max_hp, c.hp + amount)
                if "unconscious" in c.conditions and c.hp > 0:
                    c.conditions.remove("unconscious")
                return c
        raise ValueError(f"Combatant {combatant_id} not found")

    def remove_combatant(self, combatant_id: str):
        self.combatants = [c for c in self.combatants if c.id != combatant_id]
        if self.current_index >= len(self.combatants) and self.combatants:
            self.current_index = 0

    def end_combat(self):
        self.is_active = False
        self.combatants = []
        self.current_index = 0
        self.round_number = 0
        logger.info(f"Combat ended for campaign {self.campaign_id}")

    def to_dict(self) -> dict:
        return {
            "campaign_id": self.campaign_id,
            "is_active": self.is_active,
            "round_number": self.round_number,
            "current_index": self.current_index,
            "combatants": [
                {
                    "id": c.id,
                    "name": c.name,
                    "initiative": c.initiative,
                    "hp": c.hp,
                    "max_hp": c.max_hp,
                    "is_player": c.is_player,
                    "conditions": c.conditions,
                }
                for c in self.combatants
            ],
        }


# Global registry of active combat managers per campaign
_combat_managers: Dict[str, CombatManager] = {}


def get_combat_manager(campaign_id: str) -> CombatManager:
    if campaign_id not in _combat_managers:
        _combat_managers[campaign_id] = CombatManager(campaign_id)
    return _combat_managers[campaign_id]
