"""What one call did to the graph.

The counterpart to `SearchTrace`. That one answers "why did this query return
these facts"; this one answers "what did this conversation change", which for a
memory product is the more interesting question — a retrieval demo shows a
graph being read, and this shows it growing and correcting itself.

Three kinds of change, and they are not variations on a theme:

    create   a node the archive had never seen, or an edge it did not hold
    match    a mention resolved onto a node that already existed, and how
    retire   an edge the archive stops asserting, in one of two ways

The last is the one worth drawing. A state change sets `valid_to` and keeps
both edges current: the shop opened and later closed, and nothing is wrong. A
conflicting testimony sets `t_expired` and `superseded_by` and leaves valid
time exactly as she said it: she told it two ways, and the archive stops
asserting the earlier telling without ever recording that she was wrong. Same
word — "update" — two different clocks, and collapsing them is the bug the
whole bi-temporal design exists to prevent.

Everything here is assembled from values `finish_call` already has. Nothing is
recomputed, and nothing calls a model.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from sampan.contradiction import Disagreement
from sampan.entities import Resolution
from sampan.fact_extraction import Refusal
from sampan.facts import Fact


class NodeChange(BaseModel):
    """One entity the call touched: a node in the drawing."""

    entity_id: str
    name: str = ""
    # How she referred to it, which is rarely the canonical name. "my father"
    # resolving onto Lim Ah Hock is the whole point of resolution.
    surface_form: str = ""
    created: bool = False
    # alias | kin_role | containment | tiebreaker | new
    matched_by: str = ""


class EdgeChange(BaseModel):
    """One fact the call added: an edge in the drawing."""

    fact_id: str
    subject_id: str
    object_id: str = ""
    object_literal: str = ""
    predicate: str = ""
    statement: str = ""
    # The sentence that justifies it. An edge without one is refused, so every
    # edge drawn can be traced back to something she said.
    quote: str = ""


class Retirement(BaseModel):
    """One edge the archive stopped asserting, and which clock moved."""

    fact_id: str
    statement: str
    # state_change | conflicting_testimony
    kind: str
    superseded_by: str = ""
    # Set for a state change: when it stopped being true in her life.
    valid_to: str = ""
    # Set for conflicting testimony: when the archive stopped believing it.
    # Her valid time is untouched, because she is not being corrected.
    expired_at: str = ""
    reason: str = ""

    @property
    def clock(self) -> str:
        return "valid time" if self.kind == "state_change" else "transaction time"


class GraphChange(BaseModel):
    """The whole write side of one call, ready to draw."""

    conversation_id: str = ""
    nodes: list[NodeChange] = Field(default_factory=list)
    edges: list[EdgeChange] = Field(default_factory=list)
    retired: list[Retirement] = Field(default_factory=list)
    # Proposed edges the archive declined, with the rule that declined them.
    refused: list[Refusal] = Field(default_factory=list)

    @property
    def created_nodes(self) -> list[NodeChange]:
        return [n for n in self.nodes if n.created]


def describe_nodes(
    resolutions: list[Resolution], names: dict[str, str]
) -> list[NodeChange]:
    """Turn entity resolution into nodes, keeping how each one was reached."""
    return [
        NodeChange(
            entity_id=r.entity_id,
            name=names.get(r.entity_id, ""),
            surface_form=r.mention.surface_form,
            created=r.created,
            matched_by=r.matched_by,
        )
        for r in resolutions
    ]


def describe_edges(facts: list[Fact]) -> list[EdgeChange]:
    return [
        EdgeChange(
            fact_id=f.fact_id,
            subject_id=f.subject_id,
            object_id=f.object_id or "",
            object_literal=f.object_literal,
            predicate=f.predicate.value,
            statement=f.statement,
            quote=f.quote,
        )
        for f in facts
    ]


def describe_retirement(
    old: Fact, amended: Fact, kind: Disagreement, reason: str
) -> Retirement:
    """One verdict, recorded so the two clocks stay distinguishable.

    Reads `amended` rather than inferring from `kind`, so a mismatch between
    the verdict and what was actually written shows up in the record instead
    of being smoothed over by it.
    """
    return Retirement(
        fact_id=old.fact_id,
        statement=old.statement,
        kind=kind.value,
        superseded_by=amended.superseded_by or "",
        valid_to=amended.valid_to.raw_phrase if amended.valid_to else "",
        expired_at=amended.t_expired.isoformat() if amended.t_expired else "",
        reason=reason,
    )
