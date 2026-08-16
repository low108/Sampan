"""The Sampan service.

Ticket 1 scope: a deployable service that proves the round trip to Firestore
and refuses unauthenticated traffic. The Companion WebSocket and the Archivist
job land on top of this skeleton.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import Depends, FastAPI
from pydantic import BaseModel, Field

from sampan.auth import require_api_key
from sampan.config import Settings, get_settings
from sampan.store import DocumentStore, build_store

SMOKE_COLLECTION = "_smoke"


class Health(BaseModel):
    status: str
    configured: bool
    location: str


class SmokeRequest(BaseModel):
    note: str = Field(default="hello from sampan", max_length=500)


class SmokeResult(BaseModel):
    doc_id: str
    written: dict[str, Any]
    read_back: dict[str, Any] | None
    round_trip_ok: bool


def get_store(
    settings: Annotated[Settings, Depends(get_settings)],
) -> DocumentStore:
    return build_store(settings)


def create_app() -> FastAPI:
    app = FastAPI(title="Sampan", version="0.1.0")

    @app.get("/healthz", response_model=Health)
    def healthz(settings: Annotated[Settings, Depends(get_settings)]) -> Health:
        """Unauthenticated liveness probe for Cloud Run."""
        return Health(
            status="ok", configured=settings.configured, location=settings.location
        )

    @app.post(
        "/debug/smoke",
        response_model=SmokeResult,
        dependencies=[Depends(require_api_key)],
    )
    def smoke(
        body: SmokeRequest,
        store: Annotated[DocumentStore, Depends(get_store)],
    ) -> SmokeResult:
        """Write a document and read it back.

        This is the ticket 1 acceptance test, runnable against the deployed
        service with curl.
        """
        doc_id = uuid.uuid4().hex
        payload = {
            "note": body.note,
            "written_at": datetime.now(UTC).isoformat(),
        }
        store.put(SMOKE_COLLECTION, doc_id, payload)
        read_back = store.get(SMOKE_COLLECTION, doc_id)
        return SmokeResult(
            doc_id=doc_id,
            written=payload,
            read_back=read_back,
            round_trip_ok=read_back is not None and read_back.get("note") == body.note,
        )

    return app


app = create_app()
