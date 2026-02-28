from datetime import datetime, timezone, timedelta
from typing import Dict, Optional
from jose import JWTError, jwt
from fastapi import HTTPException, status

from ..config import settings
from ..models.session import PlayerSession
from ..utils.logger import logger

ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 24

# In-memory store of active sessions: token -> PlayerSession
_active_sessions: Dict[str, PlayerSession] = {}


def create_session(
    player_id: str,
    player_name: str,
    campaign_id: str,
    is_dm: bool = False,
    client_ip: str = "",
) -> str:
    session = PlayerSession(
        player_id=player_id,
        player_name=player_name,
        campaign_id=campaign_id,
        is_dm=is_dm,
        client_ip=client_ip,
    )

    expire = datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRE_HOURS)
    payload = {
        "sub": player_id,
        "name": player_name,
        "campaign_id": campaign_id,
        "is_dm": is_dm,
        "session_id": session.session_id,
        "exp": expire,
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)
    _active_sessions[token] = session
    logger.info(f"Session created for {player_name} (DM={is_dm}) in campaign {campaign_id}")
    return token


def validate_token(token: str) -> PlayerSession:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {e}",
        )

    if token in _active_sessions:
        session = _active_sessions[token]
        session.last_seen = datetime.now(timezone.utc)
        session.token = token
        return session

    # Reconstruct session from token if not in memory (e.g. after restart)
    session = PlayerSession(
        session_id=payload.get("session_id", ""),
        player_id=payload["sub"],
        player_name=payload["name"],
        campaign_id=payload["campaign_id"],
        is_dm=payload.get("is_dm", False),
        token=token,
    )
    _active_sessions[token] = session
    return session


def require_dm(token: str) -> PlayerSession:
    session = validate_token(token)
    if not session.is_dm:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="DM privileges required",
        )
    return session


def get_campaign_sessions(campaign_id: str) -> list[PlayerSession]:
    return [s for s in _active_sessions.values() if s.campaign_id == campaign_id]


def remove_session(token: str):
    _active_sessions.pop(token, None)


def update_session_character(token: str, character_id: str):
    if token in _active_sessions:
        _active_sessions[token].character_id = character_id


def update_session_ready(token: str, is_ready: bool):
    if token in _active_sessions:
        _active_sessions[token].is_ready = is_ready
