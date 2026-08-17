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

    raw_phrase: str = Field(description='Her own words, e.g. "before I married"')
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
    surface_form: str = Field(description='As she referred to them, e.g. "my sister"')
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
    dedupe Ipoh / Ipoh town / Jalan Bandar, Ipoh.
    """

    PERSON = "person"
    PLACE = "place"
    OBJECT = "object"
    FOOD = "food"


class EntityMention(BaseModel):
    """Someone or something referred to in a conversation, before resolution."""

    surface_form: str = Field(description='Exactly as she said it, e.g. "my sister"')
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
    # Set when the family merges this into another entity. Kept rather than
    # deleted so old stories keep resolving and the merge stays reversible.
    merged_into: str | None = None

    def knows(self, surface_form: str) -> bool:
        return normalise(surface_form) in {
            normalise(name) for name in [self.canonical_name, *self.aliases]
        }


# Possessives and padding carry no identity information.
_STRIP_PREFIXES = ("my ", "our ", "his ", "her ", "the ", "that ", "this ")
_STRIP_SUFFIXES = ("'s",)


def normalise(surface_form: str) -> str:
    """Reduce a surface form to something comparable.

    She says "my sister", "my elder sister" and "Ah Chee" across three sessions
    and means one person; the first two differ only by a possessive.
    """
    text = " ".join(surface_form.strip().lower().split())
    changed = True
    while changed:
        changed = False
        for prefix in _STRIP_PREFIXES:
            if text.startswith(prefix) and len(text) > len(prefix):
                text, changed = text[len(prefix) :], True
        for suffix in _STRIP_SUFFIXES:
            if text.endswith(suffix) and len(text) > len(suffix):
                text, changed = text[: -len(suffix)], True
    return text.strip()


# Kin terms are the highest-confidence resolution signal available, especially
# against a family intake. English distinguishes fewer relations than Chinese
# does — "sister" carries no seniority — so the roles here are deliberately
# coarse, and seniority is left to the family intake to state.
KIN_ROLES: dict[str, str] = {
    "mother": "mother",
    "mom": "mother",
    "mum": "mother",
    "mummy": "mother",
    "ma": "mother",
    "father": "father",
    "dad": "father",
    "daddy": "father",
    "pa": "father",
    "sister": "sister",
    "elder sister": "sister",
    "big sister": "sister",
    "younger sister": "younger_sister",
    "little sister": "younger_sister",
    "brother": "brother",
    "elder brother": "brother",
    "big brother": "brother",
    "younger brother": "younger_brother",
    "husband": "husband",
    "wife": "wife",
    "son": "son",
    "daughter": "daughter",
    "granddaughter": "granddaughter",
    "grandson": "grandson",
    "grandfather": "grandfather",
    "grandmother": "grandmother",
    # Malaysian English keeps these, and she will use them far more often than
    # the English words.
    "ah gong": "grandfather",
    "ah ma": "grandmother",
    "ah pa": "father",
    "ah mah": "grandmother",
}


def kin_role(surface_form: str) -> str | None:
    """Map a kin term to a role, or None if it isn't one."""
    return KIN_ROLES.get(normalise(surface_form))


class Energy(StrEnum):
    """Monotonic within a call. People do not get less tired."""

    FRESH = "fresh"
    FADING = "fading"
    DEPLETED = "depleted"


class Engagement(StrEnum):
    ENGAGED = "engaged"
    DRIFTING = "drifting"
    WITHDRAWING = "withdrawing"
    CLOSING = "closing"


class Affect(StrEnum):
    WARM = "warm"
    EXCITED = "excited"
    NEUTRAL = "neutral"
    SAD = "sad"
    ANXIOUS = "anxious"
    FRUSTRATED = "frustrated"
    AGITATED = "agitated"


class AffectFlag(StrEnum):
    """Non-exclusive overrides. Any of these outranks the three axes."""

    CONFUSED = "confused"
    LOOPING = "looping"
    DISTRESS = "distress"


class Assessment(BaseModel):
    """One reading of the trailing audio window.

    Three orthogonal axes rather than a flat enum, because 'sad and engaged'
    and 'sad and withdrawing' call for opposite responses and a single label
    forces a bad choice between them.
    """

    energy: Energy
    engagement: Engagement
    affect: Affect
    flags: list[AffectFlag] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    signals: list[str] = Field(
        default_factory=list, description="What the reading was based on"
    )


class AffectState(BaseModel):
    """The agent's current read of her, after hysteresis."""

    energy: Energy = Energy.FRESH
    engagement: Engagement = Engagement.ENGAGED
    affect: Affect = Affect.NEUTRAL
    flags: list[AffectFlag] = Field(default_factory=list)
    # How many consecutive assessments have disagreed with the current state.
    # Two are required to move, so one odd reading cannot make the agent lurch.
    pending: Assessment | None = None
    transitions: list[str] = Field(
        default_factory=list, description="Audit trail, and the demo overlay"
    )


class QuestionStyle(StrEnum):
    OPEN = "open"
    CLOSED = "closed"
    NONE = "none"


class TopicAction(StrEnum):
    DEEPEN = "deepen"
    HOLD = "hold"
    PIVOT = "pivot"
    CLOSE = "close"


class Knobs(BaseModel):
    """What the agent actually changes in response.

    The agent never names the state out loud; it only turns these.
    """

    turn_length: str
    question_type: QuestionStyle
    silence_tolerance: str
    topic_action: TopicAction
    guidance: str = Field(description="The line handed to the agent")
    care_flag: str | None = None


