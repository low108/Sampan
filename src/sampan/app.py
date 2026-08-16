"""The Sampan service.

Ticket 1 scope: a deployable service that proves the round trip to Firestore
and refuses unauthenticated traffic. The Companion WebSocket and the Archivist
job land on top of this skeleton.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from sampan.auth import require_api_key
from sampan.companion import build_agent
from sampan.config import Settings, apply_genai_env, get_settings
from sampan.live import open_session, pump
from sampan.store import DocumentStore, get_document_store

SMOKE_COLLECTION = "_smoke"


class Health(BaseModel):
    status: str
    configured: bool
    location: str
    backend: str


class SmokeRequest(BaseModel):
    note: str = Field(default="hello from sampan", max_length=500)


class SmokeResult(BaseModel):
    doc_id: str
    backend: str
    written: dict[str, Any]
    read_back: dict[str, Any] | None
    round_trip_ok: bool


def get_store() -> DocumentStore:
    return get_document_store()


def create_app() -> FastAPI:
    apply_genai_env()
    app = FastAPI(title="Sampan", version="0.1.0")

    # Not /healthz: Cloud Run's front end intercepts that path and answers with
    # its own 404 before the request reaches the container.
    @app.get("/health", response_model=Health)
    def health(
        settings: Annotated[Settings, Depends(get_settings)],
        store: Annotated[DocumentStore, Depends(get_store)],
    ) -> Health:
        """Unauthenticated liveness probe for Cloud Run."""
        return Health(
            status="ok",
            configured=settings.configured,
            location=settings.location,
            backend=store.backend,
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
            backend=store.backend,
            written=payload,
            read_back=read_back,
            round_trip_ok=read_back is not None and read_back.get("note") == body.note,
        )

    @app.websocket("/ws/talk")
    async def talk(websocket: WebSocket) -> None:
        """One call.

        The browser sends binary PCM frames and receives JSON. Auth rides on a
        query parameter because browsers cannot set headers on a WebSocket
        handshake.
        """
        settings = get_settings()
        if (
            not settings.api_key
            or websocket.query_params.get("key") != settings.api_key
        ):
            await websocket.close(code=4401, reason="Unauthorized")
            return

        await websocket.accept()
        user_id = websocket.query_params.get("user", "ah_khim")

        session = await open_session(build_agent(settings), settings, user_id=user_id)
        pump_task = asyncio.create_task(pump(session, websocket.send_json))

        try:
            while True:
                message = await websocket.receive()
                if message.get("type") == "websocket.disconnect":
                    break
                if (chunk := message.get("bytes")) is not None:
                    session.feed_audio(chunk)
                elif (text := message.get("text")) is not None:
                    session.feed_text(text)
        except WebSocketDisconnect:
            pass
        finally:
            session.close()
            pump_task.cancel()

    static_dir = Path(__file__).resolve().parents[2] / "static"
    if static_dir.is_dir():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

    return app


app = create_app()
