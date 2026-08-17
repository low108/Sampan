"""Memory surviving between calls — the loop closing, with a stub extractor.

Everything upstream produces state. These tests are about whether it is still
there next time she picks up.
"""

from __future__ import annotations

import pytest

from sampan.archivist import ExtractionResponse
from sampan.callflow import MIN_TURNS_TO_EXTRACT, Transcript, finish_call, prepare_call
from sampan.config import Settings
from sampan.models import (
    Ask,
    Closure,
    ClosureReason,
    Domain,
    Emotion,
    EntityMention,
    EntityType,
    PersonMention,
    PinType,
    Precision,
    PreferenceObservation,
    PreferenceType,
    StoryCandidate,
    ThreadAction,
    ThreadUpdate,
    TopicSignal,
    When,
    Where,
)
from sampan.models import AvoidanceKind as Avoid
from sampan.repository import Repository
from sampan.store import InMemoryDocumentStore

NARRATOR = "ah_khim"


class StubExtractor:
    """Returns a fixed extraction, so these tests are about persistence."""

    def __init__(self, response: ExtractionResponse) -> None:
        self.response = response
        self.seen: list[str] = []

    def extract(
        self, transcript: str, known_labels: list[str] | None = None
    ) -> ExtractionResponse:
        self.seen.append(transcript)
        return self.response


def story(title: str = "the coffee shop on Jalan Bandar") -> StoryCandidate:
    return StoryCandidate(
        title=title,
        domain=Domain.WORK,
        narrative="My father opened the coffee shop on Jalan Bandar in 1958……",
        when=When(
            raw_phrase="in 1958",
            start_year=1958,
            end_year=1958,
            precision=Precision.YEAR,
            confidence=0.95,
        ),
        where=Where(raw_name="Jalan Bandar", confidence=0.9),
        who=[PersonMention(surface_form="my father", role="father", confidence=0.9)],
        what="my father opened the coffee shop",
        sense_detail="the smell of bread toasted over charcoal",
        why_it_matters="those were the best years for the family",
        emotion=Emotion(valence=0.4, labels=["pride"]),
        pin_type=PinType.PLACE,
    )


FULL = ExtractionResponse(
    stories=[story()],
    entity_mentions=[
        EntityMention(surface_form="my father", type=EntityType.PERSON, role="father"),
        EntityMention(surface_form="Jalan Bandar", type=EntityType.PLACE),
    ],
    threads=[
        ThreadUpdate(
            topic="father's coffee shop",
            action=ThreadAction.OPENED,
            left_off_at="how the shop came to close",
        )
    ],
    closure=Closure(reason=ClosureReason.FATIGUE, evidence="a little bit tired"),
    preferences=[
        PreferenceObservation(
            type=PreferenceType.HEARING, value="left ear is weak", confidence=0.9
        )
    ],
    topic_signals=[
        TopicSignal(
            topic="sister", kind=Avoid.REFUSED, evidence="talk about something else"
        )
    ],
)


@pytest.fixture
def repository() -> Repository:
    return Repository(InMemoryDocumentStore())


@pytest.fixture
def settings() -> Settings:
    return Settings(GOOGLE_CLOUD_PROJECT="", SAMPAN_API_KEY="k")


def conversation(turns: int = 6) -> Transcript:
    transcript = Transcript()
    for i in range(turns):
        transcript.add("user" if i % 2 == 0 else "agent", f"line {i}")
    return transcript


class TestTranscript:
    def test_incremental_transcription_is_one_turn_not_many(self) -> None:
        """The Live API streams revisions of the same turn."""
        transcript = Transcript()
        transcript.add("user", "When I was small we lived on the estate")
        transcript.add("user", "I grew up on the rubber estate")

        assert len(transcript) == 1
        assert "rubber estate" in transcript.render()

    def test_speakers_alternate_into_separate_turns(self) -> None:
        transcript = Transcript()
        transcript.add("user", "Hello?")
        transcript.add("agent", "Morning, Ah Ma")
        transcript.add("user", "Morning")

        assert len(transcript) == 3

    def test_renders_in_the_shape_the_archivist_reads(self) -> None:
        transcript = Transcript()
        transcript.add("agent", "Morning, Ah Ma")
        transcript.add("user", "Morning")

        assert transcript.render() == "A: Morning, Ah Ma\nK: Morning"

    def test_blank_transcription_is_ignored(self) -> None:
        transcript = Transcript()
        transcript.add("user", "   ")

        assert len(transcript) == 0