class Ask(BaseModel):
    """A question from a family member, waiting for her next call.

    `from_name` is not optional and is never dropped: she has to hear *who*
    was thinking about her. That attribution is the emotional payload of the
    whole product, and the agent takes no credit for it.
    """

    ask_id: str
    from_name: str
    relation: str = Field(default="", description="son, granddaughter, daughter…")
    question: str
    voice_note_url: str | None = None
    created_at: str | None = None


class CandidateKind(StrEnum):
    THREAD = "thread"
    ASK = "ask"
    DOMAIN = "domain"
    DATE = "date"


class Candidate(BaseModel):
    """One thing the agent could open with, and why it ranked."""

    kind: CandidateKind
    label: str
    say: str = Field(description="How to offer it out loud")
    score: float
    reason: str = Field(default="", description="Shown in the demo overlay")


class SessionPlan(BaseModel):
    """What the agent walks into a call intending to do.

    A fallback, never an agenda: the instruction that renders this also tells
    the agent to abandon it the moment she goes somewhere else.
    """

    greeting: str
    # How many calls have already happened. The base instruction carries a
    # first-meeting introduction, and nothing else tells the agent not to use
    # it — an agent that reintroduces itself every week has no memory at all,
    # whatever the rest of the state says.
    session_count: int = 0
    ask: Ask | None = None
    offers: list[Candidate] = Field(default_factory=list)
    light_offer: Candidate | None = None
    considered: list[Candidate] = Field(
        default_factory=list, description="Everything scored, for the overlay"
    )


class PreferenceType(StrEnum):
    """How she likes to be talked to.

    This layer is what makes session 20 behave differently from session 1. It
    is assembled into the Companion's instruction, so a change here is visible
    in how the agent actually speaks.
    """

    SESSION_LENGTH = "session_length"
    BEST_TIME = "best_time"
    LISTEN_TALK_RATIO = "listen_talk_ratio"
    QUESTION_STYLE = "question_style"
    HEARING = "hearing"
    PACE = "pace"
    SILENCE_TOLERANCE = "silence_tolerance"
    TOPIC_FAVOURITE = "topic_favourite"


class PreferenceObservation(BaseModel):
    """One preference noticed in one conversation."""

    type: PreferenceType
    value: str = Field(
        description='Short and concrete, e.g. "tires after about 11 minutes"'
    )
    evidence: str = Field(default="", description="The line that shows it")
    confidence: float = Field(ge=0.0, le=1.0)


class Preference(BaseModel):
    """An accumulated preference, confirmed or revised across sessions."""

    type: PreferenceType
    value: str
    confidence: float = Field(ge=0.0, le=1.0)
    observations: int = 1
    evidence: str = ""
    first_seen_in: str | None = None
    last_seen_in: str | None = None


class AvoidanceKind(StrEnum):
    """How she declined a topic.

    An explicit refusal and a soft change of subject are different signals and
    deserve different thresholds. "Talk about something else" is not ambiguous;
    drifting onto the
    weather might be.
    """

    REFUSED = "refused"
    DEFLECTED = "deflected"
    ENGAGED = "engaged"


class TopicSignal(BaseModel):
    """One observation about her willingness to discuss something."""

    topic: str = Field(description='Short label, e.g. "her sister"')
    kind: AvoidanceKind
    evidence: str = ""


class SensitiveTopic(BaseModel):
    """A subject to approach carefully, or not to raise at all.

    Silent feedback capture: she never has to say 「don't ask me that」 twice.
    """

    topic: str
    refusals: int = 0
    deflections: int = 0
    engagements: int = 0
    evidence: str = ""
    first_seen_in: str | None = None
    last_seen_in: str | None = None

    @property
    def do_not_raise(self) -> bool:
        """Whether the agent may bring this up unprompted.

        One flat refusal is enough. Two softer deflections are also enough —
        she should not have to refuse thrice. But if she has since chosen to
        talk about it, the subject is hers again and the agent may follow.
        """
        declined = self.refusals >= 1 or self.deflections >= 2
        return declined and self.engagements == 0

    @property
    def sensitive(self) -> bool:
        """Still handled gently even once she has opened it herself."""
        return self.refusals > 0 or self.deflections > 0


class AnchorCandidate(BaseModel):
    """A dateable life event, as reported from one conversation."""

    anchor_id: str = Field(
        description="Stable slug, e.g. anchor_marriage, anchor_shop_open"
    )
    label: str = Field(description='Her event in a few words, e.g. "married"')
    year: int
    confidence: float = Field(ge=0.0, le=1.0)


class Anchor(BaseModel):
    """An accumulated anchor event.

    Anchors are what make relative time resolvable. She says "before I married"
    far more often than she says a year, and once the marriage is known to be
    1968, every such
    phrase acquires a range.
    """

    anchor_id: str
    label: str
    year: int
    confidence: float = Field(ge=0.0, le=1.0)
    first_seen_in: str | None = None
    corroborations: int = 1


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

    topic: str = Field(description='Short label, e.g. "father\'s coffee shop"')
    action: ThreadAction
    left_off_at: str = Field(
        default="",
        description="What she had not told yet. Becomes the next opener.",
    )


class Thread(BaseModel):
    """An unfinished story, carried between sessions.

    The highest-value thing the agent can open a call with, and the cheapest
    memory feature to build: "last time the neighbour came to the door".
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
        `when` becomes "that coffee shop — was that before or after you married?"
        """
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
            'story: not "we were poor" but "we ate white rice with soy sauce, '
            'and my mother said she had already eaten"'
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
