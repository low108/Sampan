"""Shared-secret request auth.

Deliberately not Cloud Run IAM: the elder's device and the family web app both
call this service from outside Google Cloud, and a header is one line on the
client instead of a token exchange.
"""

from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Query, status

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
    # Compare as bytes: Starlette decodes headers as latin-1, and
    # secrets.compare_digest raises TypeError on non-ASCII str, which would
    # surface as a 500 with a traceback instead of a clean 401.
    if x_sampan_key is None or not secrets.compare_digest(
        x_sampan_key.encode("utf-8"), settings.api_key.encode("utf-8")
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid API key.",
        )


def require_push_key(
    settings: Annotated[Settings, Depends(get_settings)],
    key: Annotated[str | None, Query()] = None,
) -> None:
    """The same secret, read from the query string instead of a header.

    For Pub/Sub push only, and separate from `require_api_key` on purpose. Push
    delivery cannot set a custom header -- a subscription may carry an OIDC
    token or a URL, and nothing else -- so the one endpoint Pub/Sub calls has to
    accept the key some other way. `/internal/memories` already documented this
    as how it worked. It was not: it depended on `require_api_key`, every push
    was answered 401, and because the failures were on Pub/Sub's side rather
    than in a call, nothing surfaced them. Four renders were queued and five
    delivery attempts each were refused before anyone looked.

    Kept to this one route rather than folded into `require_api_key`, because a
    key in a URL is a key in access logs, in referrers and in history. That is
    an acceptable trade for a server-to-server call inside one project and a bad
    one for the endpoints a browser touches, which is why those stay header-only.
    """
    if not settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service is missing SAMPAN_API_KEY; refusing to serve.",
        )
    if key is None or not secrets.compare_digest(
        key.encode("utf-8"), settings.api_key.encode("utf-8")
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid API key.",
        )
