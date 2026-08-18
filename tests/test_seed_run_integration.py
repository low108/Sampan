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
from sampan.models import ClosureReason, Entity, EntityType, PreferenceType
from sampan.preferences import describe_for_instruction, may_raise
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
    anchors = []
    preferences = []
    sensitivities = []
    outcomes: dict[int, ConversationOutcome] = {}

    for n in SESSIONS:
        outcome = ingest_conversation(
            (SEEDS / f"session-0{n}.txt").read_text(encoding="utf-8"),
            extractor,
            known_entities=entities,
            known_threads=threads,
            known_anchors=anchors,
            known_preferences=preferences,
            known_sensitivities=sensitivities,
            conversation_id=f"conv_{n:03d}",
        )
        entities, threads, anchors = (
            outcome.entities,
            outcome.threads,
            outcome.anchors,
        )
        preferences, sensitivities = outcome.preferences, outcome.sensitivities
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
        """She says wait, someone is at the door — she was mid-story and wants to
        return,
        which is a different thing from being tired."""
        assert run[4].closure.reason is ClosureReason.INTERRUPTED

    def test_the_interruption_cites_its_evidence(
        self, run: dict[int, ConversationOutcome]
    ) -> None:
        assert "door" in run[4].closure.evidence


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
        assert any(
            word in thread.topic
            for word in ("the shop closing", "the coffee shop", "shop")
        )

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
        assert any(
            word in topics.lower()
            for word in ("grandfather", "ah gong", "fujian", "yongchun", "crossing")
        )

    def test_the_family_graph_grows_without_duplicating_the_intake(
        self, final: ConversationOutcome
    ) -> None:
        """A duplicate is the failure that matters, not the total.

        A second sister in the graph means a duplicate pin on the family map
        and an agent that asks brightly after someone already known to have
        died. The total entity count drifts run to run -- the extractor is free
        to decide whether the kerosene lamp is worth naming -- so the bound on
        it is loose, and the real assertion is that no kin role from the intake
        was ever doubled.
        """
        assert len(final.entities) >= 18

        people = [e for e in final.entities if e.type is EntityType.PERSON]
        for role in ("sister", "mother", "father", "husband", "son", "grandfather"):
            named = [e for e in people if e.role == role]
            assert len(named) <= 1, (
                f"{role} duplicated: {[e.canonical_name for e in named]}"
            )

    def test_the_seed_state_holds_enough_stories_for_a_map(
        self, run: dict[int, ConversationOutcome]
    ) -> None:
        """What the demo needs is a map with spread, not a particular count.

        An exact total is not assertable here: the same four seeds yielded 7
        pinned stories on one run and 10 on the next, with every story scoring
        5 or 6 and none missing a place or a time. The extractor is
        nondeterministic about where one memory ends and the next begins, so a
        threshold set inside that spread fails for no reason anyone can act on.
        These assert the properties a map actually needs.
        """
        pinned = [story for n in SESSIONS for story in run[n].pinned]
        assert len(pinned) >= 6

        places = {
            s.candidate.where.raw_name.lower()
            for s in pinned
            if s.candidate.where.is_present
        }
        assert len(places) >= 3, f"a map needs spread, got {places}"

        years = {
            s.candidate.when.start_year for s in pinned if s.candidate.when.start_year
        }
        assert max(years) - min(years) >= 15, f"a life, not a moment: {sorted(years)}"


class TestAnchors:
    """Anchors are what make her relative time sortable on a timeline."""

    def test_discovers_the_dates_she_states_plainly(
        self, final: ConversationOutcome
    ) -> None:
        found = {a.anchor_id for a in final.anchors}
        assert {
            "anchor_birth",
            "anchor_shop_open",
            "anchor_marriage",
            "anchor_shop_close",
        } <= found

    @pytest.mark.parametrize(
        ("anchor_id", "year"),
        [
            ("anchor_birth", 1946),
            ("anchor_shop_open", 1958),
            ("anchor_marriage", 1968),
            ("anchor_shop_close", 1969),
        ],
    )
    def test_gets_the_years_right(
        self, final: ConversationOutcome, anchor_id: str, year: int
    ) -> None:
        anchor = next(a for a in final.anchors if a.anchor_id == anchor_id)
        assert anchor.year == year

    def test_anchors_survive_across_sessions(
        self, run: dict[int, ConversationOutcome]
    ) -> None:
        """Discovered in session 2, still known in session 4."""
        assert any(a.anchor_id == "anchor_marriage" for a in run[4].anchors)

    def test_a_date_mentioned_twice_is_corroborated(
        self, final: ConversationOutcome
    ) -> None:
        """She dates the shop closing in session 2 and again in session 4."""
        anchor = next(a for a in final.anchors if a.anchor_id == "anchor_shop_close")
        assert anchor.corroborations >= 2

    def test_does_not_invent_an_anchor_she_never_dated(
        self, final: ConversationOutcome
    ) -> None:
        """Her grandfather's crossing is 「,me」. That is not
        a date, and guessing one would put a false pin on the map."""
        assert not any(a.anchor_id == "anchor_arrival" for a in final.anchors)

    def test_a_relative_phrase_gets_a_bound_from_its_anchor(
        self, run: dict[int, ConversationOutcome]
    ) -> None:
        """before I married has no year in the transcript. Against anchor_marriage it
        acquires an upper bound, while keeping her own words."""
        bounded = [
            s.candidate.when
            for n in SESSIONS
            for s in run[n].stories
            if s.candidate.when.anchor_ref is not None
            and (
                s.candidate.when.start_year is not None
                or s.candidate.when.end_year is not None
            )
        ]

        assert bounded
        for when in bounded:
            assert when.raw_phrase.strip()

    def test_a_phrase_with_no_anchor_is_left_unresolved(
        self, run: dict[int, ConversationOutcome]
    ) -> None:
        """「in the old days」 on its own anchors to nothing. An unsortable story is
        better than a fabricated date."""
        unresolved = [
            s.candidate.when
            for n in SESSIONS
            for s in run[n].stories
            if s.candidate.when.start_year is None and s.candidate.when.end_year is None
        ]

        assert unresolved


