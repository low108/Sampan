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


class EntityType(StrEnum):
    """One collection, discriminated by type.

    Entities are first-class documents rather than name-keyed maps on stories,
    because the map, the family tree and the filters all need to query them and
    dedupe 怡保 / Ipoh / Ipoh town.
    """

    PERSON = "person"
    PLACE = "place"
    OBJECT = "object"
    FOOD = "food"


class EntityMention(BaseModel):
    """Someone or something referred to in a conversation, before resolution."""

    surface_form: str = Field(description="Exactly as she said it, e.g. 我姐姐")
    type: EntityType
    role: str | None = Field(
        default=None, description="For people: father, sister, neighbour, husband…"
    )
    detail: str = Field(
        default="", description="Anything new she said about them or it"
    )


class Entity(BaseModel):
    """A person, place, object or food, accumulated across conversations."""

    entity_id: str
    type: EntityType
    canonical_name: str
    aliases: list[str] = Field(default_factory=list)
    role: str | None = None
    detail: str = ""
    mention_count: int = 0
    first_mentioned_in: str | None = None
    # Provisional entities are shown to the family to confirm or merge. The
    # correction path is also the feedback-capture path.
    confirmed_by_family: bool = False
    provisional: bool = True

    def knows(self, surface_form: str) -> bool:
        return normalise(surface_form) in {
            normalise(name) for name in [self.canonical_name, *self.aliases]
        }


# Possessives and honorific padding carry no identity information.
_STRIP_PREFIXES = ("我的", "我", "他的", "她的", "那个", "那间", "那条")
_STRIP_SUFFIXES = ("的",)


def normalise(surface_form: str) -> str:
    """Reduce a surface form to something comparable.

    她说「我姐姐」, 「姐姐」 and 「阿姐」 across three sessions and means one
    person; the first two differ only by a possessive.
    """
    text = surface_form.strip().replace(" ", "")
    changed = True
    while changed:
        changed = False
        for prefix in _STRIP_PREFIXES:
            if text.startswith(prefix) and len(text) > len(prefix):
                text, changed = text[len(prefix) :], True
        for suffix in _STRIP_SUFFIXES:
            if text.endswith(suffix) and len(text) > len(suffix):
                text, changed = text[: -len(suffix)], True
    return text.lower()


# Kin terms are near-unambiguous in Chinese and are the highest-confidence
# resolution signal available, especially against a family intake.
KIN_ROLES: dict[str, str] = {
    "妈妈": "mother",
    "母亲": "mother",
    "阿妈": "mother",
    "爸爸": "father",
    "父亲": "father",
    "阿爸": "father",
    "姐姐": "elder_sister",
    "阿姐": "elder_sister",
    "妹妹": "younger_sister",
    "哥哥": "elder_brother",
    "弟弟": "younger_brother",
    "先生": "husband",
    "老公": "husband",
    "太太": "wife",
    "儿子": "son",
    "女儿": "daughter",
    "孙女": "granddaughter",
    "孙子": "grandson",
    "阿公": "grandfather",
    "阿嬷": "grandmother",
}


def kin_role(surface_form: str) -> str | None:
    """Map a kin term to a role, or None if it isn't one."""
    return KIN_ROLES.get(normalise(surface_form))


class ThreadStatus(StrEnum):
    OPEN = "open"
    CLOSED = "closed"


class ThreadAction(StrEnum):
    OPENED = "opened"
    ADVANCED = "advanced"
    CLOSED = "closed"


class ClosureReason(StrEnum):
    """Why the conversation ended.

    The distinction that matters is INTERRUPTED versus FATIGUE. If the doorbell
    went, she was mid-story and wants to come back to it. If she was tired, the
    story is finished for now and reopening it reads as nagging.
    """

    NATURAL = "natural"
    FATIGUE = "fatigue"
    INTERRUPTED = "interrupted"
    REFUSED = "refused"
    UNKNOWN = "unknown"


class Closure(BaseModel):
    """How this conversation ended, and on what."""

    reason: ClosureReason
    evidence: str = Field(
        default="", description="The line in the transcript that shows it"
    )
    active_topic: str = Field(
        default="", description="What she was talking about when it ended"
    )


class ThreadUpdate(BaseModel):
    """One thread's movement in a single conversation."""

    topic: str = Field(description="Short label, e.g. 爸爸的咖啡店")
    action: ThreadAction
    left_off_at: str = Field(
        default="",
        description="What she had not told yet. Becomes the next opener.",
    )


class Thread(BaseModel):
    """An unfinished story, carried between sessions.

    The highest-value thing the agent can open a call with, and the cheapest
    memory feature to build: 「上次讲到一半,隔壁的来按门铃」.
    """

    thread_id: str
    topic: str
    status: ThreadStatus = ThreadStatus.OPEN
    # Set only when the conversation was cut short from outside, never when she
    # simply tired. Drives whether the next opener reopens this thread.
    interrupted: bool = False
    left_off_at: str = ""
    opened_in: str | None = None
    last_touched: str | None = None
    touch_count: int = 0


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
