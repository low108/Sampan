"""The Sampan service.

Ticket 1 scope: a deployable service that proves the round trip to Firestore
and refuses unauthenticated traffic. The Companion WebSocket and the Archivist
job land on top of this skeleton.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from sampan.affect import GeminiAffectMonitor, policy, watch
from sampan.archivist import GeminiStoryExtractor
from sampan.auth import require_api_key
from sampan.callflow import Transcript, finish_call, prepare_call
from sampan.config import Settings, apply_genai_env, get_settings
from sampan.corrections import (
    Correction,
    apply_correction,
    duplicate_candidates,
    needs_confirmation,
)
from sampan.family import build_cards, build_map, feed, stats, timeline
from sampan.live import open_session, pump
from sampan.models import AffectState, Ask
from sampan.places import GeminiPlaceResolver
from sampan.quiet import is_quiet
from sampan.repository import Repository
from sampan.store import DocumentStore, get_document_store
from sampan.tools import CallMemory

SMOKE_COLLECTION = "_smoke"


class Health(BaseModel):
    status: str
    configured: bool
    location: str
    backend: str


# A ten-second Opus clip is tens of kilobytes; base64 in Firestore keeps the
# demo to one storage service. Cloud Storage is the right answer for anything
# longer, and the cap is here so nobody discovers the 1MB document limit in
# production.
MAX_VOICE_NOTE_CHARS = 700_000


class AskRequest(BaseModel):
    from_name: str = Field(min_length=1, max_length=40)
    relation: str = Field(default="", max_length=20)
    question: str = Field(min_length=1, max_length=500)
    voice_note: str | None = Field(
        default=None, description="base64 data URL of a short recording"
    )


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


def find_static_dir() -> Path | None:
    """Locate the web pages, in the image and in a checkout.

    Once installed, `sampan` lives under site-packages, so resolving relative
    to __file__ walks into the virtualenv rather than the repo. That worked
    locally by accident and 404'd every page on Cloud Run while the API kept
    answering perfectly.
    """
    candidates = [
        Path(os.environ["SAMPAN_STATIC_DIR"])
        if os.environ.get("SAMPAN_STATIC_DIR")
        else None,
        Path.cwd() / "static",
        Path(__file__).resolve().parents[2] / "static",
    ]
    for candidate in candidates:
        if candidate is not None and (candidate / "index.html").is_file():
            return candidate
    return None


_PLACE_CACHE = "_places"
_LETTER_CACHE = "_letters"


def _letters_for(
    settings: Settings, store: DocumentStore, cards: list[Any]
) -> dict[str, dict[str, str]]:
    """Letters for pinned stories, written once and kept.

    Generated lazily rather than at extraction time so a call never waits on
    them, and cached because a letter about 1958 will not change.
    """
    from sampan.letters import GeminiLetterWriter, Letter, worth_writing

    out: dict[str, dict[str, str]] = {}
    pending = []
    for card in cards:
        if not worth_writing(card):
            continue
        raw = store.get(_LETTER_CACHE, card.story_id)
        if raw is None:
            pending.append(card)
        else:
            out[card.story_id] = Letter.model_validate(raw).model_dump(mode="json")

    if pending and settings.configured:
        writer = GeminiLetterWriter(settings)
        for card in pending:
            with contextlib.suppress(Exception):
                letter = writer.write(card)
                store.put(_LETTER_CACHE, card.story_id, letter.model_dump(mode="json"))
                out[card.story_id] = letter.model_dump(mode="json")
    return out


def _resolve_places(
    settings: Settings, store: DocumentStore, cards: list[Any]
) -> list[Any]:
    """Resolve place names, caching results.

    Cached because a place does not move, and because the map is the view a
    family opens most often — re-resolving on every load would be the single
    largest avoidable cost in the product.
    """
    from sampan.places import Place

    names = sorted({c.where_said for c in cards if c.where_said})
    cached: list[Place] = []
    missing: list[str] = []
    for name in names:
        raw = store.get(_PLACE_CACHE, name)
        if raw is None:
            missing.append(name)
        else:
            cached.append(Place.model_validate(raw))

    if missing and settings.configured:
        with contextlib.suppress(Exception):
            for place in GeminiPlaceResolver(settings).resolve(missing):
                store.put(_PLACE_CACHE, place.raw_name, place.model_dump(mode="json"))
                cached.append(place)

    resolved = {p.raw_name for p in cached}
    cached.extend(Place(raw_name=name) for name in names if name not in resolved)
    return cached


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

    @app.get("/api/family/{narrator_id}", dependencies=[Depends(require_api_key)])
    def family_view(
        narrator_id: str,
        settings: Annotated[Settings, Depends(get_settings)],
        store: Annotated[DocumentStore, Depends(get_store)],
        view: str = "feed",
    ) -> dict[str, Any]:
        """Her archive, in whichever projection was asked for.

        Feed, timeline and map are three orderings of the same stories, so they
        share one endpoint rather than three that could drift apart.
        """
        repository = Repository(store)
        memory = repository.load_memory(narrator_id)
        cards = build_cards(repository.load_stories(narrator_id))
        entities = repository.load_entities(narrator_id)

        payload: dict[str, Any] = {
            "narrator_id": narrator_id,
            "session_count": memory.session_count,
            "stats": stats(cards, len(entities), memory.session_count).model_dump(),
            # Surfaced on every view, not tucked into a tab. The agent has
            # already told her it was passing this on.
            "concerns": repository.open_concerns(narrator_id),
        }

        if view == "map":
            places = _resolve_places(settings, store, cards)
            payload["map"] = build_map(cards, places).model_dump(mode="json")
            # The journey view needs every story's year to order the stops,
            # not just the ones grouped under a pin.
            payload["allStories"] = [c.model_dump() for c in timeline(cards)]
        elif view == "timeline":
            payload["stories"] = [c.model_dump() for c in timeline(cards)]
        else:
            ordered = feed(cards)
            payload["stories"] = [c.model_dump() for c in ordered]
            payload["letters"] = _letters_for(settings, store, ordered)
        return payload

    @app.post("/api/family/{narrator_id}/ask", dependencies=[Depends(require_api_key)])
    def leave_ask(
        narrator_id: str,
        body: AskRequest,
        store: Annotated[DocumentStore, Depends(get_store)],
    ) -> dict[str, Any]:
        """Leave a question, and optionally ten seconds of your own voice.

        The voice note is the point. A text question arrives in the agent's
        voice; a recording arrives in her son's, and that is the difference
        between being told he was thinking of her and hearing it.
        """
        if body.voice_note and len(body.voice_note) > MAX_VOICE_NOTE_CHARS:
            raise HTTPException(
                status_code=413,
                detail="Voice note too long; ten seconds is the intended length.",
            )

        ask = Ask(
            ask_id=f"ask_{uuid.uuid4().hex[:10]}",
            from_name=body.from_name,
            relation=body.relation,
            question=body.question,
            voice_note_url=body.voice_note,
            created_at=datetime.now(UTC).isoformat(),
        )
        Repository(store).queue_ask(narrator_id, ask)
        return {
            "ask_id": ask.ask_id,
            "queued": True,
            "has_voice": bool(body.voice_note),
        }

    @app.get(
        "/api/family/{narrator_id}/corrections",
        dependencies=[Depends(require_api_key)],
    )
    def pending_corrections(
        narrator_id: str, store: Annotated[DocumentStore, Depends(get_store)]
    ) -> dict[str, Any]:
        """What the archive is unsure about, for the family to settle.

        Places are listed with the key stored against them rather than a
        prettified name, because a correction has to target the key the map
        actually uses — 双溪镇树胶园, not 双溪镇.
        """
        from sampan.places import Place

        repository = Repository(store)
        entities = repository.load_entities(narrator_id)
        cards = build_cards(repository.load_stories(narrator_id))

        places: list[dict[str, Any]] = []
        for name in sorted({c.where_said for c in cards if c.where_said}):
            raw = store.get(_PLACE_CACHE, name)
            place = Place.model_validate(raw) if raw else Place(raw_name=name)
            if place.needs_confirmation or not place.locatable:
                payload = place.model_dump(mode="json")
                payload["stories"] = sum(1 for c in cards if c.where_said == name)
                places.append(payload)

        return {
            "unconfirmed": [
                e.model_dump(mode="json") for e in needs_confirmation(entities)
            ],
            "possible_duplicates": [
                {"a": a.model_dump(mode="json"), "b": b.model_dump(mode="json")}
                for a, b in duplicate_candidates(entities)
            ],
            "places": places,
        }

    @app.post(
        "/api/family/{narrator_id}/corrections",
        dependencies=[Depends(require_api_key)],
    )
    def correct(
        narrator_id: str,
        correction: Correction,
        store: Annotated[DocumentStore, Depends(get_store)],
    ) -> dict[str, Any]:
        """Fix a name, a detail, or a place — or merge two people into one."""
        result = apply_correction(Repository(store), narrator_id, correction)
        if not result.applied:
            raise HTTPException(status_code=400, detail=result.reason)
        return result.model_dump()

    @app.get("/api/talk/{narrator_id}/pending", dependencies=[Depends(require_api_key)])
    def pending_for_her(
        narrator_id: str,
        settings: Annotated[Settings, Depends(get_settings)],
        store: Annotated[DocumentStore, Depends(get_store)],
    ) -> dict[str, Any]:
        """Whether someone has left her something.

        Her phone cannot truly ring — a PWA has no access to a full-screen
        incoming call (PRD 9.4). So the app asks, and if her son has left a
        question it shows his name and plays his voice.
        """
        # Queued instantly, shown when she is awake.
        if is_quiet(settings):
            return {"waiting": False, "quiet_hours": True}

        ask = Repository(store).pending_ask(narrator_id)
        if ask is None:
            return {"waiting": False}
        return {
            "waiting": True,
            "from_name": ask.from_name,
            "relation": ask.relation,
            "voice_note": ask.voice_note_url,
        }

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

        repository = Repository(get_document_store())
        prepared = await asyncio.to_thread(
            prepare_call, repository, settings, narrator_id=user_id
        )
        memory = prepared.memory
        transcript = Transcript()

        async def relay(message: dict[str, Any]) -> None:
            if (text := message.get("user_transcript")) is not None:
                transcript.add("user", text)
            if (text := message.get("agent_transcript")) is not None:
                transcript.add("agent", text)
            await websocket.send_json(message)

        session = await open_session(prepared.agent, settings, user_id=user_id)
        pump_task = asyncio.create_task(pump(session, relay))
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
            # The call is over for her the moment she hangs up; extraction
            # happens afterwards and must never hold the socket open.
            with contextlib.suppress(Exception):
                await asyncio.to_thread(
                    finish_call,
                    repository,
                    GeminiStoryExtractor(settings),
                    prepared,
                    transcript,
                    narrator_id=user_id,
                )

    static_dir = find_static_dir()
    if static_dir is not None:
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

    return app


app = create_app()
