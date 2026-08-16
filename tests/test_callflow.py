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


def story(title: str = "板底街的咖啡店") -> StoryCandidate:
    return StoryCandidate(
        title=title,
        domain=Domain.WORK,
        narrative="我爸爸一九五八年在板底街开了一间咖啡店……",
        when=When(
            raw_phrase="一九五八年",
            start_year=1958,
            end_year=1958,
            precision=Precision.YEAR,
            confidence=0.95,
        ),
        where=Where(raw_name="板底街", confidence=0.9),
        who=[PersonMention(surface_form="我爸爸", role="father", confidence=0.9)],
        what="爸爸开了咖啡店",
        sense_detail="炭火烤面包涂牛油的味道",
        why_it_matters="那是家里最好的日子",
        emotion=Emotion(valence=0.4, labels=["pride"]),
        pin_type=PinType.PLACE,
    )


FULL = ExtractionResponse(
    stories=[story()],
    entity_mentions=[
        EntityMention(surface_form="我爸爸", type=EntityType.PERSON, role="father"),
        EntityMention(surface_form="板底街", type=EntityType.PLACE),
    ],
    threads=[
        ThreadUpdate(
            topic="爸爸的咖啡店",
            action=ThreadAction.OPENED,
            left_off_at="店后来怎么关的",
        )
    ],
    closure=Closure(reason=ClosureReason.FATIGUE, evidence="有一点点累"),
    preferences=[
        PreferenceObservation(
            type=PreferenceType.HEARING, value="左耳不好", confidence=0.9
        )
    ],
    topic_signals=[TopicSignal(topic="姐姐", kind=Avoid.REFUSED, evidence="讲别的")],
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
        transcript.add("user" if i % 2 == 0 else "agent", f"第{i}句")
    return transcript


class TestTranscript:
    def test_incremental_transcription_is_one_turn_not_many(self) -> None:
        """The Live API streams revisions of the same turn."""
        transcript = Transcript()
        transcript.add("user", "我小时候")
        transcript.add("user", "我小时候在树胶园长大")

        assert len(transcript) == 1
        assert "树胶园" in transcript.render()

    def test_speakers_alternate_into_separate_turns(self) -> None:
        transcript = Transcript()
        transcript.add("user", "喂")
        transcript.add("agent", "阿嬷早")
        transcript.add("user", "早")

        assert len(transcript) == 3

    def test_renders_in_the_shape_the_archivist_reads(self) -> None:
        transcript = Transcript()
        transcript.add("agent", "阿嬷早")
        transcript.add("user", "早")

        assert transcript.render() == "A: 阿嬷早\nK: 早"

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

        assert "我是小船" in prepared.agent.instruction  # type: ignore[attr-defined]


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
        assert any("咖啡店" in t.topic for t in second.memory.threads)
        assert any(p.value == "左耳不好" for p in second.memory.preferences)

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

        assert "我是小船" not in second.agent.instruction  # type: ignore[attr-defined]

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

        assert "姐姐" in second.agent.instruction  # type: ignore[attr-defined]
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
            Ask(ask_id="a1", from_name="伟伦", relation="儿子", question="阿公的店?"),
        )

        prepared = prepare_call(repository, settings, narrator_id=NARRATOR)

        assert prepared.memory.ask is not None
        assert prepared.memory.ask.from_name == "伟伦"

    def test_a_delivered_ask_is_not_asked_again(
        self, repository: Repository, settings: Settings
    ) -> None:
        repository.queue_ask(
            NARRATOR, Ask(ask_id="a1", from_name="伟伦", question="阿公的店?")
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
            NARRATOR, Ask(ask_id="a1", from_name="伟伦", question="阿公的店?")
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
                    from_name="伟伦",
                    question=f"问题{i}",
                    created_at=f"2026-08-0{i + 1}T00:00:00Z",
                ),
            )

        prepared = prepare_call(repository, settings, narrator_id=NARRATOR)

        assert prepared.memory.ask is not None
        assert prepared.memory.ask.ask_id == "a0"
