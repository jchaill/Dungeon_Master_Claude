import random
import re
from dataclasses import dataclass, field
from typing import List


@dataclass
class DiceResult:
    notation: str
    rolls: List[int]
    modifier: int
    total: int
    description: str = ""


def roll(notation: str) -> DiceResult:
    """Parse and roll dice notation like '2d6+3', 'd20', '1d4-1'."""
    notation = notation.strip().lower()
    pattern = r"^(\d*)d(\d+)([+-]\d+)?$"
    match = re.match(pattern, notation)
    if not match:
        raise ValueError(f"Invalid dice notation: {notation}")

    count_str, sides_str, modifier_str = match.groups()
    count = int(count_str) if count_str else 1
    sides = int(sides_str)
    modifier = int(modifier_str) if modifier_str else 0

    if count < 1 or count > 100:
        raise ValueError(f"Dice count must be between 1 and 100, got {count}")
    if sides not in (4, 6, 8, 10, 12, 20, 100):
        raise ValueError(f"Invalid die type: d{sides}")

    rolls = [random.randint(1, sides) for _ in range(count)]
    total = sum(rolls) + modifier

    description = f"Rolled {notation}: [{', '.join(str(r) for r in rolls)}]"
    if modifier > 0:
        description += f" + {modifier}"
    elif modifier < 0:
        description += f" - {abs(modifier)}"
    description += f" = {total}"

    return DiceResult(notation=notation, rolls=rolls, modifier=modifier, total=total, description=description)


def roll_ability_score() -> DiceResult:
    """Roll 4d6, drop the lowest."""
    rolls = sorted([random.randint(1, 6) for _ in range(4)])
    kept = rolls[1:]  # drop lowest
    total = sum(kept)
    return DiceResult(
        notation="4d6kh3",
        rolls=rolls,
        modifier=0,
        total=total,
        description=f"Rolled 4d6 drop lowest: {rolls} → kept {kept} = {total}",
    )


STANDARD_ARRAY = [15, 14, 13, 12, 10, 8]


def point_buy_cost(score: int) -> int:
    """Return the point buy cost for an ability score (D&D 5e standard)."""
    costs = {8: 0, 9: 1, 10: 2, 11: 3, 12: 4, 13: 5, 14: 7, 15: 9}
    if score not in costs:
        raise ValueError(f"Point buy score must be 8-15, got {score}")
    return costs[score]


def validate_point_buy(scores: dict) -> tuple[bool, int]:
    """Validate a point buy spread. Returns (valid, points_spent)."""
    total = 0
    try:
        for score in scores.values():
            total += point_buy_cost(score)
    except ValueError:
        return False, total
    return total <= 27, total
