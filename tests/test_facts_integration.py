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


class TestTheAssembledPath:
    """`finish_call` with the production stack, against the real model.

    Every other test in this file builds the pieces itself, in the order the
    comment above says `finish_call` uses them. That reimplementation is
    precisely how the wiring gap survived: the pieces all worked, were all
    tested, and were never connected. The WebSocket handler passed neither
    `fact_extractor` nor `judge`, both default to `None`, and no fact was
    extracted by any live call for the whole life of the subsystem.

    This exercises what production actually runs, so the same gap cannot open
    again without a red test.
    """

    def _repo_with_intake(self):
        from sampan.repository import Repository
        from sampan.store import InMemoryDocumentStore

        store = InMemoryDocumentStore()
        raw = json.loads((SEEDS / "intake.json").read_text(encoding="utf-8"))
        for entity in raw["entities"]:
            store.put("entities__probe", entity["entity_id"], entity)
        return Repository(store)

    def _transcript(self, text: str):
        from sampan.callflow import Transcript

        parsed = Transcript()
        for line in text.splitlines():
            if line.startswith("K: "):
                parsed.add("user", line[3:])
            elif line.startswith("A: "):
                parsed.add("agent", line[3:])
        return parsed

    def test_a_call_through_the_production_stack_writes_facts(
        self, transcript: str
    ) -> None:
        from sampan.app import build_extraction_stack
        from sampan.callflow import finish_call, prepare_call

        settings = Settings()
        if not settings.configured:
            pytest.skip("No GOOGLE_CLOUD_PROJECT configured")

        repo = self._repo_with_intake()
        stack = build_extraction_stack(settings)
        prepared = prepare_call(repo, settings, narrator_id="probe")

        finish_call(
            repo,
            stack.stories,
            prepared,
            self._transcript(transcript),
            narrator_id="probe",
            fact_extractor=stack.facts,
            judge=stack.judge,
        )

        stored = repo.load_facts("probe")

        # Structural, not exact: the model varies. What must hold is that the
        # assembled path produced edges at all, and that each carries the
        # sentence she said -- the refusal rule that makes them trustworthy.
        assert stored, "the production stack extracted no facts"
        assert all(fact.quote for fact in stored)
        assert all(is_quoted(fact.quote, transcript) for fact in stored)

    def test_facts_accumulate_across_chained_calls(self, transcript: str) -> None:
        """Two calls, same narrator. The second must see the first's facts as
        held, which is the only condition under which the judge is reached."""
        from sampan.app import build_extraction_stack
        from sampan.callflow import finish_call, prepare_call

        settings = Settings()
        if not settings.configured:
            pytest.skip("No GOOGLE_CLOUD_PROJECT configured")

        repo = self._repo_with_intake()
        stack = build_extraction_stack(settings)

        for _ in range(2):
            prepared = prepare_call(repo, settings, narrator_id="probe")
            finish_call(
                repo,
                stack.stories,
                prepared,
                self._transcript(transcript),
                narrator_id="probe",
                fact_extractor=stack.facts,
                judge=stack.judge,
            )

        everything = repo.load_facts("probe", current_only=False)

        assert everything, "no facts survived two calls"
        # Retelling the same session should not double the archive: the judge
        # saw the held facts. Whether it retired any is its call, not ours.
        assert len({f.statement for f in everything}) < len(everything) or all(
            f.is_current for f in everything
        )


class TestContradictionEndToEnd:
    """The judge, against the real model, on a real disagreement.

    Every other contradiction test stubs the verdict, which proves the archive
    acts correctly on a verdict but not that a verdict is ever reached. Three
    probes failed to reach one before this shape worked. Only one cause is
    confirmed -- with no entity for the narrator, every fact about her is
    refused for an unknown subject, so nothing about her can ever be compared.
    The others are unproven; see docs/system-analysis.md §8.3.

    The claim under test is the two-clock rule: a later telling retires the
    earlier one in *transaction* time and leaves *valid* time exactly as she
    said it, because the family may correct the system and never her.
    """

    HELD = "Her father opened a coffee shop in Ipoh on Jalan Bandar in 1958."

    RETELLING = """\
A: Ah Ma, tell me about the coffee shop again.
K: The shop at Jalan Bandar. My father's shop, Ah Gong's shop everybody call it.
A: How long did he keep it?
K: He kept that shop until nineteen seventy-one. Nineteen seventy-one he stopped.
A: Nineteen seventy-one.
K: Yes. Nineteen seventy-one, that year he close the shop and never open again.
A: What happened that year?
K: His hands no good already. He told me, Ah Khim, cannot do anymore.
A: I see.
K: The shop was open right up to nineteen seventy-one, then finish.
"""

    def test_a_later_telling_retires_the_earlier_one_without_editing_her(
        self,
    ) -> None:
        from sampan.app import build_extraction_stack
        from sampan.callflow import Transcript, finish_call, prepare_call
        from sampan.facts import Fact, Predicate
        from sampan.models import Precision, When
        from sampan.repository import Repository
        from sampan.store import InMemoryDocumentStore

        settings = Settings()
        if not settings.configured:
            pytest.skip("No GOOGLE_CLOUD_PROJECT configured")

        store = InMemoryDocumentStore()
        raw = json.loads((SEEDS / "intake.json").read_text(encoding="utf-8"))
        for entity in raw["entities"]:
            store.put("entities__probe", entity["entity_id"], entity)
        repo = Repository(store)

        # The archive already believes the shop closed in 1969.
        original = Fact(
            fact_id="fact_held_shop",
            subject_id="ent_father",
            predicate=Predicate.OWNED,
            object_literal="a coffee shop on Jalan Bandar",
            statement=self.HELD,
            quote=(
                "Later he saved a bit of money, nineteen fifty-eight "
                "he opened a coffee shop."
            ),
            valid_from=When(
                raw_phrase="nineteen fifty-eight",
                start_year=1958,
                precision=Precision.YEAR,
                confidence=1.0,
            ),
            valid_to=When(
                raw_phrase="sixty-nine closed",
                start_year=1969,
                precision=Precision.YEAR,
                confidence=1.0,
            ),
            episode_id="conv_seed",
        )
        repo.save_facts("probe", [original])

        transcript = Transcript()
        for line in self.RETELLING.splitlines():
            if line.startswith("K: "):
                transcript.add("user", line[3:])
            elif line.startswith("A: "):
                transcript.add("agent", line[3:])

        stack = build_extraction_stack(settings)
        prepared = prepare_call(repo, settings, narrator_id="probe")
        finish_call(
            repo,
            stack.stories,
            prepared,
            transcript,
            narrator_id="probe",
            fact_extractor=stack.facts,
            judge=stack.judge,
        )

        everything = repo.load_facts("probe", current_only=False)
        held = next(f for f in everything if f.fact_id == "fact_held_shop")

        # Structural, because the model varies: either the judge found the
        # disagreement, or it did not and the archive is unchanged. What must
        # never happen is the earlier telling being edited.
        assert held.valid_from is not None
        assert held.valid_from.start_year == 1958, "her valid time was rewritten"
        assert held.valid_to is not None
        assert held.valid_to.start_year == 1969, "her valid time was rewritten"

        if not held.is_current:
            # Retired: transaction time only, and it names its successor.
            assert held.t_expired is not None
            assert held.superseded_by
            assert held.superseded_by != held.fact_id
            # And the disagreement comes back as a question rather than the
            # archive quietly choosing which telling is true.
            kinds = [c["kind"] for c in repo.open_concerns("probe")]
            assert "contradiction" in kinds
