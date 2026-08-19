"""The Archivist — post-call extraction.

Runs after the conversation has ended, never during it. The Companion agent
never chases schema fields mid-call; whatever is missing here becomes a gentle
question in a later session instead.

`ingest_conversation` is the seam the pipeline is tested at (docs/spec-p0.md).
Ticket 2 fills in the story half; entities, threads, anchors and preferences
land on top in tickets 3-6.
"""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel

from sampan.anchors import apply_anchors, fold_anchors
from sampan.config import Settings
from sampan.entities import Resolution, Tiebreaker, resolve_mentions
from sampan.models import (
    Anchor,
    AnchorCandidate,
    Closure,
    ClosureReason,
    Entity,
    EntityMention,
    Preference,
    PreferenceObservation,
    ScoredStory,
    SensitiveTopic,
    StoryCandidate,
    Thread,
    ThreadUpdate,
    TopicSignal,
    assess,
)
from sampan.preferences import fold_preferences, fold_sensitivities
from sampan.threads import fold_threads, open_threads

EXTRACTION_PROMPT = """\
You are an oral-history archivist. Below is a transcript between an elderly
woman and the companion that keeps her company.

Find the STORIES she told and turn each into a structured record.

What counts as a story:
- One thing that happened, with a beginning and an end. Not a general feeling.
- "We were poor" is not a story. "We ate white rice with soy sauce, and my
  mother said she had already eaten" is a story.

**Include half-told ones too.** She raised something and did not finish it, or
did not say when or where, or was interrupted — those belong here as well, with
the unknown fields simply left empty. Those gaps matter: they are how the next
conversation knows what to ask her.

So a conversation is usually 2 to 6 stories: the complete ones plus the
half-told ones. One rule holds above all: **do not invent.** If she did not say
it, leave it empty. Never fill a field by guessing.

For each story fill in what you can:
- where: the place, using the name she used
- when: she usually speaks in relative time ("before I married", "the year of
  the big flood"). raw_phrase must be her own words. Fill years only if they
  can be worked out; otherwise leave them empty and use precision `relative`
  or `era`
- who: the people, as she referred to them ("my sister", "Ah Chwee")
- what: what happened
- sense_detail: **the most important field, and the easiest to get wrong.**
  It must be one concrete sensory detail **she herself said** — a taste, a
  sound, something she could see or touch. You must be able to point at the
  line it came from. One only, not a list.

  GOOD  "the ka-ta ka-ta of the sewing machine" — she described that sound
  GOOD  "white rice with soy sauce" — she said what they ate
  BAD   "the scene of the crossing", "those hard years" — that is your summary
        of her, not her words
  BAD   restating the story's own facts and adding "the image of" or "the scene of"

  A simple check: if the sentence is something you concluded rather than
  something she said, **leave it empty.** Empty is completely fine — the next
  conversation will ask her. Forcing something in ruins the field.
- why_it_matters: why it stayed with her
- narrative: 80-150 words, first person, using her own wording where possible
- verbatim_quotes: one or two of her actual sentences

pin_type decides where the story appears. Decide in this order:
- place: it happened somewhere specific (at the river, in the shop, in the
  house). **Most stories are place.**
- object: the story is really about a thing (a sewing machine, a photograph)
- person: it is mainly about what someone was like, with no particular place
- timeline: a lesson, a reflection, advice — no place and no single event
If `where` holds a real place, never choose timeline.

Mark sensitivity `sensitive` for: money, conflict with a living relative,
health, and anything she visibly avoided or steered away from. Otherwise
`routine`.

Also list entity_mentions — the people, places, objects and foods that came up.
- surface_form must be exactly how she said it ("my sister" stays "my sister",
  do not replace it with a name)
- one entry per person per conversation, however often they were mentioned
- type: person / place / object / food
- role: people only — father, mother, elder_sister, husband, son, neighbour…
- detail: one line about what she said of them

threads — subjects raised in this conversation but not finished:
- topic: a short label, e.g. "father's coffee shop"
- action: opened (raised for the first time) / advanced (continuing from
  before) / closed (finished)
- left_off_at: the part she has not reached yet. The next conversation picks up
  from here, so be specific.

closure — how this conversation ended. **This one matters:**
- reason:
  - interrupted: something outside cut it short (doorbell, phone, a visitor)
  - fatigue: she got tired, wanted to rest, her turns got shorter
  - natural: it finished on its own
  - refused: she did not want to talk
  - unknown: cannot tell
- evidence: the line in the transcript that shows it
- active_topic: what she was talking about when it ended

Keep interrupted and fatigue strictly apart. Interrupted means she was
mid-story and still wants to tell it; tired means enough for today. How the
next conversation opens depends entirely on this.

anchors — datable life events. She rarely gives years, but once "married =
1968" is known, every later "before I married" acquires a time.
- Use these fixed anchor_ids: anchor_birth, anchor_marriage, anchor_shop_open,
  anchor_shop_close, anchor_first_child, anchor_arrival (an ancestor's
  crossing), anchor_husband_death, anchor_sister_death. Do not force others in.
- Only list one when she gave a clear year, or one that can be worked out.
  Never a guess.
- confidence: high when she stated the year; low when it had to be derived.

A story's `when`: if she spoke relatively ("before I married"), set anchor_ref
to the matching anchor_id and leave the years empty — they are computed later.

preferences — what this conversation shows about how she likes to be treated.
Only list what is visible:
- session_length: roughly how long before she tires
- best_time: morning or evening
- listen_talk_ratio: does she prefer to talk on, or be asked
- question_style: do concrete questions work better than open ones
- hearing: e.g. left ear weak
- pace: fast or slow
- silence_tolerance: how long a pause she needs
- topic_favourite: what she lights up talking about
Keep value short and concrete. evidence is the line that shows it.

topic_signals — how she responded to each subject. **This is her silent
feedback:**
- kind:
  - refused: she said no plainly ("talk about something else", "don't talk
    about this")
  - deflected: no plain refusal, but she changed the subject, gave one or two
    words, or answered a different question
  - engaged: she brought it up herself, or talked at length
- topic: a short label (e.g. "sister", "why the shop closed")
- evidence: the line

If she later chooses to talk about the same subject, record that honestly as
engaged.

{known_labels}
Transcript:
---
{transcript}
---
"""

