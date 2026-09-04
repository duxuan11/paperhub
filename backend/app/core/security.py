"""API Key 鉴权。"""

import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings

_bearer = HTTPBearer(auto_error=False)


def _safe_equal(a: str, b: str) -> bool:
    return secrets.compare_digest(a, b)


async def require_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> None:
    if not settings.auth_enabled:
        return
    if credentials is None or not _safe_equal(
        credentials.credentials, settings.paperhub_api_key
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
