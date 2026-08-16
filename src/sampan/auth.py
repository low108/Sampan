"""Shared-secret request auth.

Deliberately not Cloud Run IAM: the elder's device and the family web app both
call this service from outside Google Cloud, and a header is one line on the
client instead of a token exchange.
"""

from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from sampan.config import Settings, get_settings

API_KEY_HEADER = "X-Sampan-Key"


def require_api_key(
    settings: Annotated[Settings, Depends(get_settings)],
    x_sampan_key: Annotated[str | None, Header(alias=API_KEY_HEADER)] = None,
) -> None:
    """Reject the request unless it carries the shared secret.

    Refuses to run at all when no key is configured, so a misconfigured deploy
    fails closed rather than serving an open endpoint.
    """
    if not settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service is missing SAMPAN_API_KEY; refusing to serve.",
        )
    if x_sampan_key is None or not secrets.compare_digest(
        x_sampan_key, settings.api_key
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid API key.",
        )
