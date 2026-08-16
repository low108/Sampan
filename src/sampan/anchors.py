"""Anchor events, and resolving relative time against them.

Elders speak in relative time far more often than in years: 结婚以前,
店关了以后, 大水那年. Storing only her phrase makes a timeline unsortable;
storing only a guessed year loses how she actually said it. So both are kept,
and anchors are what turn one into the other.

Once 结婚 is known to be 1968, every 结婚以前 in the archive acquires an upper
bound — including, eventually, ones recorded before the anchor was known.
Retroactive re-resolution is deferred (PRD P2); this module resolves forward.
"""

from __future__ import annotations

from sampan.models import Anchor, AnchorCandidate, Precision, When

# Direction markers, longest first so 之前 is not shadowed by 前.
_BEFORE = ("以前", "之前", "前", "还没", "未")
_AFTER = ("以后", "之后", "后", "过后")
_SAME = ("那年", "当时", "那时", "那一年")


def direction(phrase: str) -> str | None:
    """Which side of the anchor she means. None when the phrase gives no clue."""
    text = phrase.strip()
    for marker in _SAME:
        if marker in text:
            return "same"
    for marker in _AFTER:
        if marker in text:
            return "after"
    for marker in _BEFORE:
        if marker in text:
            return "before"
    return None


def fold_anchors(
    existing: list[Anchor],
    candidates: list[AnchorCandidate],
    *,
    conversation_id: str,
) -> list[Anchor]:
    """Merge newly reported anchors into the accumulated set.

    A repeated anchor corroborates rather than overwrites. Disagreement is kept
    by preferring the more confident year and counting the corroboration, so a
    single confused mention cannot move a well-established date.
    """
    anchors = {a.anchor_id: a.model_copy(deep=True) for a in existing}

    for candidate in candidates:
        known = anchors.get(candidate.anchor_id)
        if known is None:
            anchors[candidate.anchor_id] = Anchor(
                anchor_id=candidate.anchor_id,
                label=candidate.label,
                year=candidate.year,
                confidence=candidate.confidence,
                first_seen_in=conversation_id,
            )
            continue

        known.corroborations += 1
        if candidate.year == known.year:
            # Agreement across sessions is itself evidence.
            known.confidence = min(1.0, known.confidence + 0.1)
        elif candidate.confidence > known.confidence:
            known.year = candidate.year
            known.confidence = candidate.confidence

    return list(anchors.values())


def apply_anchors(when: When, anchors: list[Anchor]) -> When:
    """Give a relative phrase a year range, without discarding her words.

    Leaves an already-resolved time alone: the model often infers a year
    directly from the transcript, and that is better evidence than an anchor
    offset.
    """
    if when.start_year is not None or when.end_year is not None:
        return when
    if when.anchor_ref is None:
        return when

    anchor = next((a for a in anchors if a.anchor_id == when.anchor_ref), None)
    if anchor is None:
        return when

    side = direction(when.raw_phrase)
    if side is None:
        return when

    resolved = when.model_copy(deep=True)
    if side == "before":
        # An upper bound only. How long before is unknown, and inventing a
        # lower bound would put a false start date on the timeline.
        resolved.end_year = anchor.year
    elif side == "after":
        resolved.start_year = anchor.year
    else:
        resolved.start_year = resolved.end_year = anchor.year

    resolved.precision = Precision.RELATIVE
    # Never more certain than the anchor it was derived from.
    resolved.confidence = min(when.confidence, anchor.confidence)
    return resolved


def resolve_all(whens: list[When], anchors: list[Anchor]) -> list[When]:
    return [apply_anchors(w, anchors) for w in whens]
