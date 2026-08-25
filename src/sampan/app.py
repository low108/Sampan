"""The Sampan service.

Ticket 1 scope: a deployable service that proves the round trip to Firestore
and refuses unauthenticated traffic. The Companion WebSocket and the Archivist
job land on top of this skeleton.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any, NamedTuple

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
from sampan.armor import build_screen
from sampan.auth import require_api_key
from sampan.callflow import Transcript, finish_call, prepare_call
from sampan.config import Settings, apply_genai_env, get_settings
from sampan.contradiction import (
    Disagreement,
    GeminiContradictionJudge,
    Judgement,
    apply_conflicting_testimony,
    apply_state_change,
)
from sampan.corrections import (
    Correction,
    apply_correction,
    duplicate_candidates,
    needs_confirmation,
)
from sampan.fact_extraction import GeminiFactExtractor
from sampan.facts import Fact, Predicate
from sampan.family import build_cards, build_map, feed, stats, timeline
from sampan.household import (
    cards_for,
    list_members,
    to_pins,
    unplaced,
)
from sampan.live import ToolLog, open_session, pump
from sampan.memories import BucketBlobs, VeoGenerator, decode_push, render
from sampan.models import AffectState, Ask, Precision, When
from sampan.notifications import mark_seen, notifications_for, unseen_count
from sampan.places import GeminiPlaceResolver
from sampan.quiet import is_quiet
from sampan.repository import Repository
from sampan.retrieval import FactGraph, SearchTrace, search_facts
from sampan.store import DocumentStore, get_document_store
from sampan.tools import CallMemory

log = logging.getLogger("sampan.app")

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


class SeenRequest(BaseModel):
    ids: list[str] = Field(default_factory=list)


class DraftFact(BaseModel):
    """A fact the demo invented. Never stored."""

    # Empty is allowed: a demo may invent a fact about someone the archive has
    # never heard of, and rejecting that surfaced as "could not reach the
    # archive", which is both wrong and unhelpful.
    subject_id: str = Field(default="", max_length=120)
    # Typed as the enum so an unknown verb is a 422 at the boundary. As a bare
    # string it reached `Predicate(...)` inside the handler and raised, which
    # the client saw as a 500 and reported as "could not reach the archive".
    predicate: Predicate = Predicate.WORKED_AT
    object_literal: str = Field(default="", max_length=200)
    statement: str = Field(min_length=1, max_length=400)


class Supersession(BaseModel):
    """A later telling that replaces an earlier one.

    Retiring a fact on its own answers "stop asserting this". It does not show
    the thing worth showing, which is that the archive holds *both* tellings and
    knows which one it currently stands behind. A supersession carries the
    replacement with it, so the drawing gets a retired edge and a fresh one on
    the same subject and you can see the belief move.
    """

    # The telling being replaced. Named explicitly rather than inferred: the
    # real path asks a model which fact a new one disagrees with, and a demo
    # that guessed would be claiming a capability it is not exercising.
    fact_id: str = Field(min_length=1, max_length=200)
    statement: str = Field(min_length=1, max_length=400)
    # What the new edge points at. The client extracts it from the sentence for
    # a readable label; empty is fine and falls back to the sentence.
    object_literal: str = Field(default="", max_length=200)


class SearchRequest(BaseModel):
    """A question, plus whatever the demo has added, retired or replaced.

    The sandbox rides on the request rather than living on the server. Nothing
    is written, so a demo cannot leave marks on her archive -- and the whole
    product rests on the family being able to correct the system and never her.
    Stateless also means reproducible: the same request always answers the same.
    """

    question: str = Field(min_length=1, max_length=300)
    added: list[DraftFact] = Field(default_factory=list, max_length=20)
    retired: list[str] = Field(default_factory=list, max_length=20)
    replaced: list[Supersession] = Field(default_factory=list, max_length=20)


class ChooseAskRequest(BaseModel):
    ask_id: str = Field(min_length=1, max_length=200)


class AboutRequest(BaseModel):
    question: str = Field(min_length=1, max_length=300)


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


class ExtractionStack(NamedTuple):
    """Everything `finish_call` needs to fold a call back into memory.

    Named and constructed in one place because the alternative failed silently:
    `finish_call` takes `fact_extractor` and `judge` as optional keywords, the
    WebSocket handler passed neither, and the whole memory-v2 pass -- fact
    extraction, contradiction, every edge the graph is made of -- was skipped on
    every real call for as long as it has existed. Nothing raised. The graph
    only ever grew when someone ran `scripts/backfill_facts.py` by hand.

    Optionality is right for the seam, which is exercised with fakes. It is
    wrong for production, so production builds all three together or not at all.
    """

    stories: GeminiStoryExtractor
    facts: GeminiFactExtractor
    judge: GeminiContradictionJudge


def build_extraction_stack(settings: Settings) -> ExtractionStack:
    return ExtractionStack(
        stories=GeminiStoryExtractor(settings),
        facts=GeminiFactExtractor(settings),
        judge=GeminiContradictionJudge(settings),
    )


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


def _judge_swap(settings: Settings, new: Fact, old: Fact) -> Judgement:
    """Which kind of disagreement, decided by the model a real call uses.

    Falls back to conflicting testimony, which is the conservative half of the
    pair: it moves transaction time and leaves her own dates untouched, so a
    demo running without cloud credentials still refuses to imply she was
    wrong. The verdict says `confidence=0` so the page can be honest that
    nothing was actually judged, rather than showing a fallback as a finding.

    Failing open matters more here than elsewhere: this runs live in front of
    an audience, and a flat network should cost the explanation, not the demo.
    """
    if not settings.configured:
        return Judgement(kind=Disagreement.CONFLICTING_TESTIMONY, confidence=0.0)
    try:
        return GeminiContradictionJudge(settings).judge(new, old)
    except Exception:
        log.exception("contradiction judge failed in the graph demo")
        return Judgement(kind=Disagreement.CONFLICTING_TESTIMONY, confidence=0.0)


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


_LINK_CACHE = "_place_links"


def _link_relational_places(
    settings: Settings, store: DocumentStore, narrator_id: str, places: list[Any]
) -> list[Any]:
    """Place stories she located by relationship rather than address.

    Her best stories name a place as "my father's coffee shop" or "home", which no
    geocoder can touch — but she often gave the address in another session, so
    the answer is already in the archive and only needs joining. Every link
    carries the sentence that justifies it; links without one are dropped.
    """
    from sampan.places import GeminiPlaceLinker, PlaceLink, apply_links

    unknown = [p.raw_name for p in places if not p.locatable]
    known = [p for p in places if p.locatable]
    if not unknown or not known:
        return places

    cached = store.get(_LINK_CACHE, narrator_id)
    if cached is not None:
        links = [PlaceLink.model_validate(x) for x in cached.get("links", [])]
        return apply_links(places, links)

    if not settings.configured:
        return places

    repository = Repository(store)
    transcripts = "\n\n".join(
        raw.get("transcript", "") for raw in store.list(f"conversations__{narrator_id}")
    )
    links: list[Any] = []
    with contextlib.suppress(Exception):
        links = GeminiPlaceLinker(settings).link(unknown, known, transcripts)
    store.put(
        _LINK_CACHE,
        narrator_id,
        {"links": [link.model_dump(mode="json") for link in links]},
    )
    _ = repository
    return apply_links(places, links)


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

    @app.post(
        "/api/family/{narrator_id}/about",
        dependencies=[Depends(require_api_key)],
    )
    def ask_about_her(
        narrator_id: str,
        body: AboutRequest,
        settings: Annotated[Settings, Depends(get_settings)],
        store: Annotated[DocumentStore, Depends(get_store)],
    ) -> dict[str, Any]:
        """Ask a question about someone, answered only from what she said.

        When the archive does not contain the answer, the reply says so and
        offers the question back — which is the useful half: a gap becomes the
        next thing Xiao Chuan asks her.
        """
        from sampan.ask_about import GeminiAboutHer

        repository = Repository(store)
        member = next(
            (m for m in list_members(repository) if m.narrator_id == narrator_id), None
        )
        agent = GeminiAboutHer(
            settings,
            who=member.display_name if member else narrator_id,
            cards=cards_for(repository, narrator_id),
            entities=repository.load_entities(narrator_id),
        )
        try:
            answer = agent.answer(body.question)
        except Exception as error:  # noqa: BLE001
            raise HTTPException(status_code=502, detail=str(error)) from error

        payload = answer.model_dump(mode="json")
        # Turning the follow-up into a queued question is the family's choice,
        # not something that happens because they were curious out loud.
        payload["can_ask_her"] = bool(answer.follow_up)
        return payload

    @app.get("/api/bell/{viewer_id}", dependencies=[Depends(require_api_key)])
    def bell(
        viewer_id: str, store: Annotated[DocumentStore, Depends(get_store)]
    ) -> dict[str, Any]:
        """What this person should see when they open the bell."""
        repository = Repository(store)
        items = notifications_for(repository, viewer_id, list_members(repository))
        return {
            "unseen": unseen_count(items),
            "notifications": [n.model_dump(mode="json") for n in items],
        }

    @app.post("/api/bell/{viewer_id}/seen", dependencies=[Depends(require_api_key)])
    def bell_seen(
        viewer_id: str,
        body: SeenRequest,
        store: Annotated[DocumentStore, Depends(get_store)],
    ) -> dict[str, Any]:
        repository = Repository(store)
        # Expand groups: dismissing "told 11 new stories" must settle all eleven.
        items = notifications_for(repository, viewer_id, list_members(repository))
        expanded = list(body.ids)
        for item in items:
            if item.id in body.ids:
                expanded.extend(item.covers)
        mark_seen(repository, viewer_id, expanded)
        return {"ok": True, "settled": len(expanded)}

    @app.get("/api/household", dependencies=[Depends(require_api_key)])
    def household(
        settings: Annotated[Settings, Depends(get_settings)],
        store: Annotated[DocumentStore, Depends(get_store)],
        member: str | None = None,
    ) -> dict[str, Any]:
        """The shared family map, or one member's scoped to them.

        The only view that crosses narrators. Everywhere else the archive is
        one person's, because that is how the agent remembers.
        """
        repository = Repository(store)
        members = list_members(repository)
        wanted = [m for m in members if member is None or m.narrator_id == member]

        pins: list[dict[str, Any]] = []
        without_place: list[dict[str, Any]] = []
        for person in wanted:
            cards = cards_for(repository, person.narrator_id)
            if not cards:
                continue
            places = _resolve_places(settings, store, cards)
            places = _link_relational_places(
                settings, store, person.narrator_id, places
            )
            pins.extend(
                p.model_dump(mode="json")
                for p in to_pins(
                    cards,
                    places,
                    narrator_id=person.narrator_id,
                    narrator_name=person.display_name,
                )
            )
            without_place.extend(
                {
                    **c.model_dump(),
                    "narrator_id": person.narrator_id,
                    "narrator_name": person.display_name,
                }
                for c in unplaced(cards, places)
            )

        return {
            "members": [m.model_dump(mode="json") for m in members],
            "pins": pins,
            "unplaced": without_place,
        }

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
        cards = build_cards(
            repository.load_stories(narrator_id),
            repository.private_subjects(narrator_id),
        )
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
            places = _link_relational_places(settings, store, narrator_id, places)
            payload["map"] = build_map(cards, places).model_dump(mode="json")
            # The journey view needs every story's year to order the stops,
            # not just the ones grouped under a pin.
            payload["allStories"] = [c.model_dump() for c in timeline(cards)]
        elif view == "timeline":
            payload["stories"] = [c.model_dump() for c in timeline(cards)]
        elif view == "chapters":
            # Her life in named sections, clustered from the fact graph rather
            # than written by anyone. Facts carry the sentence she said, so a
            # chapter can be opened all the way down to her own words.
            by_id = {e.entity_id: e for e in entities}
            facts = repository.load_facts(narrator_id)
            # Both tellings are kept and the older one is visibly retired,
            # never deleted -- she is not corrected, and the archive does not
            # quietly drop the sentence it stopped believing.
            retired = [
                f
                for f in repository.load_facts(narrator_id, current_only=False)
                if not f.is_current and f.quote
            ]
            payload["chapters"] = [
                {
                    "id": chapter.community_id,
                    "name": chapter.name,
                    "summary": chapter.summary,
                    # Names, for recognition. Extraction occasionally produces
                    # a whole clause as an entity -- "toast the bread, charcoal
                    # fire one, spread butter" -- which is a phrase she said
                    # rather than something anyone would recognise as a name.
                    # It stays in the graph and out of the chips.
                    "members": [
                        by_id[m].canonical_name
                        for m in chapter.member_ids
                        if m in by_id and len(by_id[m].canonical_name) <= 30
                    ],
                    "facts": [
                        {"fact": f.render(), "she_said": f.quote}
                        for f in facts
                        if f.subject_id in set(chapter.member_ids)
                        or (f.object_id or "") in set(chapter.member_ids)
                    ][:6],
                    "retired": [
                        {"fact": f.render(), "she_said": f.quote}
                        for f in retired
                        if f.subject_id in set(chapter.member_ids)
                        or (f.object_id or "") in set(chapter.member_ids)
                    ],
                }
                for chapter in repository.load_communities(narrator_id)
                if chapter.member_ids
            ]
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
        actually uses — "the estate at Sungai Siput", not "Sungai Siput".
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

    @app.post(
        "/api/family/{narrator_id}/search", dependencies=[Depends(require_api_key)]
    )
    def search_archive(
        narrator_id: str,
        body: SearchRequest,
        store: Annotated[DocumentStore, Depends(get_store)],
        settings: Annotated[Settings, Depends(get_settings)],
    ) -> dict[str, Any]:
        """Run the agent's own retrieval, and return its working.

        The same `search_facts` the Companion calls mid-sentence, driven from a
        text box instead — so the ranking can be watched without waiting for
        the agent to decide to reach for something.

        Nodes and edges come back laid out by hop distance rather than as a
        flat list, because the distance *is* the structure: seeds at zero, then
        what they reach. There is no model anywhere in this path, so the same
        query returns the same numbers every time.
        """
        repository = Repository(store)
        entities = repository.load_entities(narrator_id)
        names = {e.entity_id: e.canonical_name for e in entities}

        # Retired facts are loaded too: the trace names what it stopped
        # asserting, which is the thing a flat index cannot report.
        stored = repository.load_facts(narrator_id, current_only=False)

        # The sandbox, applied in memory only. `retired` expires a fact the way
        # a later telling would -- transaction time, leaving valid time exactly
        # as she said it, because even a demo does not get to imply she was
        # wrong. `added` invents new edges so a node can be watched appearing.
        expiring = set(body.retired)
        working = [
            f.model_copy(
                update={"t_expired": datetime.now(UTC), "superseded_by": "demo"}
            )
            if f.fact_id in expiring
            else f
            for f in stored
        ]
        # An invented edge gets an invented node at the far end. Without one
        # it has a subject and nothing to point at, so the count goes up and
        # the drawing does not change -- which is the one thing a create demo
        # has to show.
        invented: dict[str, str] = {}
        for i, draft in enumerate(body.added):
            target = f"demo_node_{i}"
            invented[target] = draft.object_literal or draft.statement
            subject = draft.subject_id
            if subject not in names:
                # Nobody named -- or named somebody who does not exist, which
                # amounts to the same thing and used to draw a node labelled
                # with the raw id. Both ends are invented, so the edge floats
                # rather than being quietly attached to whichever node happened
                # to be first, which would draw a relationship the sentence
                # does not claim.
                subject = f"demo_subject_{i}"
                invented[subject] = "someone new"
            working.append(
                Fact(
                    fact_id=f"demo_{i}",
                    subject_id=subject,
                    predicate=draft.predicate,
                    object_id=target,
                    object_literal=draft.object_literal,
                    statement=draft.statement,
                    quote=draft.statement,
                    episode_id="demo",
                )
            )

        # A supersession: she says it differently now. The replacement takes the
        # old fact's subject and predicate by copying them, so the new edge
        # lands on the same node and the two can be seen side by side.
        #
        # *Which* fact is being corrected came from a click -- on a real call
        # that is a deterministic narrowing to the same subject and predicate,
        # and this is a dict lookup instead.
        #
        # *Which kind* of disagreement it is, though, is decided here by the
        # same judge a real call uses, because it is the question that matters
        # and the answer is not obvious:
        #
        #   state change          she moved. Both tellings were true, one after
        #                         the other, so `valid_to` closes on the old one
        #                         and both stay current.
        #   conflicting testimony one event, two accounts. `t_expired` moves and
        #                         her valid time is left exactly as she said it.
        #
        # Hardcoding the second was wrong: "Ah Chwee lives in Kampung Baru now"
        # is a state change, and calling it conflicting testimony collapses the
        # two clocks -- the precise error the whole bi-temporal design exists to
        # prevent. Guessing it in a panel built to explain the difference would
        # have been the worst place in the product to get it wrong.
        verdicts: list[dict[str, Any]] = []
        by_id = {f.fact_id: f for f in working}
        for i, swap in enumerate(body.replaced):
            old = by_id.get(swap.fact_id)
            if old is None or not old.is_current:
                continue
            target = f"demo_super_node_{i}"
            invented[target] = swap.object_literal or swap.statement
            fresh = Fact(
                fact_id=f"demo_super_{i}",
                subject_id=old.subject_id,
                predicate=old.predicate,
                object_id=target,
                object_literal=swap.object_literal,
                statement=swap.statement,
                quote=swap.statement,
                episode_id="demo",
                # `apply_state_change` closes the old interval where the new one
                # opens, so a state change needs somewhere to close it to. She
                # is describing how things stand now, which is what this says.
                valid_from=When(
                    raw_phrase="now",
                    start_year=datetime.now(UTC).year,
                    precision=Precision.YEAR,
                    confidence=0.6,
                ),
            )
            judged = _judge_swap(settings, fresh, old)
            if judged.kind is Disagreement.STATE_CHANGE:
                amended = apply_state_change(old, fresh)
            else:
                amended = apply_conflicting_testimony(old, fresh)
            verdicts.append(
                {
                    "fact_id": old.fact_id,
                    "kind": judged.kind.value,
                    "reason": judged.reason,
                    "confidence": judged.confidence,
                    "clock": (
                        "valid time"
                        if judged.kind is Disagreement.STATE_CHANGE
                        else "transaction time"
                    ),
                    "judged": judged.confidence > 0.0,
                    "replacement": fresh.fact_id,
                }
            )
            working = [
                amended if f.fact_id == old.fact_id else f for f in working
            ]
            working.append(fresh)

        graph = FactGraph(facts=working, entities=entities)

        needle = body.question.strip()

        # Grounding: which entities does this question actually name?
        #
        # `remember` is handed a short name and can match on equality. A typed
        # question is a sentence, so the entity has to be found *inside* it --
        # "what did her father do at the coffee shop" names Lim Ah Hock by his
        # role and Ah Gong's shop by part of its name. TrustGraph spends an LLM
        # call on this step; a substring sweep over a few dozen entities is
        # both cheaper and reproducible.
        #
        # Guarded by length: a two-character name would match almost any
        # sentence, which is the same failure `_MIN_QUERY_TERM` fixes in BM25.
        asked = needle.lower()
        seeds = [
            e.entity_id
            for e in entities
            if e.merged_into is None
            and any(
                len(term) >= 4 and term.lower() in asked
                for term in [e.canonical_name, e.role or "", *e.aliases]
            )
        ]

        held: list[SearchTrace] = []
        found = search_facts(
            needle, graph, seeds=seeds, limit=5, on_trace=held.append
        )
        trace = held[0] if held else SearchTrace(query=needle)

        rank_by_id = {f.fact_id: i for i, f in enumerate(found)}
        scored = {c.fact_id: c for c in trace.candidates}
        # Demo edges are always drawn, ranked or not. They are the thing that
        # was just added, and an edge that vanishes because it does not match
        # the current question is indistinguishable from one that failed.
        drawn = [
            f
            for f in graph.facts
            if f.fact_id in scored
            or not f.is_current
            or f.fact_id.startswith("demo_")
        ]

        touched: set[str] = {*trace.seeds}
        for fact in drawn:
            touched.add(fact.subject_id)
            if fact.object_id:
                touched.add(fact.object_id)

        return {
            "trace": trace.model_dump(mode="json"),
            # What the judge made of each correction. The only part of this
            # response that came from a model, and the page says so.
            "verdicts": verdicts,
            "nodes": [
                {
                    "id": entity_id,
                    # The real name, at full length. Shortening it for the
                    # drawing is the drawing's business: the create panel finds
                    # its subject by looking for a node name inside the typed
                    # sentence, and a truncated name would stop matching.
                    "name": invented.get(entity_id) or names.get(entity_id, entity_id),
                    "hops": trace.reached.get(entity_id),
                    "seed": entity_id in trace.seeds,
                    "invented": entity_id in invented,
                }
                for entity_id in sorted(touched)
            ],
            "edges": [
                {
                    "fact_id": fact.fact_id,
                    "source": fact.subject_id,
                    "target": fact.object_id or "",
                    "literal": fact.object_literal,
                    "predicate": fact.predicate.value,
                    "statement": fact.statement,
                    "quote": fact.quote,
                    "rank": rank_by_id.get(fact.fact_id),
                    "retired": not fact.is_current,
                    "superseded_by": fact.superseded_by or "",
                    # Both clocks, so the page can show them side by side.
                    #
                    # Valid time is her life: when a thing was true, in her own
                    # words, and often absent because she rarely speaks in
                    # dates. Transaction time is the archive's belief: when it
                    # started asserting this and, if ever, when it stopped.
                    #
                    # A state change moves `valid_to`. Conflicting testimony
                    # moves `t_expired`. Watching which field fills in is the
                    # clearest way to see that they are not the same clock.
                    "valid_from": fact.valid_from.raw_phrase
                    if fact.valid_from
                    else "",
                    "valid_to": fact.valid_to.raw_phrase if fact.valid_to else "",
                    "t_created": fact.t_created.isoformat(),
                    "t_expired": fact.t_expired.isoformat() if fact.t_expired else "",
                }
                for fact in drawn
            ],
        }

    @app.get(
        "/api/family/{narrator_id}/changes", dependencies=[Depends(require_api_key)]
    )
    def graph_changes(
        narrator_id: str,
        store: Annotated[DocumentStore, Depends(get_store)],
        limit: int = 6,
    ) -> dict[str, Any]:
        """What each call did to the graph: nodes created, edges added, edges retired.

        Reconstructed from stored data rather than read from the live
        `GraphChange` record, so it works on the calls already in the archive
        instead of only on ones made from now on. Nothing here is inferred:
        `first_mentioned_in` is written when an entity is created and
        `episode_id` when a fact is, so both answers come from the same
        conversation that produced them.

        What reconstruction cannot recover is *how* a mention was matched --
        alias, kin role, containment -- because resolution records that at the
        moment it happens. Calls made from now on carry it on the conversation.
        """
        repository = Repository(store)
        entities = repository.load_entities(narrator_id)
        facts = repository.load_facts(narrator_id, current_only=False)
        names = {e.entity_id: e.canonical_name for e in entities}

        rows = store.list(f"conversations__{narrator_id}")
        rows.sort(key=lambda raw: raw.get("occurred_at") or "", reverse=True)

        calls: list[dict[str, Any]] = []
        for raw in rows[: max(1, min(limit, 30))]:
            conversation_id = raw.get("conversation_id", "")
            created = [e for e in entities if e.first_mentioned_in == conversation_id]
            added = [f for f in facts if f.episode_id == conversation_id]
            # Retired *by* this call: the fact that replaced it came from here.
            replaced_by = {f.fact_id for f in added}
            retired = [
                f
                for f in facts
                if not f.is_current and (f.superseded_by or "") in replaced_by
            ]
            if not (created or added or retired):
                continue
            calls.append(
                {
                    "conversation_id": conversation_id,
                    "occurred_at": raw.get("occurred_at", ""),
                    "turns": raw.get("turns", 0),
                    # Recorded live from rev 10 onward; absent on older calls.
                    "recorded": raw.get("graph_change") or None,
                    "created": [
                        {
                            "id": e.entity_id,
                            "name": e.canonical_name,
                            "type": e.type.value,
                            "role": e.role or "",
                        }
                        for e in created
                    ],
                    "added": [
                        {
                            "fact_id": f.fact_id,
                            "subject": names.get(f.subject_id, f.subject_id),
                            "object": names.get(f.object_id or "", f.object_literal),
                            "predicate": f.predicate.value,
                            "statement": f.statement,
                            "quote": f.quote,
                        }
                        for f in added
                    ],
                    "retired": [
                        {
                            "fact_id": f.fact_id,
                            "statement": f.statement,
                            "superseded_by": f.superseded_by or "",
                            # Which clock moved. valid_to means the world
                            # changed; t_expired means she told it differently.
                            "clock": "valid time"
                            if f.valid_to
                            else "transaction time",
                        }
                        for f in retired
                    ],
                }
            )

        return {"calls": calls}

    @app.get("/api/talk/{narrator_id}/calls", dependencies=[Depends(require_api_key)])
    def call_log(
        narrator_id: str,
        store: Annotated[DocumentStore, Depends(get_store)],
        limit: int = 10,
    ) -> dict[str, Any]:
        """What the agent reached for, call by call, newest first.

        The tool record is the only evidence of what the agent did with its
        memory: the transcript shows what it said, and this shows what it
        looked up before saying it. Without it a wrong answer mid-call is
        unfalsifiable after the fact — you cannot tell a bad lookup from a
        good lookup badly used.

        `fact_refusals` is the other half: what extraction declined and which
        rule declined it, so a fact she plainly stated going missing has an
        explanation rather than a shrug.
        """
        rows = store.list(f"conversations__{narrator_id}")
        rows.sort(key=lambda raw: raw.get("occurred_at") or "", reverse=True)
        return {
            "calls": [
                {
                    "conversation_id": raw.get("conversation_id", ""),
                    "occurred_at": raw.get("occurred_at", ""),
                    "turns": raw.get("turns", 0),
                    "tool_calls": raw.get("tool_calls", []),
                    "fact_refusals": raw.get("fact_refusals", []),
                    "searches": raw.get("searches", []),
                    "unscreened": bool(raw.get("unscreened")),
                    "screened": raw.get("screened", []),
                }
                for raw in rows[: max(1, min(limit, 50))]
            ]
        }

    @app.post(
        "/api/talk/{narrator_id}/pending/choose",
        dependencies=[Depends(require_api_key)],
    )
    def choose_pending(
        narrator_id: str,
        body: ChooseAskRequest,
        store: Annotated[DocumentStore, Depends(get_store)],
    ) -> dict[str, Any]:
        """Answer this one next.

        Opening a specific question from the bell has to change what the call
        asks, not only what the screen shows. Without this the agent read the
        oldest question in the queue aloud whichever one she had tapped, and
        said the wrong person's name while doing it.
        """
        chosen = Repository(store).choose_ask(narrator_id, body.ask_id)
        if not chosen:
            raise HTTPException(status_code=404, detail="No such question is waiting.")
        return {"ok": True, "ask_id": body.ask_id}

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
            # The question itself. Without it the bell says "Wei Lun asked you
            # something", she taps, and the screen shows his name and nothing
            # he wanted to know -- which is the one thing the bell exists to
            # carry across.
            "question": ask.question,
            "voice_note": ask.voice_note_url,
        }

    @app.post("/internal/memories", dependencies=[Depends(require_api_key)])
    def make_memory(
        body: dict[str, Any],
        settings: Annotated[Settings, Depends(get_settings)],
        store: Annotated[DocumentStore, Depends(get_store)],
    ) -> dict[str, Any]:
        """Pub/Sub push: generate one story's image.

        Always 200, even on failure. A push endpoint that returns an error gets
        the same message redelivered, and redelivering a Veo call is expensive
        in a way that redelivering most things is not — a wedged message could
        bill for hours. The outcome is in the body instead.

        Auth is the shared key on the subscription's push URL rather than an
        OIDC token: the whole service already gates on it, and one auth model
        is easier to keep correct than two.
        """
        request = decode_push(body)
        if request is None:
            return {"ok": False, "reason": "unreadable message"}
        if not settings.memories_bucket:
            return {"ok": False, "reason": "no SAMPAN_MEMORIES_BUCKET configured"}

        try:
            asset = render(
                request,
                VeoGenerator(settings),
                BucketBlobs(settings.memories_bucket),
            )
        except Exception as error:  # noqa: BLE001 -- see the docstring
            return {"ok": False, "story_id": request.story_id, "error": str(error)}

        Repository(store).save_memory_asset(
            request.narrator_id, asset.model_dump(mode="json")
        )
        return {"ok": True, "story_id": asset.story_id, "video_url": asset.video_url}

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
        tool_log = ToolLog()

        async def relay(message: dict[str, Any]) -> None:
            if (text := message.get("user_transcript")) is not None:
                transcript.add("user", text)
            if (text := message.get("agent_transcript")) is not None:
                transcript.add("agent", text)
            # Recorded here rather than inside the pump so the log holds
            # exactly what the browser was told, and there is one thing to keep
            # correct instead of two.
            tool_log.observe(message, turn=len(transcript))
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
                stack = build_extraction_stack(settings)
                await asyncio.to_thread(
                    finish_call,
                    repository,
                    stack.stories,
                    prepared,
                    transcript,
                    narrator_id=user_id,
                    fact_extractor=stack.facts,
                    judge=stack.judge,
                    tool_calls=tool_log.as_records(),
                    settings=settings,
                    screener=build_screen(settings),
                )

    static_dir = find_static_dir()
    if static_dir is not None:
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

    return app


app = create_app()
