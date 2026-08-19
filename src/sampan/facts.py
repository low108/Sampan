"""Facts — the edges of the memory graph.

A story is the narrative unit: the thing with a sensory detail that becomes a
letter. A fact is the *queryable* projection of the same material — "her father
ran a coffee shop at Jalan Bandar, from 1958 until it closed". Both reference
the same episode and neither replaces the other; forcing a story into triples
destroys the thing this product exists for.

Facts carry two time axes, after Zep (arXiv 2501.13956 §2.2.3):

    valid time (T)   when it was true in her life
    transaction time (T')  when the archive came to believe it

The departure from that paper is that valid time here is a `When`, not a
timestamp. She says "before I married". A datetime forces a date she never gave;
`When` keeps her phrase beside the year it resolved to. Published agent-memory
systems store valid-time edges but not *uncertain* valid-time intervals, and
sixty-year-old recollection is nothing but uncertain intervals.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from sampan.models import When


class Predicate(StrEnum):
    """The relations a fact may assert.

    Closed on purpose. The model chooses from this list and never invents a
    label, because these are join keys: the same relation named two ways is two
    relations, and no string matching reconciles them afterwards. Zep makes the
    same argument about its own writes, preferring predefined Cypher to
    LLM-generated queries "to ensure consistent schema formats and reduce the
    potential for hallucinations".

    Chosen for an oral history of one family, not for generality.
    """

    LIVED_AT = "lived_at"
    WORKED_AT = "worked_at"
    OWNED = "owned"
    MADE = "made"
    ATE = "ate"
    MARRIED_TO = "married_to"
    PARENT_OF = "parent_of"
    SIBLING_OF = "sibling_of"
    NEIGHBOUR_OF = "neighbour_of"
    ESTRANGED_FROM = "estranged_from"
    BORN_AT = "born_at"
    DIED = "died"
    TRAVELLED_TO = "travelled_to"


class Fact(BaseModel):
    """One assertion she made, with both timelines and the sentence behind it."""

    fact_id: str
    subject_id: str = Field(description="entity_id of the subject")
    predicate: Predicate
    object_id: str | None = Field(
        default=None, description="entity_id when the object is an entity"
    )
    object_literal: str = Field(
        default="", description="the object when it is not an entity"
    )
    statement: str = Field(
        description="The fact as a sentence. This is what retrieval searches."
    )

    # --- valid time (T): when it was true in her life ---------------------
    valid_from: When | None = None
    valid_to: When | None = None

    # --- transaction time (T'): when the archive believed it --------------
    t_created: datetime = Field(default_factory=lambda: datetime.now(UTC))
    t_expired: datetime | None = Field(
        default=None,
        description="Set when a later telling superseded this one. Never deleted.",
    )
    superseded_by: str | None = None

    # --- provenance -------------------------------------------------------
    episode_id: str = Field(description="conversation_id this came from")
    quote: str = Field(
        description="Her sentence. Required; verified against the transcript."
    )
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)

    @property
    def is_current(self) -> bool:
        """Whether this is what the archive currently believes.

        Retrieval, the map, the timeline and the letters all read only current
        facts. Superseded ones stay readable but stop being asserted.
        """
        return self.t_expired is None

    @property
    def year_span(self) -> tuple[int | None, int | None]:
        start = self.valid_from.start_year if self.valid_from else None
        end = (
            self.valid_to.end_year or self.valid_to.start_year
            if self.valid_to
            else None
        )
        return start, end

    def render(self) -> str:
        """One line for a tool response or a letter.

        Leads with the years when they are known, because a fact without a time
        is a fact the next call should ask about.
        """
        start, end = self.year_span
        if start and end and start != end:
            when = f"{start}–{end}"
        elif start and end:
            when = str(start)
        elif start:
            # Open-ended: it began then and nothing has ended it.
            when = f"from {start}"
        elif end:
            # An end with no beginning, which is what a state change leaves
            # behind. Rendered bare it reads as the year the thing *happened* --
            # "she grew up on the estate in 1968" -- and that reading reached a
            # chapter summary before this was fixed.
            when = f"until {end}"
        elif self.valid_from and self.valid_from.raw_phrase:
            when = self.valid_from.raw_phrase
        else:
            when = "year not yet told"
        return f"{when} · {self.statement}"


def is_quoted(quote: str, transcripts: str) -> bool:
    """Whether the quote is something she actually said.

    The fourth place this check has been needed. Asked for a supporting
    sentence, a model will return its own reasoning in the shape of one --
    "Identified as being in the vicinity of Sungai Siput" -- and a field that
    must be non-empty will be made non-empty. A claim about a source can be
    tested against the source, so it is.

    Comparison ignores case and whitespace because the model re-punctuates
    freely, and very short fragments are rejected because almost any few words
    can be found somewhere in a long transcript.
    """
    claim = " ".join(quote.strip().lower().split())
    if len(claim) < 20:
        return False
    haystack = " ".join(transcripts.lower().split())
    if claim in haystack:
        return True
    head = claim[: max(20, len(claim) // 2)]
    return head in haystack
