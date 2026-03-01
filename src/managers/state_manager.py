import json
import uuid
from datetime import datetime, timezone
from typing import List, Optional
import aiosqlite

from ..config import settings
from ..models.campaign import CampaignState
from ..models.character import Character
from ..utils.logger import logger


async def init_db():
    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS campaigns (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                dm_id TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_played TIMESTAMP,
                state TEXT NOT NULL,
                is_active BOOLEAN DEFAULT 1
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS players (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                campaign_id TEXT REFERENCES campaigns(id),
                session_token TEXT,
                is_dm BOOLEAN DEFAULT 0,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS characters (
                id TEXT PRIMARY KEY,
                player_id TEXT REFERENCES players(id),
                campaign_id TEXT REFERENCES campaigns(id),
                data TEXT NOT NULL,
                is_active BOOLEAN DEFAULT 1
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                campaign_id TEXT REFERENCES campaigns(id),
                sender_id TEXT REFERENCES players(id),
                sender_type TEXT CHECK (sender_type IN ('player', 'dm', 'system', 'roll')),
                content TEXT NOT NULL,
                metadata TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()
    logger.info("Database initialized")


# --- Campaign CRUD ---

async def create_campaign(name: str, dm_id: str) -> CampaignState:
    campaign = CampaignState(name=name, dm_id=dm_id)
    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.execute(
            "INSERT INTO campaigns (id, name, dm_id, state) VALUES (?, ?, ?, ?)",
            (campaign.id, campaign.name, campaign.dm_id, campaign.model_dump_json()),
        )
        await db.commit()
    logger.info(f"Created campaign: {campaign.id} - {campaign.name}")
    return campaign


async def get_campaign(campaign_id: str) -> Optional[CampaignState]:
    async with aiosqlite.connect(settings.DB_PATH) as db:
        async with db.execute(
            "SELECT state FROM campaigns WHERE id = ?", (campaign_id,)
        ) as cursor:
            row = await cursor.fetchone()
    if row:
        return CampaignState.model_validate_json(row[0])
    return None


async def list_campaigns() -> List[dict]:
    async with aiosqlite.connect(settings.DB_PATH) as db:
        async with db.execute(
            "SELECT id, name, dm_id, created_at, last_played, is_active FROM campaigns ORDER BY last_played DESC"
        ) as cursor:
            rows = await cursor.fetchall()
    return [
        {
            "id": r[0],
            "name": r[1],
            "dm_id": r[2],
            "created_at": r[3],
            "last_played": r[4],
            "is_active": bool(r[5]),
        }
        for r in rows
    ]


async def delete_campaign(campaign_id: str):
    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.execute("DELETE FROM messages WHERE campaign_id = ?", (campaign_id,))
        await db.execute("DELETE FROM characters WHERE campaign_id = ?", (campaign_id,))
        await db.execute("DELETE FROM players WHERE campaign_id = ?", (campaign_id,))
        await db.execute("DELETE FROM campaigns WHERE id = ?", (campaign_id,))
        await db.commit()
    logger.info(f"Deleted campaign: {campaign_id}")


async def save_campaign_state(campaign: CampaignState):
    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.execute(
            "UPDATE campaigns SET state = ?, last_played = ? WHERE id = ?",
            (campaign.model_dump_json(), datetime.now(timezone.utc).isoformat(), campaign.id),
        )
        await db.commit()


# --- Player CRUD ---

async def create_player(name: str, campaign_id: str, is_dm: bool = False) -> dict:
    player_id = str(uuid.uuid4())
    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.execute(
            "INSERT INTO players (id, name, campaign_id, is_dm) VALUES (?, ?, ?, ?)",
            (player_id, name, campaign_id, int(is_dm)),
        )
        await db.commit()
    return {"id": player_id, "name": name, "campaign_id": campaign_id, "is_dm": is_dm}


async def get_player(player_id: str) -> Optional[dict]:
    async with aiosqlite.connect(settings.DB_PATH) as db:
        async with db.execute(
            "SELECT id, name, campaign_id, is_dm FROM players WHERE id = ?", (player_id,)
        ) as cursor:
            row = await cursor.fetchone()
    if row:
        return {"id": row[0], "name": row[1], "campaign_id": row[2], "is_dm": bool(row[3])}
    return None


async def get_campaign_players(campaign_id: str) -> List[dict]:
    async with aiosqlite.connect(settings.DB_PATH) as db:
        async with db.execute(
            "SELECT id, name, campaign_id, is_dm, joined_at FROM players WHERE campaign_id = ?",
            (campaign_id,),
        ) as cursor:
            rows = await cursor.fetchall()
    return [
        {"id": r[0], "name": r[1], "campaign_id": r[2], "is_dm": bool(r[3]), "joined_at": r[4]}
        for r in rows
    ]


async def update_player_token(player_id: str, token: str):
    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.execute(
            "UPDATE players SET session_token = ? WHERE id = ?", (token, player_id)
        )
        await db.commit()


# --- Character CRUD ---

async def create_character(character: Character) -> Character:
    async with aiosqlite.connect(settings.DB_PATH) as db:
        # Determine campaign_id from player
        async with db.execute(
            "SELECT campaign_id FROM players WHERE id = ?", (character.player_id,)
        ) as cursor:
            row = await cursor.fetchone()
        campaign_id = row[0] if row else None
        await db.execute(
            "INSERT INTO characters (id, player_id, campaign_id, data) VALUES (?, ?, ?, ?)",
            (character.id, character.player_id, campaign_id, character.model_dump_json()),
        )
        await db.commit()
    return character


async def get_character(character_id: str) -> Optional[Character]:
    async with aiosqlite.connect(settings.DB_PATH) as db:
        async with db.execute(
            "SELECT data FROM characters WHERE id = ? AND is_active = 1", (character_id,)
        ) as cursor:
            row = await cursor.fetchone()
    if row:
        return Character.model_validate_json(row[0])
    return None


async def get_player_characters(player_id: str) -> List[Character]:
    async with aiosqlite.connect(settings.DB_PATH) as db:
        async with db.execute(
            "SELECT data FROM characters WHERE player_id = ? AND is_active = 1", (player_id,)
        ) as cursor:
            rows = await cursor.fetchall()
    return [Character.model_validate_json(r[0]) for r in rows]


async def update_character(character: Character):
    character.updated_at = datetime.now(timezone.utc)
    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.execute(
            "UPDATE characters SET data = ? WHERE id = ?",
            (character.model_dump_json(), character.id),
        )
        await db.commit()


async def delete_character(character_id: str):
    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.execute(
            "UPDATE characters SET is_active = 0 WHERE id = ?", (character_id,)
        )
        await db.commit()


# --- Messages CRUD ---

async def save_message(
    campaign_id: str,
    sender_id: str,
    sender_type: str,
    content: str,
    metadata: Optional[dict] = None,
) -> str:
    message_id = str(uuid.uuid4())
    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.execute(
            "INSERT INTO messages (id, campaign_id, sender_id, sender_type, content, metadata) VALUES (?, ?, ?, ?, ?, ?)",
            (
                message_id,
                campaign_id,
                sender_id,
                sender_type,
                content,
                json.dumps(metadata) if metadata else None,
            ),
        )
        await db.commit()
    return message_id


async def get_messages(campaign_id: str, limit: int = 50) -> List[dict]:
    async with aiosqlite.connect(settings.DB_PATH) as db:
        async with db.execute(
            "SELECT id, sender_id, sender_type, content, metadata, created_at FROM messages WHERE campaign_id = ? ORDER BY created_at DESC LIMIT ?",
            (campaign_id, limit),
        ) as cursor:
            rows = await cursor.fetchall()
    messages = []
    for r in reversed(rows):
        messages.append(
            {
                "id": r[0],
                "sender_id": r[1],
                "sender_type": r[2],
                "content": r[3],
                "metadata": json.loads(r[4]) if r[4] else None,
                "created_at": r[5],
            }
        )
    return messages
