from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import List, Optional
import os

from .auth import get_current_session, get_current_dm, get_optional_session
from ..models.session import PlayerSession
from ..models.character import Character, AbilityScores, Item, RACES, CLASSES, BACKGROUNDS
from ..models.campaign import CampaignState
from ..managers import state_manager, session_manager, combat_manager as cm
from ..services.dice_roller import roll, roll_ability_score, STANDARD_ARRAY, validate_point_buy
from ..services.rules_engine import ability_modifier, calculate_hp, calculate_ac, proficiency_bonus
from ..services.ollama_client import ollama_client, DM_SYSTEM_PROMPT
from ..socket_manager import sio
from ..config import settings
from ..utils.logger import logger

router = APIRouter()
templates = Jinja2Templates(directory="templates")


# ─── Request / Response schemas ───────────────────────────────────────────────

class JoinRequest(BaseModel):
    player_name: str
    campaign_id: str
    dm_password: Optional[str] = None


class CreateCampaignRequest(BaseModel):
    name: str
    dm_password: str


class DeleteCampaignRequest(BaseModel):
    dm_password: str


class CreateCharacterRequest(BaseModel):
    name: str
    race: str
    class_name: str
    background: str = ""
    abilities: dict  # {strength: 15, dexterity: 14, ...}
    skills: dict = {}
    backstory: str = ""
    actions: List[str] = []
    known_spells: List[str] = []
    inventory: List[dict] = []


class UpdateCharacterRequest(BaseModel):
    name: Optional[str] = None
    race: Optional[str] = None
    class_name: Optional[str] = None
    background: Optional[str] = None
    abilities: Optional[dict] = None
    skills: Optional[dict] = None
    backstory: Optional[str] = None
    current_hp: Optional[int] = None
    temp_hp: Optional[int] = None
    conditions: Optional[List[str]] = None
    inventory: Optional[list] = None
    actions: Optional[List[str]] = None
    known_spells: Optional[List[str]] = None


class RollRequest(BaseModel):
    notation: str = "d20"


class NarrateRequest(BaseModel):
    campaign_id: str
    player_action: str
    player_id: Optional[str] = None


class CombatStartRequest(BaseModel):
    campaign_id: str
    participants: List[dict]


class DMCharacterUpdateRequest(BaseModel):
    current_hp: Optional[int] = None
    temp_hp: Optional[int] = None
    conditions: Optional[List[str]] = None
    xp: Optional[int] = None


# ─── Page routes ──────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    campaigns = await state_manager.list_campaigns()
    return templates.TemplateResponse("index.html", {"request": request, "campaigns": campaigns})


@router.get("/character/new", response_class=HTMLResponse)
async def character_new(request: Request):
    return templates.TemplateResponse(
        "character_builder.html",
        {
            "request": request,
            "character": None,
            "races": RACES,
            "classes": CLASSES,
            "backgrounds": BACKGROUNDS,
        },
    )


@router.get("/character/{character_id}/edit", response_class=HTMLResponse)
async def character_edit(request: Request, character_id: str):
    character = await state_manager.get_character(character_id)
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")
    return templates.TemplateResponse(
        "character_builder.html",
        {
            "request": request,
            "character": character.model_dump(),
            "races": RACES,
            "classes": CLASSES,
            "backgrounds": BACKGROUNDS,
        },
    )


@router.get("/game/{campaign_id}", response_class=HTMLResponse)
async def game_page(request: Request, campaign_id: str):
    campaign = await state_manager.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return templates.TemplateResponse(
        "game.html",
        {"request": request, "campaign": campaign.model_dump(), "campaign_id": campaign_id},
    )


# ─── Auth endpoints ───────────────────────────────────────────────────────────

