from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timezone
import uuid


class PlayerSession(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    player_id: str
    player_name: str
    campaign_id: str
    character_id: Optional[str] = None
    is_dm: bool = False
    is_ready: bool = False
    is_connected: bool = True
    last_seen: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    client_ip: str = ""
    token: str = ""
