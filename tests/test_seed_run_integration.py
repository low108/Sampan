"""The full seed run — all four sessions in sequence against the real model.

This is Gate 1 from docs/build-plan.md. If it fails, the demo's central claim
fails with it, because sessions 5 and 6 open against exactly this state.

    uv run pytest -m integration tests/test_seed_run_integration.py

Costs four model calls. Assertions are structural, never on wording.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sampan.archivist import (
    ConversationOutcome,
    GeminiStoryExtractor,
    ingest_conversation,
)
from sampan.config import Settings
from sampan.models import ClosureReason, Entity, EntityType
from sampan.threads import rank_for_opener

pytestmark = pytest.mark.integration

SEEDS = Path(__file__).resolve().parents[1] / "seeds"
SESSIONS = (1, 2, 3, 4)


@pytest.fixture(scope="module")
def run() -> dict[int, ConversationOutcome]:
    """Four sessions, carrying entities and threads forward as production does."""
    settings = Settings()
    if not settings.configured:
        pytest.skip("No GOOGLE_CLOUD_PROJECT configured")

    extractor = GeminiStoryExtractor(settings)
    intake = json.loads((SEEDS / "intake.json").read_text(encoding="utf-8"))
    entities = [Entity.model_validate(e) for e in intake["entities"]]
    threads = []
    outcomes: dict[int, ConversationOutcome] = {}

    for n in SESSIONS:
        outcome = ingest_conversation(
            (SEEDS / f"session-0{n}.txt").read_text(encoding="utf-8"),
            extractor,
            known_entities=entities,
            known_threads=threads,
            conversation_id=f"conv_{n:03d}",
        )
        entities, threads = outcome.entities, outcome.threads
        outcomes[n] = outcome

    return outcomes


@pytest.fixture(scope="module")
def final(run: dict[int, ConversationOutcome]) -> ConversationOutcome:
    return run[SESSIONS[-1]]


class TestClosureDetection:
    """The distinction session 5's opening line rests on."""

    @pytest.mark.parametrize("session", [1, 2, 3])
    def test_a_tired_ending_is_read_as_fatigue(
        self, run: dict[int, ConversationOutcome], session: int
    ) -> None:
        assert run[session].closure.reason is ClosureReason.FATIGUE

    def test_the_doorbell_is_read_as_an_interruption(
        self, run: dict[int, ConversationOutcome]
    ) -> None:
        """She says 等一下,有人按门铃 — she was mid-story and wants to return,
        which is a different thing from being tired."""
        assert run[4].closure.reason is ClosureReason.INTERRUPTED

    def test_the_interruption_cites_its_evidence(
        self, run: dict[int, ConversationOutcome]
    ) -> None:
        assert "门铃" in run[4].closure.evidence


class TestInterruptedThread:
    def test_session_four_leaves_an_interrupted_thread(
        self, final: ConversationOutcome
    ) -> None:
        assert final.interrupted_thread is not None

    def test_the_interrupted_thread_is_about_the_shop_closing(
        self, final: ConversationOutcome
    ) -> None:
        """What she was actually cut off in the middle of."""
        thread = final.interrupted_thread
        assert thread is not None
        assert any(word in thread.topic for word in ("关店", "咖啡店", "店"))

    def test_it_records_what_she_had_not_told_yet(
        self, final: ConversationOutcome
    ) -> None:
        """This becomes the next call's opening offer, so it has to be
        specific enough to say out loud."""
        thread = final.interrupted_thread
        assert thread is not None
        assert len(thread.left_off_at) > 5

    def test_the_interrupted_thread_ranks_first_for_the_opener(
        self, final: ConversationOutcome
    ) -> None:
        assert rank_for_opener(final.threads)[0].interrupted is True

    def test_only_one_thread_is_flagged(self, final: ConversationOutcome) -> None:
        assert sum(1 for t in final.threads if t.interrupted) == 1


class TestAccumulation:
    def test_threads_accumulate_across_sessions(
        self, run: dict[int, ConversationOutcome]
    ) -> None:
        assert len(run[4].open_threads) >= 4

    def test_the_grandfather_crossing_stays_open(
        self, final: ConversationOutcome
    ) -> None:
        """Raised in session 3, never finished — the deepest pin on the map
        and still incomplete."""
        topics = " ".join(t.topic for t in final.open_threads)
        assert any(word in topics for word in ("阿公", "槟城", "永春"))

    def test_the_family_graph_grows_without_duplicating_the_intake(
        self, final: ConversationOutcome
    ) -> None:
        assert 20 <= len(final.entities) <= 32
        sisters = [
            e
            for e in final.entities
            if e.type is EntityType.PERSON and e.role == "elder_sister"
        ]
        assert len(sisters) == 1

    def test_the_seed_state_holds_enough_stories_for_a_map(
        self, run: dict[int, ConversationOutcome]
    ) -> None:
        pinned = sum(len(run[n].pinned) for n in SESSIONS)
        assert pinned >= 9


class TestExtractionHonesty:
    def test_a_missing_sensory_detail_is_left_empty_not_invented(
        self, run: dict[int, ConversationOutcome]
    ) -> None:
        """The model will happily satisfy this field with a paraphrase of the
        story's own facts. An empty field is worth more than an invented one,
        because missing_fields is what generates the next question."""
        gaps = [
            field
            for n in SESSIONS
            for story in run[n].stories
            for field in story.missing_fields
        ]
        assert gaps, "every field filled on every story suggests fabrication"

    def test_pinned_stories_still_report_their_gaps(
        self, run: dict[int, ConversationOutcome]
    ) -> None:
        """A story can go on the map and still owe a follow-up question."""
        assert any(story.missing_fields for n in SESSIONS for story in run[n].pinned)