class TestFirstCall:
    def test_a_narrator_we_have_never_met_is_not_an_error(
        self, repository: Repository, settings: Settings
    ) -> None:
        prepared = prepare_call(repository, settings, narrator_id=NARRATOR)

        assert prepared.stored.session_count == 0
        assert prepared.memory.threads == []

    def test_the_first_call_gets_an_introduction(
        self, repository: Repository, settings: Settings
    ) -> None:
        prepared = prepare_call(repository, settings, narrator_id=NARRATOR)

        assert "I am Xiao Chuan" in prepared.agent.instruction  # type: ignore[attr-defined]


class TestMemorySurvives:
    def test_a_finished_call_is_stored(
        self, repository: Repository, settings: Settings
    ) -> None:
        prepared = prepare_call(repository, settings, narrator_id=NARRATOR)

        updated = finish_call(
            repository,
            StubExtractor(FULL),
            prepared,
            conversation(),
            narrator_id=NARRATOR,
        )

        assert updated is not None
        assert updated.session_count == 1

    def test_the_next_call_starts_from_it(
        self, repository: Repository, settings: Settings
    ) -> None:
        """The whole point: session 2 knows what session 1 heard."""
        first = prepare_call(repository, settings, narrator_id=NARRATOR)
        finish_call(
            repository,
            StubExtractor(FULL),
            first,
            conversation(),
            narrator_id=NARRATOR,
        )

        second = prepare_call(repository, settings, narrator_id=NARRATOR)

        assert second.stored.session_count == 1
        assert any("coffee shop" in t.topic for t in second.memory.threads)
        assert any(p.value == "left ear is weak" for p in second.memory.preferences)

    def test_the_second_call_does_not_reintroduce_itself(
        self, repository: Repository, settings: Settings
    ) -> None:
        first = prepare_call(repository, settings, narrator_id=NARRATOR)
        finish_call(
            repository,
            StubExtractor(FULL),
            first,
            conversation(),
            narrator_id=NARRATOR,
        )

        second = prepare_call(repository, settings, narrator_id=NARRATOR)

        assert "I am Xiao Chuan" not in second.agent.instruction  # type: ignore[attr-defined]

    def test_a_refused_subject_is_still_refused_next_time(
        self, repository: Repository, settings: Settings
    ) -> None:
        first = prepare_call(repository, settings, narrator_id=NARRATOR)
        finish_call(
            repository,
            StubExtractor(FULL),
            first,
            conversation(),
            narrator_id=NARRATOR,
        )

        second = prepare_call(repository, settings, narrator_id=NARRATOR)

        assert "sister" in second.agent.instruction  # type: ignore[attr-defined]
        assert any(t.do_not_raise for t in second.memory.sensitivities)

    def test_entities_are_carried_forward(
        self, repository: Repository, settings: Settings
    ) -> None:
        first = prepare_call(repository, settings, narrator_id=NARRATOR)
        finish_call(
            repository,
            StubExtractor(FULL),
            first,
            conversation(),
            narrator_id=NARRATOR,
        )

        assert prepare_call(repository, settings, narrator_id=NARRATOR).memory.entities

    def test_stories_accumulate_rather_than_overwrite(
        self, repository: Repository, settings: Settings
    ) -> None:
        for _ in range(2):
            prepared = prepare_call(repository, settings, narrator_id=NARRATOR)
            finish_call(
                repository,
                StubExtractor(FULL),
                prepared,
                conversation(),
                narrator_id=NARRATOR,
            )

        assert len(repository.load_stories(NARRATOR)) == 2

    def test_one_narrator_cannot_see_another(
        self, repository: Repository, settings: Settings
    ) -> None:
        prepared = prepare_call(repository, settings, narrator_id=NARRATOR)
        finish_call(
            repository,
            StubExtractor(FULL),
            prepared,
            conversation(),
            narrator_id=NARRATOR,
        )

        other = prepare_call(repository, settings, narrator_id="someone_else")

        assert other.memory.entities == []
        assert other.stored.session_count == 0


