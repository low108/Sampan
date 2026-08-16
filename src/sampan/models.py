"""Domain model for extracted life stories.

Vocabulary follows docs/spec-p0.md. The shapes here are what the Archivist
returns and what the map, the timeline and the letters are all projections of.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class Domain(StrEnum):
    """Topic domains. A categorisation structure, never a script — the agent
    does not announce these or work through them."""

    ROOT = "root"
    JOURNEY = "journey"
    TASTE = "taste"
    PEOPLE = "people"
    EVENTS = "events"
    TRADITION = "tradition"
    WORK = "work"
    HOME = "home"
    LOVE = "love"
    HARDSHIP = "hardship"
    OBJECTS = "objects"
    PLAY = "play"
    SKILLS = "skills"
    WISDOM = "wisdom"


class PinType(StrEnum):
    """Four projections over one schema."""

    PLACE = "place"
    PERSON = "person"
    OBJECT = "object"
    TIMELINE = "timeline"


class Precision(StrEnum):
    """How firmly a date is known. Elders speak relatively far more often than
    they speak in years."""

    EXACT = "exact"
    YEAR = "year"
    DECADE = "decade"
    ERA = "era"
    RELATIVE = "relative"


class Sensitivity(StrEnum):
    ROUTINE = "routine"
    SENSITIVE = "sensitive"


class StoryStatus(StrEnum):
    PINNABLE = "pinnable"
    FRAGMENT = "fragment"


class When(BaseModel):
    """A time, stored twice: as she said it, and as we resolved it."""

    raw_phrase: str = Field(description="Her own words, e.g. 结婚以前")
    start_year: int | None = None
    end_year: int | None = None
    precision: Precision
    anchor_ref: str | None = Field(
        default=None,
        description="Anchor event this was resolved against, e.g. anchor_marriage",
    )
    confidence: float = Field(ge=0.0, le=1.0)

    @property
    def is_present(self) -> bool:
        """A year or an era both count. 'During the Emergency' is a when."""
        return bool(self.raw_phrase.strip())


class Where(BaseModel):
    raw_name: str = Field(description="The place as she named it")
    aliases: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)

    @property
    def is_present(self) -> bool:
        return bool(self.raw_name.strip())


class PersonMention(BaseModel):
    surface_form: str = Field(description="As she referred to them, e.g. 我姐姐")
    role: str | None = Field(default=None, description="father, sister, neighbour…")
    confidence: float = Field(ge=0.0, le=1.0)


class Quote(BaseModel):
    text: str
    turn_id: int | None = None


class Emotion(BaseModel):
    valence: float = Field(ge=-1.0, le=1.0)
    labels: list[str] = Field(default_factory=list)


class Completeness(BaseModel):
    """The pinnability rubric, computed rather than guessed at by the model."""

    where: bool
    when: bool
    who: bool
    what: bool
    sense: bool
    why: bool

    @property
    def score(self) -> int:
        return sum([self.where, self.when, self.who, self.what, self.sense, self.why])

    @property
    def missing_fields(self) -> list[str]:
        """Drives a later session's clarifying question. A fragment missing
        `when` becomes 那间咖啡店 — 是你结婚以前还是以后?"""
        return [
            name
            for name, present in (
                ("where", self.where),
                ("when", self.when),
                ("who", self.who),
                ("what", self.what),
                ("sense", self.sense),
                ("why", self.why),
            )
            if not present
        ]


class StoryCandidate(BaseModel):
    """One story as the model heard it, before scoring."""

    title: str
    domain: Domain
    narrative: str = Field(description="80-150 words, first person, her words")
    verbatim_quotes: list[Quote] = Field(default_factory=list)
    when: When
    where: Where
    who: list[PersonMention] = Field(default_factory=list)
    what: str = Field(default="", description="An event with a beginning and an end")
    sense_detail: str = Field(
        default="",
        description=(
            "One concrete sensory detail. The difference between a fact and a "
            "story: not 我们很穷 but 我们吃白饭配酱油,妈妈说她已经吃过了"
        ),
    )
    why_it_matters: str = ""
    emotion: Emotion
    pin_type: PinType
    sensitivity: Sensitivity = Sensitivity.ROUTINE


class ScoredStory(BaseModel):
    """A candidate with the rubric applied. This is what gets stored."""

    candidate: StoryCandidate
    completeness: Completeness
    status: StoryStatus
    missing_fields: list[str]

    @property
    def score(self) -> int:
        return self.completeness.score


# WHERE and WHEN are mandatory; four of six fields pins.
PIN_THRESHOLD = 4


def assess(candidate: StoryCandidate) -> ScoredStory:
    """Apply the pinnability rubric.

    Deliberately computed here rather than asked of the model: the threshold is
    a product decision, and a model that scores its own output will drift.
    """
    completeness = Completeness(
        where=candidate.where.is_present,
        when=candidate.when.is_present,
        who=bool(candidate.who),
        what=bool(candidate.what.strip()),
        sense=bool(candidate.sense_detail.strip()),
        why=bool(candidate.why_it_matters.strip()),
    )
    pinnable = (
        completeness.where and completeness.when and completeness.score >= PIN_THRESHOLD
    )
    return ScoredStory(
        candidate=candidate,
        completeness=completeness,
        status=StoryStatus.PINNABLE if pinnable else StoryStatus.FRAGMENT,
        missing_fields=completeness.missing_fields,
    )
