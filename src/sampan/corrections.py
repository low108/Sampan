"""What the family sends in: questions, and fixes.

Both are feedback capture, and the second is the more interesting one. The
agent learns from her silently, but it cannot learn that "my sister" is
called Lim Siew Choo unless someone tells it — and the person who knows is
her son, reading the archive at his desk. A correction is therefore not an
edit to one story; it is a fact entering the graph, and later stories get
it right because of it.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from sampan.models import Entity, normalise
from sampan.repository import Repository


class CorrectionKind(StrEnum):
    ENTITY_NAME = "entity_name"
    ENTITY_DETAIL = "entity_detail"
    PLACE = "place"
    MERGE = "merge"


class Correction(BaseModel):
    kind: CorrectionKind
    target: str = Field(description="Entity id, or the raw place name")
    value: str = Field(default="", description="The corrected name or detail")
    merge_into: str | None = Field(
        default=None, description="For merge: the entity that survives"
    )
    by: str = Field(default="", description="Which family member")


class CorrectionResult(BaseModel):
    applied: bool
    entity_id: str | None = None
    reason: str = ""


def apply_correction(
    repository: Repository, narrator_id: str, correction: Correction
) -> CorrectionResult:
    """Fold a family correction into the entity graph.

    Confirming an entity is as important as renaming one: a provisional entity
    that a human has looked at should stop being offered for confirmation, and
    should outrank a fresh guess in future resolution.
    """
    entities = repository.load_entities(narrator_id)
    by_id = {e.entity_id: e for e in entities}

    if correction.kind is CorrectionKind.MERGE:
        return _merge(repository, narrator_id, entities, by_id, correction)

    if correction.kind is CorrectionKind.PLACE:
        repository._store.put(  # noqa: SLF001 - places cache is repository-owned
            "_places",
            correction.target,
            {
                "raw_name": correction.target,
                "display_name": correction.value,
                "precision": "exact",
                "confidence": 1.0,
                "note": f"confirmed by family ({correction.by})"
                if correction.by
                else "confirmed by family",
            },
        )
        return CorrectionResult(applied=True)

    target = by_id.get(correction.target)
    if target is None:
        return CorrectionResult(applied=False, reason="no such entity")

    if correction.kind is CorrectionKind.ENTITY_NAME:
        # The name she used is kept as an alias. Her son may rename the entity
        # to Lim Siew Choo, but she will go on saying "my sister" and the archive
        # keep understanding her.
        previous = target.canonical_name
        if previous and previous not in target.aliases:
            target.aliases.append(previous)
        target.canonical_name = correction.value
    else:
        target.detail = correction.value

    target.confirmed_by_family = True
    target.provisional = False
    repository.save_entities(narrator_id, [target])
    return CorrectionResult(applied=True, entity_id=target.entity_id)


def _merge(
    repository: Repository,
    narrator_id: str,
    entities: list[Entity],
    by_id: dict[str, Entity],
    correction: Correction,
) -> CorrectionResult:
    """Fold one entity into another.

    The resolver deliberately splits rather than guesses, so merging is the
    family's half of that bargain and has to actually work.
    """
    duplicate = by_id.get(correction.target)
    survivor = by_id.get(correction.merge_into or "")
    if duplicate is None or survivor is None:
        return CorrectionResult(applied=False, reason="unknown entity")
    if duplicate.entity_id == survivor.entity_id:
        return CorrectionResult(applied=False, reason="cannot merge into itself")

    for name in [duplicate.canonical_name, *duplicate.aliases]:
        if name and not survivor.knows(name):
            survivor.aliases.append(name)
    if duplicate.detail and duplicate.detail not in survivor.detail:
        survivor.detail = f"{survivor.detail} {duplicate.detail}".strip()
    survivor.mention_count += duplicate.mention_count
    survivor.confirmed_by_family = True
    survivor.provisional = False

    duplicate.merged_into = survivor.entity_id
    repository.save_entities(narrator_id, [survivor, duplicate])
    return CorrectionResult(applied=True, entity_id=survivor.entity_id)


def needs_confirmation(entities: list[Entity]) -> list[Entity]:
    """Provisional entities the family has not looked at yet.

    Shown as a short list rather than a queue: a hundred pending items is a
    chore nobody does, and the point is to make correction feel like reading.
    """
    return [
        e
        for e in entities
        if e.provisional
        and not e.confirmed_by_family
        and getattr(e, "merged_into", None) is None
    ]


def duplicate_candidates(entities: list[Entity]) -> list[tuple[Entity, Entity]]:
    """Pairs that look like the same person, for the family to confirm.

    Surfaced rather than merged automatically — the resolver's whole posture is
    that a wrong merge is unrecoverable and a wrong split is one click.
    """
    live = [e for e in entities if getattr(e, "merged_into", None) is None]
    pairs: list[tuple[Entity, Entity]] = []
    for index, first in enumerate(live):
        for second in live[index + 1 :]:
            if first.type is not second.type:
                continue
            if (
                first.role
                and first.role == second.role
                or normalise(first.canonical_name) in normalise(second.canonical_name)
                or normalise(second.canonical_name) in normalise(first.canonical_name)
            ):
                pairs.append((first, second))
    return pairs


def timestamp() -> str:
    return datetime.now(UTC).isoformat()