class TestShortCalls:
    def test_a_misdial_is_not_extracted(
        self, repository: Repository, settings: Settings
    ) -> None:
        """Running the Archivist on two turns wastes a model call and puts
        nothing worth keeping in the archive."""
        prepared = prepare_call(repository, settings, narrator_id=NARRATOR)
        extractor = StubExtractor(FULL)

        result = finish_call(
            repository,
            extractor,
            prepared,
            conversation(MIN_TURNS_TO_EXTRACT - 1),
            narrator_id=NARRATOR,
        )

        assert result is None
        assert extractor.seen == []

    def test_but_the_conversation_is_still_recorded(
        self, repository: Repository, settings: Settings
    ) -> None:
        prepared = prepare_call(repository, settings, narrator_id=NARRATOR)

        finish_call(
            repository,
            StubExtractor(FULL),
            prepared,
            conversation(2),
            narrator_id=NARRATOR,
        )

        assert repository.load_stories(NARRATOR) == []
        assert (
            prepare_call(
                repository, settings, narrator_id=NARRATOR
            ).stored.session_count
            == 0
        )


class TestFamilyAsks:
    def test_a_queued_ask_reaches_the_next_call(
        self, repository: Repository, settings: Settings
    ) -> None:
        repository.queue_ask(
            NARRATOR,
            Ask(
                ask_id="a1",
                from_name="Wei Lun",
                relation="son",
                question="Ah Gong's shop?",
            ),
        )

        prepared = prepare_call(repository, settings, narrator_id=NARRATOR)

        assert prepared.memory.ask is not None
        assert prepared.memory.ask.from_name == "Wei Lun"

    def test_a_delivered_ask_is_not_asked_again(
        self, repository: Repository, settings: Settings
    ) -> None:
        repository.queue_ask(
            NARRATOR, Ask(ask_id="a1", from_name="Wei Lun", question="Ah Gong's shop?")
        )
        prepared = prepare_call(repository, settings, narrator_id=NARRATOR)
        prepared.memory.ask_delivered = True

        finish_call(
            repository,
            StubExtractor(FULL),
            prepared,
            conversation(),
            narrator_id=NARRATOR,
        )

        assert repository.pending_ask(NARRATOR) is None

    def test_an_undelivered_ask_waits_for_the_next_call(
        self, repository: Repository, settings: Settings
    ) -> None:
        """She hung up before hearing it. It should still be there."""
        repository.queue_ask(
            NARRATOR, Ask(ask_id="a1", from_name="Wei Lun", question="Ah Gong's shop?")
        )
        prepared = prepare_call(repository, settings, narrator_id=NARRATOR)

        finish_call(
            repository,
            StubExtractor(FULL),
            prepared,
            conversation(2),
            narrator_id=NARRATOR,
        )

        assert repository.pending_ask(NARRATOR) is not None

    def test_only_one_ask_is_carried_per_call(
        self, repository: Repository, settings: Settings
    ) -> None:
        """Two would turn a conversation into an inbox."""
        for i in range(3):
            repository.queue_ask(
                NARRATOR,
                Ask(
                    ask_id=f"a{i}",
                    from_name="Wei Lun",
                    question=f"question {i}",
                    created_at=f"2026-08-0{i + 1}T00:00:00Z",
                ),
            )

        prepared = prepare_call(repository, settings, narrator_id=NARRATOR)

        assert prepared.memory.ask is not None
        assert prepared.memory.ask.ask_id == "a0"