KNOWN_LABELS_BLOCK = """\
Labels already used in earlier conversations. If this is the same subject,
**reuse the existing label** rather than inventing a new name — a new name
makes the system treat it as a different thing.
{labels}

"""


def _known_labels_block(topics: list[str]) -> str:
    """Give the model the vocabulary it has already used.

    Without this it invents a fresh label every call — "why the shop closed" one
    session, "grandfather's shop closing" the next — and no amount of string matching
    afterwards can tell that they are the same subject.
    """
    unique = sorted({t.strip() for t in topics if t.strip()})
    if not unique:
        return ""
    return KNOWN_LABELS_BLOCK.format(labels="\n".join(f"- {t}" for t in unique))


class ExtractionResponse(BaseModel):
    stories: list[StoryCandidate]
    entity_mentions: list[EntityMention] = []
    threads: list[ThreadUpdate] = []
    closure: Closure = Closure(reason=ClosureReason.UNKNOWN)
    anchors: list[AnchorCandidate] = []
    preferences: list[PreferenceObservation] = []
    topic_signals: list[TopicSignal] = []


class ConversationOutcome(BaseModel):
    """Everything derived from one conversation.

    Grows as tickets land: threads, anchors and preferences join `stories` and
    `entities` here, and this stays the single return value of the seam.
    """

    stories: list[ScoredStory]
    entities: list[Entity] = []
    resolutions: list[Resolution] = []
    threads: list[Thread] = []
    closure: Closure = Closure(reason=ClosureReason.UNKNOWN)
    anchors: list[Anchor] = []
    preferences: list[Preference] = []
    sensitivities: list[SensitiveTopic] = []

    @property
    def pinned(self) -> list[ScoredStory]:
        return [s for s in self.stories if s.status == "pinnable"]

    @property
    def fragments(self) -> list[ScoredStory]:
        return [s for s in self.stories if s.status == "fragment"]

    @property
    def new_entities(self) -> list[Entity]:
        new_ids = {r.entity_id for r in self.resolutions if r.created}
        return [e for e in self.entities if e.entity_id in new_ids]

    @property
    def open_threads(self) -> list[Thread]:
        return open_threads(self.threads)

    @property
    def do_not_raise(self) -> list[SensitiveTopic]:
        """Subjects the agent must not open on its own next time."""
        return [t for t in self.sensitivities if t.do_not_raise]

    @property
    def interrupted_thread(self) -> Thread | None:
        """What she was cut off mid-way through. The next call's opener."""
        return next((t for t in self.threads if t.interrupted), None)


class StoryExtractor(Protocol):
    """Seam for the model call, so the pipeline can be exercised offline."""

    def extract(
        self, transcript: str, known_labels: list[str] | None = None
    ) -> ExtractionResponse: ...


