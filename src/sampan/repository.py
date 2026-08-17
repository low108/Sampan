"""Storing and loading what the agent remembers.

Shapes follow PRD section 8. The split matters: a narrator's *memory* — threads,
anchors, preferences, sensitivities — is small and always read whole, so it
lives in one profile document. Stories and entities grow without bound and get
a collection each, because a single document would hit Firestore's 1MB limit
inside a year of daily calls.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from sampan.models import (
    Anchor,
    Ask,
    ClosureReason,
    Entity,
    Preference,
    ScoredStory,
    SensitiveTopic,
    Thread,
)
from sampan.store import DocumentStore

PROFILES = "profiles"
ENTITIES = "entities"
STORIES = "stories"
CONVERSATIONS = "conversations"
ASKS = "asks"
CONCERNS = "concerns"
FORGOTTEN = "forgotten"
PRIVATE = "private"


class NarratorMemory(BaseModel):
    """Everything a call needs to know before it starts.

    Read whole at the top of every call, written whole at the end. Small by
    construction: the things that grow live elsewhere.
    """

    narrator_id: str
    display_name: str = ""
    threads: list[Thread] = Field(default_factory=list)
    anchors: list[Anchor] = Field(default_factory=list)
    preferences: list[Preference] = Field(default_factory=list)
    sensitivities: list[SensitiveTopic] = Field(default_factory=list)
    session_count: int = 0
    last_closure: ClosureReason | None = None
    updated_at: str | None = None


class Repository:
    """Persistence for one family's archive."""

    def __init__(self, store: DocumentStore) -> None:
        self._store = store

    # --- narrator memory --------------------------------------------------

    def load_memory(self, narrator_id: str) -> NarratorMemory:
        """Return stored memory, or an empty one for a narrator we have never
        spoken to. A first call is not an error."""
        raw = self._store.get(PROFILES, narrator_id)
        if raw is None:
            return NarratorMemory(narrator_id=narrator_id)
        return NarratorMemory.model_validate(raw)

    def save_memory(self, memory: NarratorMemory) -> None:
        memory.updated_at = datetime.now(UTC).isoformat()
        self._store.put(PROFILES, memory.narrator_id, memory.model_dump(mode="json"))

    # --- entities ---------------------------------------------------------

    def load_entities(self, narrator_id: str) -> list[Entity]:
        return [
            Entity.model_validate(raw)
            for raw in self._store.list(self._scoped(ENTITIES, narrator_id))
        ]

    def save_entities(self, narrator_id: str, entities: list[Entity]) -> None:
        collection = self._scoped(ENTITIES, narrator_id)
        for entity in entities:
            self._store.put(
                collection, entity.entity_id, entity.model_dump(mode="json")
            )

    # --- stories ----------------------------------------------------------

    def save_stories(
        self, narrator_id: str, conversation_id: str, stories: list[ScoredStory]
    ) -> list[str]:
        """Store one call's stories. Returns the ids written."""
        collection = self._scoped(STORIES, narrator_id)
        written: list[str] = []
        for index, story in enumerate(stories):
            story_id = f"{conversation_id}_{index:02d}"
            payload = story.model_dump(mode="json")
            payload["story_id"] = story_id
            payload["narrator_id"] = narrator_id
            payload["conversation_id"] = conversation_id
            self._store.put(collection, story_id, payload)
            written.append(story_id)
        return written

    def load_stories(self, narrator_id: str) -> list[dict]:
        return self._store.list(self._scoped(STORIES, narrator_id))

    # --- conversations ----------------------------------------------------

    def save_conversation(
        self, narrator_id: str, conversation_id: str, transcript: str, **extra: object
    ) -> None:
        self._store.put(
            self._scoped(CONVERSATIONS, narrator_id),
            conversation_id,
            {
                "conversation_id": conversation_id,
                "narrator_id": narrator_id,
                "transcript": transcript,
                "occurred_at": datetime.now(UTC).isoformat(),
                **extra,
            },
        )

    # --- care -------------------------------------------------------------

    def raise_concern(
        self, narrator_id: str, kind: str, detail: str, conversation_id: str = ""
    ) -> str:
        """Record something the family needs to know about, now.

        Written the moment it is flagged rather than at the end of the call:
        the agent has just told her it is telling her family, and a fall should
        not wait for her to hang up.
        """
        concern_id = f"care_{datetime.now(UTC).strftime('%Y%m%d%H%M%S%f')}"
        self._store.put(
            self._scoped(CONCERNS, narrator_id),
            concern_id,
            {
                "concern_id": concern_id,
                "narrator_id": narrator_id,
                "kind": kind,
                "detail": detail,
                "conversation_id": conversation_id,
                "raised_at": datetime.now(UTC).isoformat(),
                "seen_by_family": False,
            },
        )
        return concern_id

    def open_concerns(self, narrator_id: str) -> list[dict]:
        return [
            raw
            for raw in self._store.list(self._scoped(CONCERNS, narrator_id))
            if not raw.get("seen_by_family")
        ]

    # --- privacy ----------------------------------------------------------

    def mark_private(self, narrator_id: str, subject: str) -> None:
        """Record that she asked for something to stay off the family's view.

        The agent tells her "I won't write that down" when she asks. That sentence
        has to be true, which means it has to survive the call.
        """
        key = subject.strip()
        if not key:
            return
        self._store.put(
            self._scoped(PRIVATE, narrator_id),
            f"priv_{abs(hash(key)) % 10**12}",
            {"subject": key, "marked_at": datetime.now(UTC).isoformat()},
        )

    def private_subjects(self, narrator_id: str) -> list[str]:
        return [
            raw["subject"]
            for raw in self._store.list(self._scoped(PRIVATE, narrator_id))
            if raw.get("subject")
        ]

    # --- raw transcripts --------------------------------------------------

    def search_transcripts(
        self, narrator_id: str, query: str, limit: int = 3
    ) -> list[dict]:
        """Search what she actually said, not what was extracted from it.

        Structured records lose sequence, context and affect (Pink et al.,
        2025). The consensus design is a structured index that points back into
        raw text, so the agent can reach her own words when the graph has only
        a summary of them.
        """
        needle = query.strip()
        if not needle:
            return []
        hits = []
        for raw in self._store.list(self._scoped(CONVERSATIONS, narrator_id)):
            transcript = raw.get("transcript") or ""
            if needle not in transcript:
                continue
            for line in transcript.splitlines():
                # Only her lines. The agent quoting itself back at her is not
                # remembering.
                if line.startswith("K:") and needle in line:
                    hits.append(
                        {
                            "said": line[2:].strip(),
                            "conversation_id": raw.get("conversation_id", ""),
                            "when": raw.get("occurred_at", ""),
                        }
                    )
        hits.sort(key=lambda h: h["when"], reverse=True)
        return hits[:limit]

    # --- forgetting -------------------------------------------------------

    def forget(self, narrator_id: str, subject: str) -> None:
        """Record that she asked for something to be forgotten.

        A tombstone rather than a delete: the request itself has to survive, or
        the next extraction pass would happily rebuild what she asked to lose.
        """
        key = subject.strip()
        if not key:
            return
        self._store.put(
            self._scoped(FORGOTTEN, narrator_id),
            f"forget_{abs(hash(key)) % 10**12}",
            {"subject": key, "asked_at": datetime.now(UTC).isoformat()},
        )

    def forgotten(self, narrator_id: str) -> list[str]:
        return [
            raw["subject"]
            for raw in self._store.list(self._scoped(FORGOTTEN, narrator_id))
            if raw.get("subject")
        ]

    # --- family asks ------------------------------------------------------

    def queue_ask(self, narrator_id: str, ask: Ask) -> None:
        payload = ask.model_dump(mode="json")
        payload["delivered"] = False
        payload["created_at"] = ask.created_at or datetime.now(UTC).isoformat()
        self._store.put(self._scoped(ASKS, narrator_id), ask.ask_id, payload)

    def pending_ask(self, narrator_id: str) -> Ask | None:
        """The oldest undelivered question.

        One per call by design: two would turn a conversation into an inbox.
        """
        undelivered = [
            raw
            for raw in self._store.list(self._scoped(ASKS, narrator_id))
            if not raw.get("delivered")
        ]
        if not undelivered:
            return None
        oldest = min(undelivered, key=lambda raw: raw.get("created_at") or "")
        return Ask.model_validate({k: v for k, v in oldest.items() if k != "delivered"})

    def mark_ask_delivered(self, narrator_id: str, ask_id: str) -> None:
        collection = self._scoped(ASKS, narrator_id)
        raw = self._store.get(collection, ask_id)
        if raw is None:
            return
        raw["delivered"] = True
        raw["delivered_at"] = datetime.now(UTC).isoformat()
        self._store.put(collection, ask_id, raw)

    @staticmethod
    def _scoped(collection: str, narrator_id: str) -> str:
        """One collection per narrator.

        Firestore subcollections would be tidier, but the DocumentStore
        protocol is deliberately flat so the whole pipeline stays runnable
        against a dictionary.
        """
        return f"{collection}__{narrator_id}"
