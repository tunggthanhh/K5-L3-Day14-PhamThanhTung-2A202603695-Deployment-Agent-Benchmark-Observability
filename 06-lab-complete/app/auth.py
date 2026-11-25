"""API-key authentication dependency."""
from secrets import compare_digest

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from app.config import settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(api_key: str | None = Security(api_key_header)) -> str:
    """Return a verified key or consistently reject the request with HTTP 401."""
    if not api_key or not compare_digest(api_key, settings.agent_api_key):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return api_key
