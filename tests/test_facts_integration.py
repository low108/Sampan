"""Fact extraction against the real model.

Marked `integration` and excluded from the default run: it costs money, takes
seconds, and varies between runs. Assertions are therefore structural — what was
extracted and whether it is supportable — never on exact wording or counts.

    uv run pytest -m integration -k facts
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sampan.archivist import GeminiStoryExtractor, ingest_conversation
from sampan.config import Settings
from sampan.fact_extraction import GeminiFactExtractor, build_facts
from sampan.facts import Predicate, is_quoted
from sampan.models import Entity

pytestmark = pytest.mark.integration

SEEDS = Path(__file__).resolve().parents[1] / "seeds"


@pytest.fixture(scope="module")
def transcript() -> str:
    """Session 2: the shop opens in 1958 and closes in 1969, so it carries a
    genuine bounded interval rather than an open-ended one."""
    return (SEEDS / "session-02.txt").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def facts(transcript: str):
    settings = Settings()
    if not settings.configured:
        pytest.skip("No GOOGLE_CLOUD_PROJECT configured")

    intake = [
        Entity.model_validate(e)
        for e in json.loads((SEEDS / "intake.json").read_text(encoding="utf-8"))[
            "entities"
        ]
    ]
    # Entity resolution first, exactly as finish_call orders it: facts can only
    # point at entities that exist by the time they are extracted.
    outcome = ingest_conversation(
        transcript,
        GeminiStoryExtractor(settings),
        known_entities=intake,
        conversation_id="conv_facts",
    )
    proposed = GeminiFactExtractor(settings).extract(transcript, outcome.entities)
    return build_facts(
        proposed,
        transcript=transcript,
        known_entities=outcome.entities,
        episode_id="conv_facts",
    )


class TestWhatSurvives:
    def test_the_session_yields_facts(self, facts) -> None:
        assert facts

    def test_every_fact_is_something_she_said(self, facts, transcript: str) -> None:
        """The check that four separate bugs have now been traced to. A model
        asked for a supporting sentence will return its own reasoning shaped
        like one unless the claim is tested against the source."""
        for fact in facts:
            assert is_quoted(fact.quote, transcript), fact.quote

    def test_every_subject_is_a_real_entity(self, facts) -> None:
        for fact in facts:
            assert fact.subject_id.startswith("ent_")

    def test_predicates_stay_inside_the_vocabulary(self, facts) -> None:
        """Predicates are join keys. Validation would have caught an invented
        one, so this asserts the model can work within the closed set at all."""
        allowed = set(Predicate)
        for fact in facts:
            assert fact.predicate in allowed

    def test_statements_are_written_to_be_found(self, facts) -> None:
        """`statement` is the retrieval surface. "he ran it" is unfindable."""
        for fact in facts:
            assert len(fact.statement.split()) >= 4


class TestTime:
    def test_the_shop_carries_a_bounded_interval(self, facts) -> None:
        """She gives both ends in this session — opened fifty-eight, closed
        sixty-nine. That is the bi-temporal model earning its place."""
        spans = [f.year_span for f in facts]
        bounded = [(a, b) for a, b in spans if a and b and b > a]

        assert bounded, f"no fact resolved a span: {spans}"
        assert any(1950 <= a <= 1975 for a, _ in bounded)

    def test_her_words_survive_beside_any_resolved_year(self, facts) -> None:
        for fact in facts:
            if fact.valid_from is not None:
                assert fact.valid_from.raw_phrase.strip()

    def test_undated_facts_are_allowed(self, facts) -> None:
        """An invented year is worse than an absent one, so the prompt permits
        absence. This asserts the permission is real, not that it is used."""
        for fact in facts:
            start, end = fact.year_span
            if start is None and end is None:
                assert "year not yet told" in fact.render()


class TestCurrency:
    def test_newly_extracted_facts_are_current(self, facts) -> None:
        for fact in facts:
            assert fact.is_current
            assert fact.superseded_by is None
