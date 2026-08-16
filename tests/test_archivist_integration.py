"""Seam 1 against the real model.

Marked `integration` and excluded from the default run: it costs money, takes
seconds, and varies between runs. Assertions are therefore structural — what
was extracted and how it scored — never on exact wording.

    uv run pytest -m integration
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sampan.archivist import GeminiStoryExtractor, ingest_conversation
from sampan.config import Settings
from sampan.models import Entity, EntityType, PinType, StoryStatus

pytestmark = pytest.mark.integration

SEEDS = Path(__file__).resolve().parents[1] / "seeds"


@pytest.fixture(scope="module")
def session_one() -> str:
    return (SEEDS / "session-01.txt").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def intake() -> list[Entity]:
    raw = json.loads((SEEDS / "intake.json").read_text(encoding="utf-8"))
    return [Entity.model_validate(e) for e in raw["entities"]]


@pytest.fixture(scope="module")
def outcome(session_one: str, intake: list[Entity]):
    settings = Settings()
    if not settings.configured:
        pytest.skip("No GOOGLE_CLOUD_PROJECT configured")
    return ingest_conversation(
        session_one,
        GeminiStoryExtractor(settings),
        known_entities=intake,
        conversation_id="conv_001",
    )


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


class TestEntitiesInSessionOne:
    """Expectations from docs/seed-sessions.md: 父, 母, 姐姐, 阿水,
    双溪镇树胶园, plus foods."""

    def test_uses_her_own_words_for_people(self, outcome) -> None:
        """「我姐姐」 must stay 「我姐姐」 in the mention, not be helpfully
        rewritten to a name she never said."""
        surfaces = {r.mention.surface_form for r in outcome.resolutions}
        assert any("姐姐" in s for s in surfaces)

    def test_resolves_kin_terms_to_the_family_intake(self, outcome) -> None:
        """The point of the child-completed intake: she says 我妈妈 and it
        lands on the mother the family already described."""
        resolved = {r.entity_id for r in outcome.resolutions if not r.created}
        assert {"ent_mother", "ent_father", "ent_sister"} <= resolved

    def test_does_not_duplicate_anyone_from_the_intake(self, outcome) -> None:
        """A second 姐姐 in the graph means a duplicate pin on the family map
        and an agent that asks about someone already known to have died."""
        sisters = [
            e
            for e in outcome.entities
            if e.type is EntityType.PERSON and e.role == "elder_sister"
        ]

        assert len(sisters) == 1
        assert sisters[0].entity_id == "ent_sister"

    def test_creates_the_neighbour_she_mentions(self, outcome) -> None:
        """阿水 is not in the intake — he should arrive as a new provisional
        person for the family to confirm."""
        names = {e.canonical_name for e in outcome.new_entities}
        assert "阿水" in names

    def test_new_entities_are_provisional(self, outcome) -> None:
        for entity in outcome.new_entities:
            assert entity.provisional
            assert not entity.confirmed_by_family

    def test_records_where_each_new_entity_came_from(self, outcome) -> None:
        for entity in outcome.new_entities:
            assert entity.first_mentioned_in == "conv_001"

    def test_finds_places_and_foods_not_only_people(self, outcome) -> None:
        types = {e.type for e in outcome.new_entities}
        assert EntityType.PLACE in types
        assert EntityType.FOOD in types
