"""What the family sees.

Three projections of the same stories: a feed, a map, and a timeline generated
on demand for one narrator. The timeline is not stored — it is a sort, and
storing it would mean maintaining it.

Sorting is the interesting part. Her dates are ranges with a precision, and
many have only one end, so "chronological" needs deciding rather than assuming:
a story bounded only above by 1968 sorts before 1968, and an undated story
sorts last rather than being dropped.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from sampan.places import Place, split_tray

# Far enough in the past that anything undated sorts after everything dated,
# without an undated story quietly vanishing from her life.
_UNDATED = 9999


class StoryCard(BaseModel):
    """One story, as the family reads it."""

    story_id: str
    title: str
    domain: str
    pin_type: str
    narrative: str
    sense_detail: str
    when_said: str = Field(description="Her own words for the time")
    year_from: int | None = None
    year_to: int | None = None
    where_said: str = ""
    people: list[str] = Field(default_factory=list)
    status: str = "pinnable"
    missing_fields: list[str] = Field(default_factory=list)
    conversation_id: str = ""
    # Surfaced, not hidden. Two of the archive's most sensitive stories are
    # ones she and her son each chose to tell — burying them with no way to
    # unbury would be a worse record than marking them and treading carefully.
    sensitivity: str = "routine"


def _card(raw: dict[str, Any]) -> StoryCard:
    candidate = raw.get("candidate", {})
    when = candidate.get("when", {}) or {}
    where = candidate.get("where", {}) or {}
    return StoryCard(
        story_id=raw.get("story_id", ""),
        title=candidate.get("title", ""),
        domain=candidate.get("domain", ""),
        pin_type=candidate.get("pin_type", "timeline"),
        narrative=candidate.get("narrative", ""),
        sense_detail=candidate.get("sense_detail", ""),
        when_said=when.get("raw_phrase", ""),
        year_from=when.get("start_year"),
        year_to=when.get("end_year"),
        where_said=where.get("raw_name", ""),
        people=[p.get("surface_form", "") for p in candidate.get("who", []) or []],
        status=raw.get("status", "pinnable"),
        missing_fields=raw.get("missing_fields", []) or [],
        conversation_id=raw.get("conversation_id", ""),
        sensitivity=candidate.get("sensitivity", "routine"),
    )


def sort_key(card: StoryCard) -> tuple[int, int]:
    """Order a life whose dates are mostly ranges with one open end.

    A story known only as "before I married" has an upper bound and no lower
    one; it belongs just before that bound, not at the beginning of time.
    """
    if card.year_from is not None:
        return (card.year_from, card.year_to or card.year_from)
    if card.year_to is not None:
        # Bounded above only: sits immediately before the bound.
        return (card.year_to - 1, card.year_to)
    return (_UNDATED, _UNDATED)


def build_cards(
    raw_stories: list[dict[str, Any]], private_subjects: list[str] | None = None
) -> list[StoryCard]:
    """Story cards, minus anything she asked to keep off the family's view.

    Filtering happens here rather than at each caller, because a story that
    escapes into one view has escaped — and "I won't write that down" was a promise,
    not a preference.
    """
    cards = [_card(raw) for raw in raw_stories]
    if not private_subjects:
        return cards
    return [
        card
        for card in cards
        if not any(
            subject and (subject in card.title or subject in card.narrative)
            for subject in private_subjects
        )
    ]


def timeline(cards: list[StoryCard]) -> list[StoryCard]:
    """Her life in order. Generated on request, never stored."""
    return sorted(cards, key=sort_key)


def feed(cards: list[StoryCard]) -> list[StoryCard]:
    """Newest first — what arrived since the family last looked."""
    return sorted(cards, key=lambda c: c.conversation_id, reverse=True)


class MapPin(BaseModel):
    place: Place
    stories: list[StoryCard]


class MapView(BaseModel):
    pins: list[MapPin]
    unlocated: list[MapPin] = Field(
        default_factory=list,
        description="Places we could not put down. Shown, not hidden.",
    )

    @property
    def countries(self) -> set[str]:
        return {p.place.country for p in self.pins if p.place.country}


def build_map(cards: list[StoryCard], places: list[Place]) -> MapView:
    """Group stories under the places they happened."""
    by_name = {p.raw_name: p for p in places}
    grouped: dict[str, list[StoryCard]] = {}
    for card in cards:
        if not card.where_said:
            continue
        grouped.setdefault(card.where_said, []).append(card)

    pinned, unlocated = split_tray(
        [by_name.get(name) or Place(raw_name=name) for name in grouped]
    )
    return MapView(
        pins=[MapPin(place=p, stories=grouped[p.raw_name]) for p in pinned],
        unlocated=[MapPin(place=p, stories=grouped[p.raw_name]) for p in unlocated],
    )


class Stats(BaseModel):
    """The numbers worth showing a grandchild.

    Hours of her voice is the one that lands: it is the thing that cannot be
    recovered once she is gone.
    """

    stories: int
    years_spanned: int
    places: int
    people: int
    conversations: int


def stats(cards: list[StoryCard], entity_count: int, conversations: int) -> Stats:
    years = [y for c in cards for y in (c.year_from, c.year_to) if y is not None]
    return Stats(
        stories=len(cards),
        years_spanned=(max(years) - min(years)) if len(years) > 1 else 0,
        places=len({c.where_said for c in cards if c.where_said}),
        people=entity_count,
        conversations=conversations,
    )