class TestSensitivity:
    """Session 6's payoff depends on the agent having *learned* to avoid her
    sister, so that her raising the subject herself lands."""

    def test_learns_the_sister_is_off_limits(self, final: ConversationOutcome) -> None:
        """In session 3 the agent starts "your sister —" and she says "talk about
        something else".
        That is not ambiguous, and once is enough."""
        avoided = " ".join(t.topic for t in final.do_not_raise)
        assert "sister" in avoided

    def test_the_sister_is_never_raised_again_by_the_agent(
        self, final: ConversationOutcome
    ) -> None:
        assert not may_raise("sister", final.sensitivities)

    def test_a_refusal_she_later_reopens_is_not_permanent(
        self, final: ConversationOutcome
    ) -> None:
        """She refuses to discuss why the shop closed in session 2, then tells
        the whole story in session 4 when her son asks. The subject is hers
        again — the agent should not keep tiptoeing around it."""
        closing = [
            t
            for t in final.sensitivities
            if "shop" in t.topic.lower() and "clos" in t.topic.lower()
        ]
        assert closing, "the shop closing was never recorded as a topic"
        assert any(t.engagements > 0 for t in closing)
        assert all(not t.do_not_raise for t in closing)

    def test_topics_she_enjoyed_are_not_avoided(
        self, final: ConversationOutcome
    ) -> None:
        assert may_raise("father's coffee shop", final.sensitivities)

    def test_labels_stay_stable_across_sessions(
        self, final: ConversationOutcome
    ) -> None:
        """The model invents a fresh label every call unless given the
        vocabulary it already used, and no post-hoc string matching can then
        tell why the shop closed from shop."""
        assert len(final.sensitivities) <= 12


class TestPreferences:
    """The layer that makes session 20 speak differently from session 1."""

    def test_learns_how_to_be_heard(self, final: ConversationOutcome) -> None:
        """She says speak louder, my left ear is not good once, in session 1."""
        hearing = [p for p in final.preferences if p.type is PreferenceType.HEARING]
        assert hearing
        assert any(
            word in hearing[0].value.lower() for word in ("loud", "left", "ear", "slow")
        )

    def test_preferences_accumulate_rather_than_reset(
        self, run: dict[int, ConversationOutcome]
    ) -> None:
        """A count is not assertable here: how many preferences four
        conversations yield moves between runs, and a threshold inside that
        spread fails without telling anyone what to do about it -- the same
        trap as `pinned >= 9` and `20 <= entities <= 32` above.

        What must hold is that the layer carries forward. Folding keeps one
        value per kind, so the set can grow or hold steady and must never
        shrink; a drop means a later session discarded what an earlier one
        learned, which is the whole mechanism failing.
        """
        counts = [len(run[n].preferences) for n in SESSIONS]

        assert counts[-1] >= 1, "nothing was ever learned about how to talk to her"
        assert counts == sorted(counts), f"preferences were lost: {counts}"

    def test_holds_one_value_per_kind(self, final: ConversationOutcome) -> None:
        kinds = [p.type for p in final.preferences]
        assert len(kinds) == len(set(kinds))

    def test_the_learned_layer_reaches_the_instruction(
        self, final: ConversationOutcome
    ) -> None:
        """This string is the visible proof of memory in the demo: it is empty
        at session 1 and carries her sister and her deaf ear by session 5."""
        rendered = describe_for_instruction(final.preferences, final.sensitivities)

        assert "sister" in rendered
        assert rendered != describe_for_instruction([], [])

    def test_the_instruction_quotes_nothing_back_at_her(
        self, final: ConversationOutcome
    ) -> None:
        """Evidence is kept for the family view and for debugging. An agent
        able to quote "talk about something else" back at her is a surveillance
        device."""
        rendered = describe_for_instruction(final.preferences, final.sensitivities)

        assert "talk about something else" not in rendered


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
