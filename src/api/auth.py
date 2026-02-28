from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from ..managers.session_manager import validate_token, require_dm
from ..models.session import PlayerSession

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_session(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> PlayerSession:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return validate_token(credentials.credentials)


def get_current_dm(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> PlayerSession:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return require_dm(credentials.credentials)


def get_optional_session(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> PlayerSession | None:
    if not credentials:
        return None
    try:
        return validate_token(credentials.credentials)
    except HTTPException:
        return None
