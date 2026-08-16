"""Entity resolution.

She says 「我姐姐」 in session 1, 「阿姐」 in session 3 and 「林秀珠」 in session 8,
and means one person. Getting that wrong shows up as a duplicated pin on the
family map and as an agent that asks about someone it has already been told is
dead.

Resolution is deliberately mostly deterministic. A model is consulted only when
the cheap signals leave genuine ambiguity, because a model asked to match every
mention will happily merge two different people.
"""

from __future__ import annotations

import uuid
from typing import Protocol

from pydantic import BaseModel

from sampan.models import Entity, EntityMention, EntityType, kin_role, normalise


class Resolution(BaseModel):
    """What happened to one mention."""

    mention: EntityMention
    entity_id: str
    created: bool
    # How the match was made, so the family-facing correction UI can show it
    # and so failures are debuggable.
    matched_by: str


class ResolutionResult(BaseModel):
    entities: list[Entity]
    resolutions: list[Resolution]

    @property
    def created(self) -> list[Entity]:
        new_ids = {r.entity_id for r in self.resolutions if r.created}
        return [e for e in self.entities if e.entity_id in new_ids]

    @property
    def needs_confirmation(self) -> list[Entity]:
        return [e for e in self.entities if e.provisional and not e.confirmed_by_family]


class Tiebreaker(Protocol):
    """Consulted only when several existing entities plausibly match.

    Returns an entity_id, or None to create a new entity.
    """

    def choose(
        self, mention: EntityMention, candidates: list[Entity]
    ) -> str | None: ...


class NeverMerges:
    """Default tiebreaker: when genuinely ambiguous, create a new provisional
    entity and let the family merge it.

    Splitting is recoverable — the family clicks merge. Wrongly merging two
    people silently corrupts the archive and nobody notices.
    """

    def choose(self, mention: EntityMention, candidates: list[Entity]) -> str | None:
        return None


def _candidates(mention: EntityMention, existing: list[Entity]) -> list[Entity]:
    return [e for e in existing if e.type == mention.type]


def _match_by_alias(mention: EntityMention, pool: list[Entity]) -> Entity | None:
    for entity in pool:
        if entity.knows(mention.surface_form):
            return entity
    return None


def _match_by_kin_role(mention: EntityMention, pool: list[Entity]) -> Entity | None:
    """Kin terms resolve against the family intake with high confidence.

    Only unique matches count: two sisters mean 「我姐姐」 is ambiguous and
    belongs in the tiebreaker.
    """
    if mention.type is not EntityType.PERSON:
        return None
    role = mention.role or kin_role(mention.surface_form)
    if role is None:
        return None
    matches = [e for e in pool if e.role == role]
    return matches[0] if len(matches) == 1 else None


def _match_by_containment(mention: EntityMention, pool: list[Entity]) -> Entity | None:
    """怡保 matches 怡保板底街. Only when exactly one candidate contains or is
    contained by the mention, and only for places."""
    if mention.type is not EntityType.PLACE:
        return None
    needle = normalise(mention.surface_form)
    if len(needle) < 2:
        return None
    matches = [
        e
        for e in pool
        for name in [e.canonical_name, *e.aliases]
        if needle in normalise(name) or normalise(name) in needle
    ]
    unique = {e.entity_id: e for e in matches}
    return next(iter(unique.values())) if len(unique) == 1 else None


def resolve_mentions(
    mentions: list[EntityMention],
    existing: list[Entity],
    *,
    conversation_id: str | None = None,
    tiebreaker: Tiebreaker | None = None,
) -> ResolutionResult:
    """Fold this conversation's mentions into the family's entity graph."""
    tiebreaker = tiebreaker or NeverMerges()
    known: list[Entity] = [e.model_copy(deep=True) for e in existing]
    by_id = {e.entity_id: e for e in known}
    resolutions: list[Resolution] = []

    for mention in mentions:
        pool = _candidates(mention, known)
        matched: Entity | None = None
        how = ""

        for strategy, label in (
            (_match_by_alias, "alias"),
            (_match_by_kin_role, "kin_role"),
            (_match_by_containment, "containment"),
        ):
            matched = strategy(mention, pool)
            if matched is not None:
                how = label
                break

        if matched is None and pool:
            chosen_id = tiebreaker.choose(mention, pool)
            if chosen_id is not None and chosen_id in by_id:
                matched, how = by_id[chosen_id], "tiebreaker"

        if matched is None:
            entity = Entity(
                entity_id=f"ent_{uuid.uuid4().hex[:12]}",
                type=mention.type,
                canonical_name=mention.surface_form,
                aliases=[],
                role=mention.role or kin_role(mention.surface_form),
                detail=mention.detail,
                mention_count=1,
                first_mentioned_in=conversation_id,
                provisional=True,
            )
            known.append(entity)
            by_id[entity.entity_id] = entity
            resolutions.append(
                Resolution(
                    mention=mention,
                    entity_id=entity.entity_id,
                    created=True,
                    matched_by="new",
                )
            )
            continue

        matched.mention_count += 1
        if not matched.knows(mention.surface_form):
            matched.aliases.append(mention.surface_form)
        if mention.detail and mention.detail not in matched.detail:
            matched.detail = (
                f"{matched.detail} {mention.detail}".strip()
                if matched.detail
                else mention.detail
            )
        resolutions.append(
            Resolution(
                mention=mention,
                entity_id=matched.entity_id,
                created=False,
                matched_by=how,
            )
        )

    return ResolutionResult(entities=known, resolutions=resolutions)