@router.post("/api/auth/join")
async def join_campaign(req: JoinRequest, request: Request):
    campaign = await state_manager.get_campaign(req.campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    is_dm = False
    if req.dm_password:
        if req.dm_password == settings.DM_PASSWORD:
            is_dm = True
        else:
            raise HTTPException(status_code=403, detail="Invalid DM password")

    client_ip = request.client.host if request.client else ""
    player = await state_manager.create_player(req.player_name, req.campaign_id, is_dm)
    token = session_manager.create_session(
        player_id=player["id"],
        player_name=req.player_name,
        campaign_id=req.campaign_id,
        is_dm=is_dm,
        client_ip=client_ip,
    )
    await state_manager.update_player_token(player["id"], token)

    return {
        "token": token,
        "player_id": player["id"],
        "player_name": req.player_name,
        "campaign_id": req.campaign_id,
        "is_dm": is_dm,
    }


@router.post("/api/auth/leave")
async def leave_campaign(session: PlayerSession = Depends(get_current_session)):
    # Save state before leaving
    campaign = await state_manager.get_campaign(session.campaign_id)
    if campaign:
        await state_manager.save_campaign_state(campaign)
    session_manager.remove_session(session.token)
    return {"message": "Left campaign successfully"}


# ─── Session / Campaign endpoints ─────────────────────────────────────────────

@router.get("/api/sessions")
async def list_sessions():
    return await state_manager.list_campaigns()


@router.get("/api/sessions/{campaign_id}")
async def get_session(campaign_id: str):
    campaign = await state_manager.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    players = await state_manager.get_campaign_players(campaign_id)
    active = session_manager.get_campaign_sessions(campaign_id)
    return {
        "campaign": campaign.model_dump(),
        "players": players,
        "active_sessions": len(active),
    }


@router.post("/api/sessions")
async def create_session_endpoint(req: CreateCampaignRequest, request: Request):
    if req.dm_password != settings.DM_PASSWORD:
        raise HTTPException(status_code=403, detail="Invalid DM password")

    # Create campaign
    campaign = await state_manager.create_campaign(req.name, dm_id="dm")
    client_ip = request.client.host if request.client else ""

    # Auto-create DM player
    player = await state_manager.create_player("DM", campaign.id, is_dm=True)
    token = session_manager.create_session(
        player_id=player["id"],
        player_name="DM",
        campaign_id=campaign.id,
        is_dm=True,
        client_ip=client_ip,
    )
    await state_manager.update_player_token(player["id"], token)

    return {
        "campaign": campaign.model_dump(),
        "token": token,
        "player_id": player["id"],
    }


@router.delete("/api/sessions/{campaign_id}")
async def delete_campaign_endpoint(campaign_id: str, req: DeleteCampaignRequest):
    if req.dm_password != settings.DM_PASSWORD:
        raise HTTPException(status_code=403, detail="Invalid DM password")
    campaign = await state_manager.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    await state_manager.delete_campaign(campaign_id)
    return {"message": "Campaign deleted"}


# ─── Character endpoints ───────────────────────────────────────────────────────

async def _sync_character_to_campaign(campaign_id: str, character: Character):
    """Add or update a character in the campaign's player_characters list and broadcast."""
    campaign = await state_manager.get_campaign(campaign_id)
    if not campaign:
        return
    # Replace existing entry for this player or append
    campaign.player_characters = [
        c for c in campaign.player_characters if c.id != character.id
    ]
    campaign.player_characters.append(character)
    await state_manager.save_campaign_state(campaign)
    # Broadcast to all connected clients in this campaign
    await sio.emit(
        "character_update",
        {"player_id": character.player_id, "character": character.model_dump(mode="json")},
        room=f"campaign_{campaign_id}",
    )


@router.get("/api/characters")
async def list_characters(session: PlayerSession = Depends(get_current_session)):
    chars = await state_manager.get_player_characters(session.player_id)
    return [c.model_dump() for c in chars]


@router.post("/api/characters")
async def create_character(
    req: CreateCharacterRequest,
    session: PlayerSession = Depends(get_current_session),
):
    abilities = AbilityScores(**req.abilities)
    con_mod = ability_modifier(abilities.constitution)
    dex_mod = ability_modifier(abilities.dexterity)
    prof = proficiency_bonus(1)

    max_hp = calculate_hp(req.class_name, 1, con_mod)
    ac = calculate_ac(dex_mod)

    character = Character(
        player_id=session.player_id,
        player_name=session.player_name,
        name=req.name,
        race=req.race,
        class_name=req.class_name,
        background=req.background,
        abilities=abilities,
        max_hp=max_hp,
        current_hp=max_hp,
        armor_class=ac,
        proficiency_bonus=prof,
        skills=req.skills,
        backstory=req.backstory,
        actions=req.actions,
        known_spells=req.known_spells,
        inventory=[Item(**i) for i in req.inventory],
    )
    saved = await state_manager.create_character(character)
    session_manager.update_session_character(session.token, saved.id)
    await _sync_character_to_campaign(session.campaign_id, saved)
    return saved.model_dump()


@router.get("/api/characters/{character_id}")
async def get_character(
    character_id: str,
    session: PlayerSession = Depends(get_current_session),
):
    character = await state_manager.get_character(character_id)
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")
    if character.player_id != session.player_id and not session.is_dm:
        raise HTTPException(status_code=403, detail="Not your character")
    return character.model_dump()


@router.put("/api/characters/{character_id}")
async def update_character(
    character_id: str,
    req: UpdateCharacterRequest,
    session: PlayerSession = Depends(get_current_session),
):
    character = await state_manager.get_character(character_id)
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")
    if character.player_id != session.player_id and not session.is_dm:
        raise HTTPException(status_code=403, detail="Not your character")

    update_data = req.model_dump(exclude_none=True)
    if "abilities" in update_data:
        update_data["abilities"] = AbilityScores(**update_data["abilities"])
    for key, value in update_data.items():
        setattr(character, key, value)

    await state_manager.update_character(character)
    await _sync_character_to_campaign(session.campaign_id, character)
    return character.model_dump()


@router.delete("/api/characters/{character_id}")
async def delete_character(
    character_id: str,
    session: PlayerSession = Depends(get_current_session),
):
    character = await state_manager.get_character(character_id)
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")
    if character.player_id != session.player_id and not session.is_dm:
        raise HTTPException(status_code=403, detail="Not your character")
    await state_manager.delete_character(character_id)
    return {"message": "Character deleted"}


@router.post("/api/characters/{character_id}/roll")
async def roll_for_character(
    character_id: str,
    req: RollRequest,
    session: PlayerSession = Depends(get_current_session),
):
    result = roll(req.notation)
    return {
        "notation": result.notation,
        "rolls": result.rolls,
        "modifier": result.modifier,
        "total": result.total,
        "description": result.description,
    }


@router.post("/api/dice/roll")
async def dice_roll(req: RollRequest):
    """Public dice roll endpoint (no auth required)."""
    result = roll(req.notation)
    return {
        "notation": result.notation,
        "rolls": result.rolls,
        "modifier": result.modifier,
        "total": result.total,
        "description": result.description,
    }


@router.post("/api/dice/ability")
async def roll_ability():
    """Roll 4d6 drop lowest for ability score generation."""
    result = roll_ability_score()
    return {
        "rolls": result.rolls,
        "total": result.total,
        "description": result.description,
    }


@router.get("/api/dice/standard-array")
async def standard_array():
    return {"scores": STANDARD_ARRAY}


# ─── Game state endpoints ──────────────────────────────────────────────────────

@router.get("/api/game/state")
async def game_state(session: PlayerSession = Depends(get_current_session)):
    campaign = await state_manager.get_campaign(session.campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    combat = cm.get_combat_manager(session.campaign_id).to_dict()
    messages = await state_manager.get_messages(session.campaign_id, limit=50)
    return {
        "campaign": campaign.model_dump(),
        "combat": combat,
        "messages": messages,
    }


@router.post("/api/game/start")
async def start_game(session: PlayerSession = Depends(get_current_dm)):
    campaign = await state_manager.get_campaign(session.campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    await state_manager.save_message(
        campaign_id=session.campaign_id,
        sender_id=session.player_id,
        sender_type="system",
        content="The adventure begins!",
    )
    return {"message": "Game started"}


@router.post("/api/game/save")
async def save_game(session: PlayerSession = Depends(get_current_dm)):
    campaign = await state_manager.get_campaign(session.campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    await state_manager.save_campaign_state(campaign)
    return {"message": "Game saved"}


@router.post("/api/game/pause")
async def pause_game(session: PlayerSession = Depends(get_current_dm)):
    campaign = await state_manager.get_campaign(session.campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    campaign.is_paused = True
    await state_manager.save_campaign_state(campaign)
    msg = "⏸ The DM has paused the session. See you next time!"
    await state_manager.save_message(
        campaign_id=session.campaign_id,
        sender_id=session.player_id,
        sender_type="system",
        content=msg,
    )
    await sio.emit("game_paused", {}, room=f"campaign_{session.campaign_id}")
    await sio.emit(
        "chat_message",
        {"sender_id": "system", "sender_name": "System", "sender_type": "system", "content": msg},
        room=f"campaign_{session.campaign_id}",
    )
    return {"message": "Game paused"}


@router.post("/api/game/resume")
async def resume_game(session: PlayerSession = Depends(get_current_dm)):
    campaign = await state_manager.get_campaign(session.campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    campaign.is_paused = False
    await state_manager.save_campaign_state(campaign)
    msg = "▶ The session has resumed. Welcome back!"
    await state_manager.save_message(
        campaign_id=session.campaign_id,
        sender_id=session.player_id,
        sender_type="system",
        content=msg,
    )
    await sio.emit("game_resumed", {}, room=f"campaign_{session.campaign_id}")
    await sio.emit(
        "chat_message",
        {"sender_id": "system", "sender_name": "System", "sender_type": "system", "content": msg},
        room=f"campaign_{session.campaign_id}",
    )
    return {"message": "Game resumed"}


@router.get("/api/game/history")
async def game_history(
    limit: int = 50,
    session: PlayerSession = Depends(get_current_session),
):
    messages = await state_manager.get_messages(session.campaign_id, limit=limit)
    return messages


# ─── DM action endpoints ───────────────────────────────────────────────────────

@router.post("/api/dm/narrate")
async def dm_narrate(req: NarrateRequest, session: PlayerSession = Depends(get_current_dm)):
    campaign = await state_manager.get_campaign(req.campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    # Build context from campaign state
    context = f"""Campaign: {campaign.name}
Location: {campaign.current_location.name} — {campaign.current_location.description}
Session: {campaign.session_number}
Active quests: {', '.join(q.title for q in campaign.quests if not q.is_completed) or 'None'}
Players: {', '.join(c.name for c in campaign.player_characters) or 'None yet'}
"""
    # Fetch recent history
    history_msgs = await state_manager.get_messages(req.campaign_id, limit=10)
    history = [
        {"role": "assistant" if m["sender_type"] == "dm" else "user", "content": m["content"]}
        for m in history_msgs
    ]

    prompt = f"{context}\n\nPlayer action: {req.player_action}"
    system = DM_SYSTEM_PROMPT

    try:
        response = await ollama_client.generate(prompt, system_prompt=system, history=history)
    except Exception as e:
        logger.error(f"Ollama narration error: {e}")
        raise HTTPException(status_code=503, detail=f"AI narration unavailable: {e}")

    # Save the exchange
    if req.player_id:
        await state_manager.save_message(
            campaign_id=req.campaign_id,
            sender_id=req.player_id,
            sender_type="player",
            content=req.player_action,
        )
    await state_manager.save_message(
        campaign_id=req.campaign_id,
        sender_id=session.player_id,
        sender_type="dm",
        content=response,
    )

    return {"narration": response}


@router.post("/api/dm/combat/start")
async def start_combat(req: CombatStartRequest, session: PlayerSession = Depends(get_current_dm)):
    combat = cm.get_combat_manager(req.campaign_id)
    order = combat.start_combat(req.participants)

    # Update campaign state
    campaign = await state_manager.get_campaign(req.campaign_id)
    if campaign:
        campaign.is_combat_active = True
        campaign.initiative_order = [c.name for c in order]
        await state_manager.save_campaign_state(campaign)

    return {"combat": combat.to_dict()}


@router.post("/api/dm/combat/next")
async def next_combat_turn(session: PlayerSession = Depends(get_current_dm)):
    combat = cm.get_combat_manager(session.campaign_id)
    if not combat.is_active:
        raise HTTPException(status_code=400, detail="No active combat")
    combatant, new_round = combat.next_turn()
    return {
        "current": combatant.name,
        "new_round": new_round,
        "round_number": combat.round_number,
        "combat": combat.to_dict(),
    }


@router.post("/api/dm/combat/end")
async def end_combat(session: PlayerSession = Depends(get_current_dm)):
    combat = cm.get_combat_manager(session.campaign_id)
    combat.end_combat()
    campaign = await state_manager.get_campaign(session.campaign_id)
    if campaign:
        campaign.is_combat_active = False
        campaign.initiative_order = []
        await state_manager.save_campaign_state(campaign)
    return {"message": "Combat ended"}


@router.post("/api/dm/roll")
async def dm_roll(req: RollRequest, session: PlayerSession = Depends(get_current_dm)):
    result = roll(req.notation)
    await state_manager.save_message(
        campaign_id=session.campaign_id,
        sender_id=session.player_id,
        sender_type="system",
        content=f"DM rolls {req.notation}: {result.description}",
        metadata={"rolls": result.rolls, "total": result.total, "notation": result.notation},
    )
    return {
        "notation": result.notation,
        "rolls": result.rolls,
        "modifier": result.modifier,
        "total": result.total,
        "description": result.description,
    }


@router.put("/api/dm/character/{character_id}")
async def dm_update_character(
    character_id: str,
    req: DMCharacterUpdateRequest,
    session: PlayerSession = Depends(get_current_dm),
):
    character = await state_manager.get_character(character_id)
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")

    update_data = req.model_dump(exclude_none=True)
    for key, value in update_data.items():
        setattr(character, key, value)

    await state_manager.update_character(character)
    await _sync_character_to_campaign(session.campaign_id, character)
    return character.model_dump()


# ─── Health check ──────────────────────────────────────────────────────────────

@router.get("/api/health")
async def health():
    ollama_ok = await ollama_client.test_connection()
    return {
        "status": "ok",
        "ollama": "connected" if ollama_ok else "unreachable",
        "ollama_host": settings.OLLAMA_HOST,
        "model": settings.OLLAMA_MODEL,
    }
