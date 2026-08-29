"""When a new fact disagrees with one already held.

Zep's rule (arXiv 2501.13956 §2.2.3) is to have an LLM compare a new edge
against semantically related existing ones and, on a temporally overlapping
contradiction, set the old edge's `t_invalid` to the new edge's `t_valid`,
"consistently prioritising new information".

Adopted, with contradictions routed to the correct time axis — because two
different things wear the same shape, and only one of them is what Zep is built
for:

    state change          "she moved house in 2016"
        the world moved on. Both facts were true, at different times.
        → the old fact's valid time ends where the new one begins.

    conflicting testimony  "the shop closed in 1969" → "...in 1970"
        her *account* moved. Only one can be true; the shop closed once.
        → the old assertion expires on the transaction timeline. Valid time
          is left alone, because saying the shop "stopped closing in 1970" is
          a claim she never made.

An enterprise dataset is almost entirely the first kind. An oral history is
almost entirely the second: sixty years on she is not reporting state
transitions, she is recalling one fixed past with varying accuracy.

Two rules hold in both cases. Nothing is ever deleted — a superseded fact stays
readable, because she said it and that remains true about her. And a
contradiction becomes a *question* rather than a decision: it is a disputed
field, so it reaches the next call the way a missing `why` does. Which of two
tellings is right is hers to settle, not the database's.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Protocol

from pydantic import BaseModel, Field

from sampan.facts import Fact


class Disagreement(StrEnum):
    NONE = "none"
    STATE_CHANGE = "state_change"
    CONFLICTING_TESTIMONY = "conflicting_testimony"


class Judgement(BaseModel):
    """What the model concluded about one pair of facts."""

    kind: Disagreement
    reason: str = Field(default="", description="One line, for the family view")
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)


class ContradictionJudge(Protocol):
    """Seam for the model call, so routing is testable offline."""

    def judge(self, new: Fact, existing: Fact) -> Judgement: ...


def candidates(new: Fact, held: list[Fact]) -> list[Fact]:
    """Facts a new one could plausibly disagree with.

    Constrained to the same subject and predicate, following Zep, which limits
    edge deduplication to "edges existing between the same entity pairs". It
    prevents nonsense comparisons and keeps the number of model calls to
    something a post-call pipeline can afford.
    """
    return [
        f
        for f in held
        if f.is_current
        and f.fact_id != new.fact_id
        and f.subject_id == new.subject_id
        and f.predicate is new.predicate
    ]


def apply_state_change(old: Fact, new: Fact) -> Fact:
    """The world moved on. Close the old interval where the new one opens.

    This is Zep's rule as written, and it is right here: both facts were true,
    one after the other, and the archive should be able to say when each held.
    """
    if new.valid_from is None:
        return old
    return old.model_copy(update={"valid_to": new.valid_from})


def apply_conflicting_testimony(old: Fact, new: Fact) -> Fact:
    """She remembers it differently. Retire the assertion, not the fact.

    Valid time is deliberately untouched. The disagreement is about her
    account, so it belongs on the transaction timeline: the archive believed
    one thing until she said another.
    """
    return old.model_copy(
        update={
            "t_expired": datetime.now(UTC),
            "superseded_by": new.fact_id,
        }
    )


def reconcile(
    new_facts: list[Fact],
    held: list[Fact],
    judge: ContradictionJudge,
    on_verdict: Callable[[Fact, Fact, Judgement], None] | None = None,
) -> tuple[list[Fact], list[str]]:
    """Fold new facts into the archive, resolving disagreements.

    Returns every fact that changed — new and amended alike — together with a
    plain-language note for each disagreement found, so the next call can ask
    her about it instead of the archive quietly picking a side.

    `on_verdict` receives every disagreement acted on: the amended fact, the
    one that replaced it, and the judgement. Without it the two kinds of
    retirement are indistinguishable afterwards — a `valid_to` and a
    `t_expired` are both just fields, and which clock moved is the whole point.
    """
    updated: dict[str, Fact] = {}
    questions: list[str] = []
    current = list(held)

    for new in new_facts:
        for old in candidates(new, current):
            verdict = judge.judge(new, old)
            if verdict.kind is Disagreement.NONE:
                continue

            if verdict.kind is Disagreement.STATE_CHANGE:
                amended = apply_state_change(old, new)
            else:
                amended = apply_conflicting_testimony(old, new)
                questions.append(
                    verdict.reason
                    or f'She has said this two ways: "{old.statement}" '
                    f'and "{new.statement}".'
                )

            updated[old.fact_id] = amended
            current = [amended if f.fact_id == old.fact_id else f for f in current]
            if on_verdict is not None:
                on_verdict(amended, new, verdict)

    return [*new_facts, *updated.values()], questions


JUDGE_PROMPT = """\
An elderly woman is telling her life story across many conversations. Two
statements the archive holds about her appear to disagree. Decide which kind of
disagreement this is.

**state_change** — both are true, at different times. The world moved on: she
moved house, a shop opened and later closed, someone married. Nothing is wrong;
her life simply changed.

**conflicting_testimony** — they cannot both be true. Same event, two accounts.
She said the shop closed in sixty-nine and later said seventy; the shop closed
once and she has remembered it differently.

**none** — they do not actually disagree. One may be more specific than the
other, or about a different occasion entirely. Prefer this when unsure: an
archive that quietly retires something she said is worse than one holding two
compatible statements.

Held already:
  {old}
  her words: "{old_quote}"

Newly said:
  {new}
  her words: "{new_quote}"

If this is conflicting_testimony, write one plain sentence for her family
naming both versions, so someone can ask her about it. Never say she is wrong
or confused.
"""


class GeminiContradictionJudge:
    """Model-backed judgement, behind the protocol so routing stays testable."""

    def __init__(self, settings: Any) -> None:
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

    def judge(self, new: Fact, existing: Fact) -> Judgement:
        from google.genai import types

        response = self._client.models.generate_content(
            model=self._settings.archivist_model,
            contents=JUDGE_PROMPT.format(
                old=existing.render(),
                old_quote=existing.quote,
                new=new.render(),
                new_quote=new.quote,
            ),
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=Judgement,
                temperature=0.0,
            ),
        )
        parsed = response.parsed
        # An unreadable answer must not retire something she said.
        return parsed if parsed is not None else Judgement(kind=Disagreement.NONE)
