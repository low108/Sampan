"""The Sampan service.

Ticket 1 scope: a deployable service that proves the round trip to Firestore
and refuses unauthenticated traffic. The Companion WebSocket and the Archivist
job land on top of this skeleton.
"""

from __future__ import annotations

import asyncio
import contextlib
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from sampan.affect import GeminiAffectMonitor, policy, watch
from sampan.auth import require_api_key
from sampan.companion import build_agent
from sampan.config import Settings, apply_genai_env, get_settings
from sampan.live import open_session, pump
from sampan.models import AffectState
from sampan.opener import build_session_plan, render_plan
from sampan.store import DocumentStore, get_document_store
from sampan.tools import CallMemory, build_tools

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


async def _publish_affect(
    websocket: WebSocket, memory: CallMemory, state: AffectState
) -> None:
    """Update the call's guidance channel and the on-screen overlay.

    The state reaches the agent only via tool responses (a live session cannot
    be steered mid-call), but it reaches the *screen* immediately, which is
    what the demo shows.
    """
    memory.affect = state
    knobs = policy(state)
    with contextlib.suppress(Exception):
        await websocket.send_json(
            {
                "affect": {
                    "energy": state.energy.value,
                    "engagement": state.engagement.value,
                    "affect": state.affect.value,
                    "flags": [f.value for f in state.flags],
                    "topic_action": knobs.topic_action.value,
                    "turn_length": knobs.turn_length,
                    "care_flag": knobs.care_flag,
                }
            }
        )


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

        # TODO(ticket 9): load real memory for this narrator from Firestore.
        # Until then the call runs with an empty graph, which is session-1
        # behaviour rather than a failure.
        memory = CallMemory()
        plan = build_session_plan(
            threads=memory.threads,
            sensitivities=memory.sensitivities,
            ask=memory.ask,
            session_count=0,
        )
        agent = build_agent(
            settings,
            preferences=memory.preferences,
            sensitivities=memory.sensitivities,
            session_plan=render_plan(plan),
            tools=build_tools(memory),
        )

        session = await open_session(agent, settings, user_id=user_id)
        pump_task = asyncio.create_task(pump(session, websocket.send_json))
        watch_task = asyncio.create_task(
            watch(
                session,
                GeminiAffectMonitor(settings),
                on_state=lambda state: _publish_affect(websocket, memory, state),
            )
        )

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
            watch_task.cancel()
            pump_task.cancel()

    static_dir = Path(__file__).resolve().parents[2] / "static"
    if static_dir.is_dir():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

    return app


app = create_app()