class GeminiStoryExtractor:
    """Structured extraction against Gemini.

    The client is built lazily so importing this module costs nothing and needs
    no credentials.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._cached_client: Any | None = None

    @property
    def _client(self) -> Any:
        if self._cached_client is None:
            from google import genai

            self._cached_client = genai.Client(
                vertexai=True,
                project=self._settings.project_id,
                location=self._settings.vertex_location,
            )
        return self._cached_client

    def extract(
        self, transcript: str, known_labels: list[str] | None = None
    ) -> ExtractionResponse:
        from google.genai import types

        response = self._client.models.generate_content(
            model=self._settings.archivist_model,
            contents=EXTRACTION_PROMPT.format(
                transcript=transcript,
                known_labels=_known_labels_block(known_labels or []),
            ),
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ExtractionResponse,
                temperature=0.2,
            ),
        )
        parsed = response.parsed
        if parsed is None:
            raise RuntimeError(
                f"Extraction returned no parseable JSON: {response.text}"
            )
        return parsed


def mentions(text: str, subject: str) -> bool:
    """Whether a piece of extracted text is about a subject she named.

    Case-insensitive substring, matching how `build_cards` filters private
    subjects. Deliberately blunt: she said "forget that" in her own words, and
    over-matching costs a story nobody will miss while under-matching breaks a
    promise the agent already made out loud.
    """
    subject = subject.strip().casefold()
    return bool(subject) and subject in text.casefold()


def _forget(outcome: ConversationOutcome, subjects: list[str]) -> ConversationOutcome:
    """Drop what she asked to lose, before any of it reaches the store.

    Stories and threads only.

    Threads are the sharp end: a thread is what the *next* call opens on, so a
    forgotten subject surviving as one means the agent raises the very thing it
    was told to drop, in the next sentence it says to her.

    Entities are kept, because other stories reference them and forgetting a
    story is not forgetting that a person exists. Sensitivities are kept
    deliberately, and this is the counter-intuitive one: a sensitivity derived
    from a painful subject is what steers the agent *away* from it. Dropping it
    alongside the story would make forgetting actively dangerous (D18).
    """
    if not subjects:
        return outcome
    return outcome.model_copy(
        update={
            "stories": [
                story
                for story in outcome.stories
                if not any(
                    mentions(story.candidate.title, subject)
                    or mentions(story.candidate.narrative, subject)
                    for subject in subjects
                )
            ],
            "threads": [
                thread
                for thread in outcome.threads
                if not any(
                    mentions(thread.topic, subject)
                    or mentions(thread.left_off_at, subject)
                    for subject in subjects
                )
            ],
        }
    )


def ingest_conversation(
    transcript: str,
    extractor: StoryExtractor,
    *,
    known_entities: list[Entity] | None = None,
    known_threads: list[Thread] | None = None,
    known_anchors: list[Anchor] | None = None,
    known_preferences: list[Preference] | None = None,
    known_sensitivities: list[SensitiveTopic] | None = None,
    forgotten: list[str] | None = None,
    conversation_id: str = "conv_unknown",
    tiebreaker: Tiebreaker | None = None,
) -> ConversationOutcome:
    """Turn a finished conversation into structured memory.

    This is seam 1. Text in, everything derived out — no audio, no streaming,
    no browser, so the whole spine is testable offline.

    `known_entities` is the family's graph so far, seeded at setup by the
    child-completed intake. Passing it is what turns "my sister" into a reference
    rather than a fourth duplicate sister.

    `forgotten` is every subject she has ever asked to drop, on this call or any
    earlier one. It is applied here rather than at the call site because this is
    the seam everything derived passes through, and a story that escapes into
    one caller has escaped.
    """
    known_labels = [t.topic for t in (known_threads or [])] + [
        t.topic for t in (known_sensitivities or [])
    ]
    extracted = extractor.extract(transcript, known_labels)
    resolution = resolve_mentions(
        extracted.entity_mentions,
        known_entities or [],
        conversation_id=conversation_id,
        tiebreaker=tiebreaker,
    )
    anchors = fold_anchors(
        known_anchors or [], extracted.anchors, conversation_id=conversation_id
    )
    for candidate in extracted.stories:
        candidate.when = apply_anchors(candidate.when, anchors)

    outcome = ConversationOutcome(
        stories=[assess(c) for c in extracted.stories],
        entities=resolution.entities,
        resolutions=resolution.resolutions,
        threads=fold_threads(
            known_threads or [],
            extracted.threads,
            extracted.closure,
            conversation_id=conversation_id,
        ),
        closure=extracted.closure,
        anchors=anchors,
        preferences=fold_preferences(
            known_preferences or [],
            extracted.preferences,
            conversation_id=conversation_id,
        ),
        sensitivities=fold_sensitivities(
            known_sensitivities or [],
            extracted.topic_signals,
            conversation_id=conversation_id,
        ),
    )
    return _forget(outcome, forgotten or [])
