"""Storing and loading what the agent remembers.

Shapes follow PRD section 8. The split matters: a narrator's *memory* — threads,
anchors, preferences, sensitivities — is small and always read whole, so it
lives in one profile document. Stories and entities grow without bound and get
a collection each, because a single document would hit Firestore's 1MB limit
inside a year of daily calls.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from sampan.communities import Community
from sampan.facts import Fact
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
FACTS = "facts"
COMMUNITIES = "communities"


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

    # --- communities ------------------------------------------------------

    def load_communities(self, narrator_id: str) -> list[Community]:
        return [
            Community.model_validate(raw)
            for raw in self._store.list(self._scoped(COMMUNITIES, narrator_id))
        ]

    def save_communities(self, narrator_id: str, communities: list[Community]) -> None:
        """Replace the chapter list wholesale.

        A refresh recomputes every label, so merging would leave chapters that
        the current graph no longer supports.
        """
        collection = self._scoped(COMMUNITIES, narrator_id)
        for existing in self._store.list(collection):
            self._store.put(
                collection,
                existing["community_id"],
                {
                    "community_id": existing["community_id"],
                    "name": "",
                    "summary": "",
                    "member_ids": [],
                },
            )
        for community in communities:
            self._store.put(
                collection, community.community_id, community.model_dump(mode="json")
            )

    # --- facts ------------------------------------------------------------

    def load_facts(self, narrator_id: str, *, current_only: bool = True) -> list[Fact]:
        """The edges of the graph.

        Superseded facts are excluded by default: they remain in the archive
        because she said them, but the map, the letters and retrieval speak only
        what is currently believed. Pass `current_only=False` to read the
        history of a belief.
        """
        facts = [
            Fact.model_validate(raw)
            for raw in self._store.list(self._scoped(FACTS, narrator_id))
        ]
        return [f for f in facts if f.is_current] if current_only else facts

    def save_facts(self, narrator_id: str, facts: list[Fact]) -> None:
        collection = self._scoped(FACTS, narrator_id)
        for fact in facts:
            self._store.put(collection, fact.fact_id, fact.model_dump(mode="json"))

    def expire_fact(self, narrator_id: str, fact_id: str, superseded_by: str) -> None:
        """Retire a belief without deleting it.

        She told it differently later. The archive stops asserting the old
        version and keeps it readable, because both tellings are things she
        actually said.
        """
        collection = self._scoped(FACTS, narrator_id)
        raw = self._store.get(collection, fact_id)
        if raw is None:
            return
        raw["t_expired"] = datetime.now(UTC).isoformat()
        raw["superseded_by"] = superseded_by
        self._store.put(collection, fact_id, raw)

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

    # Bookkeeping the Ask model deliberately does not carry: whether a question
    # has been asked yet, and whether she picked it out of the queue herself.
    _ASK_INTERNAL = ("delivered", "delivered_at", "chosen")

    def _undelivered(self, narrator_id: str) -> list[dict[str, Any]]:
        rows = [
            raw
            for raw in self._store.list(self._scoped(ASKS, narrator_id))
            if not raw.get("delivered")
        ]
        rows.sort(key=lambda raw: raw.get("created_at") or "")
        return rows

    def _to_ask(self, raw: dict[str, Any]) -> Ask:
        return Ask.model_validate(
            {k: v for k, v in raw.items() if k not in self._ASK_INTERNAL}
        )

    def pending_asks(self, narrator_id: str) -> list[Ask]:
        """Every undelivered question, oldest first.

        The call only ever carries one of these (see `pending_ask`), but the
        bell must show all of them. Showing one meant a second question queued
        behind the first was invisible to everybody: the sender saw nothing
        appear, and the person it was for had no idea anyone was waiting.
        """
        return [self._to_ask(raw) for raw in self._undelivered(narrator_id)]

    def choose_ask(self, narrator_id: str, ask_id: str) -> bool:
        """Put this question at the front, because she picked it.

        Tapping "Wei Lun asked you something" and then hearing the agent ask
        somebody else's question is the archive contradicting itself out loud.
        The queue is still first-in-first-out; this is her overriding it, and
        it is the only thing that can.
        """
        collection = self._scoped(ASKS, narrator_id)
        found = False
        for raw in self._undelivered(narrator_id):
            wanted = raw.get("ask_id") == ask_id
            found = found or wanted
            if bool(raw.get("chosen")) == wanted:
                continue
            raw["chosen"] = wanted
            self._store.put(collection, raw["ask_id"], raw)
        return found

    def pending_ask(self, narrator_id: str) -> Ask | None:
        """The question this call will carry.

        One per call by design: two would turn a conversation into an inbox.
        The one she chose if she chose one, otherwise the one that has been
        waiting longest. This is the delivery queue, not the notification list.
        """
        rows = self._undelivered(narrator_id)
        if not rows:
            return None
        chosen = next((raw for raw in rows if raw.get("chosen")), None)
        return self._to_ask(chosen or rows[0])

    def mark_ask_delivered(self, narrator_id: str, ask_id: str) -> None:
        collection = self._scoped(ASKS, narrator_id)
        raw = self._store.get(collection, ask_id)
        if raw is None:
            return
        raw["delivered"] = True
        raw["delivered_at"] = datetime.now(UTC).isoformat()
        # A delivered question must not go on holding the front of the queue,
        # or the next call would open on the one she has already answered.
        raw["chosen"] = False
        self._store.put(collection, ask_id, raw)

    @staticmethod
    def _scoped(collection: str, narrator_id: str) -> str:
        """One collection per narrator.

        Firestore subcollections would be tidier, but the DocumentStore
        protocol is deliberately flat so the whole pipeline stays runnable
        against a dictionary.
        """
        return f"{collection}__{narrator_id}"
