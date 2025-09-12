from fastapi import Header, HTTPException, status
import os
from typing import Optional

def _get_expected_key() -> Optional[str]:
    return os.environ.get("SNAPSHOT_API_KEY")

def require_api_key(x_api_key: Optional[str] = Header(None)):
    """
    Simple API key check. If SNAPSHOT_API_KEY is not set the API is left open.
    Caller should include: _key: str | None = Depends(require_api_key)
    """
    expected = _get_expected_key()
    if not expected:
        # No API key configured: allow open access (make explicit in docs / env)
        return None
    if not x_api_key or x_api_key != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API key")
    return x_api_key
