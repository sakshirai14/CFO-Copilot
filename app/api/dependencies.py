"""app/api/dependencies.py

FastAPI Request Dependencies for CFO Copilot API.
Enforces:
- Foundation Lock Partition (Isolation): Server-side API key to tenant mapping.
- Foundation Lock Door (API): Consistent correlation ID extraction.
"""

import re
import uuid
from typing import Optional
from fastapi import Header, HTTPException, status
from app.core.config import get_settings


def get_request_id(x_request_id: Optional[str] = Header(None)) -> str:
    """Extracts or generates a sanitized client correlation tracking ID."""
    if x_request_id:
        clean = re.sub(r"[^a-zA-Z0-9_\-]", "", x_request_id)[:64]
        if clean:
            return clean
    return f"req_{uuid.uuid4().hex[:12]}"


def get_authenticated_tenant(x_api_key: Optional[str] = Header(None)) -> str:
    """Validates X-API-Key header against server-side tenant key mappings.
    The tenant is NEVER supplied in request body (Foundation Lock 6).
    """
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing required authentication header 'X-API-Key'."
        )

    settings = get_settings()
    tenant = settings.get_tenant_for_api_key(x_api_key)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid 'X-API-Key'. Access to tenant data is denied."
        )

    return tenant

