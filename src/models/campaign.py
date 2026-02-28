from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, timezone
import uuid

from .character import Character


class Location(BaseModel):
    name: str = "Starting Town"
    description: str = ""
    region: str = ""


class Quest(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    description: str = ""
    is_completed: bool = False
    is_main_quest: bool = False


class NPC(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str = ""
    attitude: str = "neutral"  # friendly, neutral, hostile
    location: str = ""


class GameTime(BaseModel):
    day: int = 1
    hour: int = 8
    season: str = "spring"


class CampaignState(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    dm_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_played: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    session_number: int = 1
    current_location: Location = Field(default_factory=Location)
    quests: List[Quest] = Field(default_factory=list)
    npcs_met: List[NPC] = Field(default_factory=list)
    important_events: List[str] = Field(default_factory=list)
    in_game_time: GameTime = Field(default_factory=GameTime)
    player_characters: List[Character] = Field(default_factory=list)
    initiative_order: List[str] = Field(default_factory=list)
    is_combat_active: bool = False
    is_paused: bool = False
    is_active: bool = True
