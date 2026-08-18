"""Extracting facts from a finished conversation.

A second model call, not an extra field on the story schema. `Place` was once
used directly as the geocoder's `response_schema`, and because `Place` also
carried the linker's fields the model filled them unprompted -- routing around a
verification path that existed, was tested, and worked. The schema is part of
the prompt: a fact-extraction schema contains fact fields and nothing else.
"""

from __future__ import annotations

import uuid
from typing import Any, Protocol

from pydantic import BaseModel, Field

from sampan.config import Settings
from sampan.facts import Fact, Predicate, is_quoted
from sampan.models import Entity, When

FACT_PROMPT = """\
Below is a conversation with an elderly Malaysian Chinese woman about her life.
Extract the **facts** it establishes: durable things about her world, as opposed
to the stories she told.

A fact is a relationship between two things, true over some stretch of her life:
who lived where, who worked where, who was married to whom, who made what.

**People and places already known to the archive.** Use these exact ids when a
fact is about one of them. Do not invent ids.
{entities}

**The relations you may use.** These are the only ones. If what she said does
not fit one of them, do not force it -- leave it out.
{predicates}

For each fact:

- `subject_id`, `object_id`: ids from the list above. Use `object_literal`
  instead when the object is not a listed thing (a job, an object, a dish).
- `statement`: the fact as one plain sentence, in the third person, as a
  stranger would need it. This is what gets searched later, so write it to be
  found: "her father ran a coffee shop at Jalan Bandar", not "he ran it".
- `valid_from` / `valid_to`: when it started and stopped being true.
  **Keep her words.** If she said "before I married", `raw_phrase` is "before I
  married" -- then resolve a year only if the conversation supports one. A fact
  with no time is fine and normal; an invented year is not.
- `quote`: **the sentence she said that establishes this fact.** Copy it from
  the transcript. Not a summary of it, not your reasoning about it -- her words.
  If you cannot point at one sentence, do not record the fact.

Do not extract:
- Anything the agent said. Only what she asserts.
- Events as facts. "She told a story about the river" is not a fact.
- Anything you inferred but she did not say.

Transcript:
---
{transcript}
---
"""


class ExtractedFact(BaseModel):
    """What the model is allowed to answer with.

    Deliberately not `Fact`: that also carries `t_created`, `t_expired`,
    `superseded_by` and `fact_id`, which belong to the archive and not to the
    model. A field offered is a field that will be filled.
    """

    subject_id: str
    predicate: Predicate
    object_id: str | None = None
    object_literal: str = ""
    statement: str
    valid_from: When | None = None
    valid_to: When | None = None
    quote: str
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)


class FactBatch(BaseModel):
    facts: list[ExtractedFact]


class FactExtractor(Protocol):
    """Seam for the model call, so the pipeline runs offline in tests."""

    def extract(
        self, transcript: str, known_entities: list[Entity]
    ) -> list[ExtractedFact]: ...


def _entities_block(entities: list[Entity]) -> str:
    if not entities:
        return "  (none yet)"
    return "\n".join(
        f"  {e.entity_id}  {e.canonical_name}"
        f"{f' ({e.role})' if e.role else ''}"
        f"{f' — {e.detail[:70]}' if e.detail else ''}"
        for e in entities
        if e.merged_into is None
    )


def _predicates_block() -> str:
    return "\n".join(f"  {p.value}" for p in Predicate)


class GeminiFactExtractor:
    """Structured fact extraction against Gemini."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._cached_client: Any | None = None

    @property
    def _client(self) -> Any:
        if self._cached_client is None:
            from google import genai

            self._cached_client = genai.Client(
                vertexai=True,
                project=self._settings.project_id,
                location=self._settings.vertex_location,
            )
        return self._cached_client

    def extract(
        self, transcript: str, known_entities: list[Entity]
    ) -> list[ExtractedFact]:
        from google.genai import types

        response = self._client.models.generate_content(
            model=self._settings.archivist_model,
            contents=FACT_PROMPT.format(
                transcript=transcript,
                entities=_entities_block(known_entities),
                predicates=_predicates_block(),
            ),
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=FactBatch,
                temperature=0.1,
            ),
        )
        parsed = response.parsed
        if parsed is None:
            return []
        return list(parsed.facts)


def build_facts(
    extracted: list[ExtractedFact],
    *,
    transcript: str,
    known_entities: list[Entity],
    episode_id: str,
) -> list[Fact]:
    """Turn raw extractions into facts the archive will stand behind.

    Three ways a proposed fact is refused, all of them silent by design -- the
    archive simply asserts less rather than asserting something it cannot
    support:

    1. Its quote is not in the transcript. She did not say it.
    2. Its subject is not an entity we know. There is nothing to hang it on.
    3. It has neither an object entity nor an object literal, so it asserts
       nothing about anything.
    """
    known_ids = {e.entity_id for e in known_entities if e.merged_into is None}
    facts: list[Fact] = []

    for item in extracted:
        if not is_quoted(item.quote, transcript):
            continue
        if item.subject_id not in known_ids:
            continue
        if item.object_id is not None and item.object_id not in known_ids:
            # A real relationship pointing at an entity we do not have. Keep it
            # as a literal rather than dropping what she said.
            item = item.model_copy(
                update={
                    "object_literal": item.object_literal or item.object_id,
                    "object_id": None,
                }
            )
        if item.object_id is None and not item.object_literal.strip():
            continue

        facts.append(
            Fact(
                fact_id=f"fact_{episode_id}_{uuid.uuid4().hex[:8]}",
                subject_id=item.subject_id,
                predicate=item.predicate,
                object_id=item.object_id,
                object_literal=item.object_literal,
                statement=item.statement.strip(),
                valid_from=item.valid_from,
                valid_to=item.valid_to,
                episode_id=episode_id,
                quote=item.quote.strip(),
                confidence=item.confidence,
            )
        )
    return facts
