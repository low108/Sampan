"""Seam 1 against the real model.

Marked `integration` and excluded from the default run: it costs money, takes
seconds, and varies between runs. Assertions are therefore structural — what
was extracted and how it scored — never on exact wording.

    uv run pytest -m integration
"""

from __future__ import annotations

from pathlib import Path

import pytest

from sampan.archivist import GeminiStoryExtractor, ingest_conversation
from sampan.config import Settings
from sampan.models import PinType, StoryStatus

pytestmark = pytest.mark.integration

SEEDS = Path(__file__).resolve().parents[1] / "seeds"


@pytest.fixture(scope="module")
def session_one() -> str:
    return (SEEDS / "session-01.txt").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def outcome(session_one: str):
    settings = Settings()
    if not settings.configured:
        pytest.skip("No GOOGLE_CLOUD_PROJECT configured")
    return ingest_conversation(session_one, GeminiStoryExtractor(settings))


class TestSessionOne:
    """Expectations from docs/seed-sessions.md, session 1."""

    def test_extracts_a_handful_of_stories_not_a_pile(self, outcome) -> None:
        """One conversation is 1-4 stories. Many more means the model is
        splitting a single memory or inventing."""
        assert 1 <= len(outcome.stories) <= 4

    def test_finds_at_least_two_pinnable_stories(self, outcome) -> None:
        assert len(outcome.pinned) >= 2

    def test_every_pinned_story_has_a_place_and_a_time(self, outcome) -> None:
        for story in outcome.pinned:
            assert story.candidate.where.is_present
            assert story.candidate.when.is_present

    def test_every_pinned_story_carries_a_sensory_detail(self, outcome) -> None:
        """The field that separates a fact from a story, and the one the
        letter is built around."""
        for story in outcome.pinned:
            assert story.candidate.sense_detail.strip()

    def test_place_stories_are_not_filed_as_timeline(self, outcome) -> None:
        """A story with a real location belongs on the map."""
        for story in outcome.stories:
            if story.candidate.where.is_present:
                assert story.candidate.pin_type is not PinType.TIMELINE

    def test_infers_her_age_into_years(self, outcome) -> None:
        """She says 六七岁吧 and, separately, that she was born in 1946.
        Resolving one against the other is the whole point of storing time
        twice."""
        dated = [s for s in outcome.stories if s.candidate.when.start_year is not None]
        assert dated, "no story resolved to a year"
        for story in dated:
            start = story.candidate.when.start_year
            assert start is not None and 1940 <= start <= 1960

    def test_keeps_her_own_words_for_the_time(self, outcome) -> None:
        for story in outcome.stories:
            assert story.candidate.when.raw_phrase.strip()

    def test_statuses_are_consistent_with_the_rubric(self, outcome) -> None:
        for story in outcome.stories:
            if story.status is StoryStatus.PINNABLE:
                assert story.score >= 4
