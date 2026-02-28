import os
import socketio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import router
from .managers.state_manager import init_db
from .managers.session_manager import validate_token, get_campaign_sessions
from .managers import state_manager
from .services.ollama_client import ollama_client
from .socket_manager import sio
from .config import settings
from .utils.logger import logger

# Map sid → token for session lookup
_sid_tokens: dict = {}


@sio.event
async def connect(sid, environ, auth):
    token = None
    if auth and isinstance(auth, dict):
        token = auth.get("token")
    if not token:
        # Try query string
        qs = environ.get("QUERY_STRING", "")
        for part in qs.split("&"):
            if part.startswith("token="):
                token = part[6:]
                break

    if not token:
        logger.warning(f"Socket connection rejected — no token (sid={sid})")
        return False

    try:
        session = validate_token(token)
        _sid_tokens[sid] = token
        session.is_connected = True
        await sio.enter_room(sid, f"campaign_{session.campaign_id}")
        logger.info(f"Player {session.player_name} connected (sid={sid})")
        await sio.emit(
            "player_joined",
            {"player_id": session.player_id, "player_name": session.player_name},
            room=f"campaign_{session.campaign_id}",
            skip_sid=sid,
        )
        # Send current game state to the new connection
        campaign = await state_manager.get_campaign(session.campaign_id)
        if campaign:
            await sio.emit(
                "game_state",
                {"campaign": campaign.model_dump(mode="json")},
                to=sid,
            )
    except Exception as e:
        logger.warning(f"Socket auth failed: {e}")
        return False


@sio.event
async def disconnect(sid):
    token = _sid_tokens.pop(sid, None)
    if token:
        try:
            session = validate_token(token)
            session.is_connected = False
            await sio.emit(
                "player_left",
                {"player_id": session.player_id, "player_name": session.player_name},
                room=f"campaign_{session.campaign_id}",
            )
            logger.info(f"Player {session.player_name} disconnected")
        except Exception:
            pass


@sio.event
async def chat_message(sid, data):
    token = _sid_tokens.get(sid)
    if not token:
        return
    try:
        session = validate_token(token)
        content = data.get("content", "").strip()
        if not content:
            return

        await state_manager.save_message(
            campaign_id=session.campaign_id,
            sender_id=session.player_id,
            sender_type="dm" if session.is_dm else "player",
            content=content,
        )
        await sio.emit(
            "chat_message",
            {
                "sender_id": session.player_id,
                "sender_name": session.player_name,
                "sender_type": "dm" if session.is_dm else "player",
                "content": content,
            },
            room=f"campaign_{session.campaign_id}",
        )
    except Exception as e:
        logger.error(f"chat_message error: {e}")


@sio.event
async def action(sid, data):
    """Player submits an action — DM agent processes and broadcasts narration."""
    token = _sid_tokens.get(sid)
    if not token:
        return
    try:
        session = validate_token(token)
        player_action = data.get("content", "").strip()
        if not player_action:
            return

        # Save player message
        await state_manager.save_message(
            campaign_id=session.campaign_id,
            sender_id=session.player_id,
            sender_type="player",
            content=player_action,
        )
        # Broadcast player action to room
        await sio.emit(
            "chat_message",
            {
                "sender_id": session.player_id,
                "sender_name": session.player_name,
                "sender_type": "player",
                "content": player_action,
            },
            room=f"campaign_{session.campaign_id}",
        )

        # Signal to all clients that the DM is composing a response
        await sio.emit("dm_typing", {}, room=f"campaign_{session.campaign_id}")

        # Generate DM narration
        from .services.ollama_client import DM_SYSTEM_PROMPT
        campaign = await state_manager.get_campaign(session.campaign_id)
        context = ""
        # Resolve the acting player's character name (fall back to player name if no character yet)
        character_name = session.player_name
        if campaign:
            char = next((c for c in campaign.player_characters if c.player_id == session.player_id), None)
            if char:
                character_name = char.name
            context = f"Campaign: {campaign.name}\nLocation: {campaign.current_location.name}\nCharacters: {', '.join(c.name for c in campaign.player_characters)}\n"

        history_msgs = await state_manager.get_messages(session.campaign_id, limit=10)
        history = [
            {"role": "assistant" if m["sender_type"] == "dm" else "user", "content": m["content"]}
            for m in history_msgs
        ]

        prompt = f"{context}\n{character_name}: {player_action}"

        # Stream narration via Socket.IO
        narration = await ollama_client.generate(prompt, system_prompt=DM_SYSTEM_PROMPT, history=history)
        await state_manager.save_message(
            campaign_id=session.campaign_id,
            sender_id="dm",
            sender_type="dm",
            content=narration,
        )
        await sio.emit(
            "chat_message",
            {
                "sender_id": "dm",
                "sender_name": "Dungeon Master",
                "sender_type": "dm",
                "content": narration,
            },
            room=f"campaign_{session.campaign_id}",
        )
    except Exception as e:
        logger.error(f"action handler error: {e}")
        await sio.emit("chat_message", {
            "sender_id": "system",
            "sender_name": "System",
            "sender_type": "system",
            "content": f"[Error processing action: {e}]",
        }, to=sid)


@sio.event
async def ready_toggle(sid, data):
    token = _sid_tokens.get(sid)
    if not token:
        return
    try:
        from .managers.session_manager import update_session_ready
        session = validate_token(token)
        is_ready = data.get("is_ready", False)
        update_session_ready(token, is_ready)
        await sio.emit(
            "player_ready",
            {"player_id": session.player_id, "player_name": session.player_name, "is_ready": is_ready},
            room=f"campaign_{session.campaign_id}",
        )
    except Exception as e:
        logger.error(f"ready_toggle error: {e}")


# ─── FastAPI app ───────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    os.makedirs("data", exist_ok=True)
    await init_db()
    await ollama_client.test_connection()
    logger.info("Dungeon Master Claude server started")
    yield
    # Shutdown
    await ollama_client.close()
    logger.info("Server shutting down")


app = FastAPI(
    title="Dungeon Master Claude",
    description="Multiplayer web-based D&D Dungeon Master powered by Ollama",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Wrap with Socket.IO ASGI middleware
# Use `socket_app` as the ASGI entry point:
#   uvicorn src.main:socket_app --host 0.0.0.0 --port 8000 --reload
socket_app = socketio.ASGIApp(sio, other_asgi_app=app)
