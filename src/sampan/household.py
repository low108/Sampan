"""The family, rather than one narrator.

Everything below `Repository` is scoped to one person because that is how
memory works — the agent remembers *her*. But the map is the opposite: it is
the one place where a family sees itself as a family, and Jalan Bandar has to hold
her father's coffee shop and her son's creaking staircase at the same time.

So this module aggregates across narrators, and nothing else does.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from sampan.family import StoryCard, build_cards
from sampan.places import Place
from sampan.repository import Repository

MEMBERS = "members"


class Member(BaseModel):
    """Someone whose stories are in the archive, or who reads it."""

    narrator_id: str
    display_name: str
    relation: str = Field(default="", description="Relative to the household")
    born: int | None = None
    records: bool = Field(
        default=True, description="False for family who only read and ask"
    )
    story_count: int = 0
    session_count: int = 0


class Pin(BaseModel):
    """One story on the map, in the shape `<sampan-map>` expects."""

    id: str
    title: str
    lat: float
    lng: float
    precision: str
    linked: bool = False
    year: int | None = None
    # Not consumed by the map component; carried for the story card.
    narrator_id: str = ""
    narrator_name: str = ""


def list_members(repository: Repository) -> list[Member]:
    """Everyone in the household.

    Kept as its own collection rather than inferred from who has stories, so a
    grandchild who has never recorded still appears — she is a member of the
    family, not a row in a dataset.
    """
    raw = repository._store.list(MEMBERS)  # noqa: SLF001
    members = [Member.model_validate(r) for r in raw]
    for member in members:
        member.story_count = len(repository.load_stories(member.narrator_id))
        member.session_count = repository.load_memory(member.narrator_id).session_count
    return sorted(members, key=lambda m: m.born or 9999)


def save_member(repository: Repository, member: Member) -> None:
    repository._store.put(  # noqa: SLF001
        MEMBERS, member.narrator_id, member.model_dump(mode="json")
    )


def cards_for(repository: Repository, narrator_id: str) -> list[StoryCard]:
    """Her stories as the family may see them — never the private ones."""
    return build_cards(
        repository.load_stories(narrator_id),
        repository.private_subjects(narrator_id),
    )


def to_pins(
    cards: list[StoryCard],
    places: list[Place],
    *,
    narrator_id: str = "",
    narrator_name: str = "",
) -> list[Pin]:
    """Turn stories into map pins.

    One pin per *story*, not per place: the component clusters co-located pins
    itself, and Jalan Bandar holding four stories should read as four things that
    happened there rather than one dot with a number.
    """
    by_name = {p.raw_name: p for p in places}
    pins: list[Pin] = []
    for card in cards:
        place = by_name.get(card.where_said)
        if place is None or not place.locatable:
            continue
        pins.append(
            Pin(
                id=card.story_id,
                title=card.title,
                lat=place.lat or 0.0,
                lng=place.lng or 0.0,
                precision=place.precision.value,
                linked=bool(place.linked_from),
                year=card.year_from or card.year_to,
                narrator_id=narrator_id,
                narrator_name=narrator_name,
            )
        )
    return pins


def unplaced(cards: list[StoryCard], places: list[Place]) -> list[StoryCard]:
    """Stories that cannot go on the map.

    Returned, never hidden: two of Ah Khim's best say only "home", and a map
    that silently drops them is a worse record of her life than one that admits
    it does not know where she lived.
    """
    placed = {p.raw_name for p in places if p.locatable}
    return [c for c in cards if c.where_said not in placed]
