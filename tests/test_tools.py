"""Companion tools — bound to one call's memory, no model involved."""

from __future__ import annotations

import pytest

from sampan.facts import Fact, Predicate
from sampan.models import (
    Affect,
    AffectState,
    Ask,
    Energy,
    Entity,
    EntityType,
    SensitiveTopic,
    Thread,
)
from sampan.tools import CallMemory, build_tools


@pytest.fixture
def memory() -> CallMemory:
    return CallMemory(
        threads=[
            Thread(
                thread_id="t1",
                topic="why the shop closed",
                interrupted=True,
                left_off_at="the years after the shop closed",
            ),
            Thread(thread_id="t2", topic="sister", left_off_at="what became of her"),
            Thread(
                thread_id="t3",
                topic="the wedding photograph",
                left_off_at="the day it was taken",
            ),
        ],
        entities=[
            Entity(
                entity_id="e1",
                type=EntityType.PERSON,
                canonical_name="Ah Chwee",
                aliases=["Ong Ah Chwee"],
                detail=",walking stick",
            ),
            Entity(
                entity_id="e2",
                type=EntityType.PLACE,
                canonical_name="Jalan Bandar",
                detail="father's coffee shop",
            ),
        ],
        facts=[
            Fact(
                fact_id="f1",
                subject_id="e1",
                predicate=Predicate.NEIGHBOUR_OF,
                object_id="e2",
                statement="Ah Chwee lived next door on Jalan Bandar",
                episode_id="conv_001",
                quote="next door stayed Ah Chwee, and we went to the river every day",
                confidence=0.8,
            )
        ],
        sensitivities=[SensitiveTopic(topic="sister", refusals=1)],
        ask=Ask(
            ask_id="a1",
            from_name="Wei Lun",
            relation="son",
            question="Did Ah Gong leave anything behind?",
        ),
    )


def tool(memory: CallMemory, name: str):
    return next(t for t in build_tools(memory) if t.__name__ == name)


class TestPendingAsk:
    def test_hands_back_the_asker_by_name(self, memory: CallMemory) -> None:
        result = tool(memory, "get_pending_ask")()

        assert result["from_name"] == "Wei Lun"
        assert "Wei Lun asked" in result["say_it_like"]

    def test_records_that_it_was_delivered(self, memory: CallMemory) -> None:
        tool(memory, "get_pending_ask")()

        assert memory.ask_delivered is True

    def test_no_ask_is_reported_plainly(self) -> None:
        empty = CallMemory()

        assert tool(empty, "get_pending_ask")()["has_ask"] is False


class TestRemember:
    """One tool where there were three. Retrieval is agent-initiated because a
    live session's instruction is fixed at connect and nothing can be injected
    per turn (FINDINGS.md)."""

    def test_it_finds_a_fact_by_name(self, memory: CallMemory) -> None:
        result = tool(memory, "remember")("Ah Chwee")

        assert result["known"]
        assert "Jalan Bandar" in result["known"][0]["fact"]

    def test_a_fact_arrives_with_the_sentence_behind_it(
        self, memory: CallMemory
    ) -> None:
        """The agent should be able to say what she said, not paraphrase the
        archive back at her."""
        result = tool(memory, "remember")("Ah Chwee")

        assert "next door stayed Ah Chwee" in result["known"][0]["she_said"]

    def test_an_alias_reaches_the_same_entity(self, memory: CallMemory) -> None:
        assert tool(memory, "remember")("Ong Ah Chwee")["known"]

    def test_an_unknown_name_returns_nothing_rather_than_guessing(
        self, memory: CallMemory
    ) -> None:
        assert tool(memory, "remember")("Ah Seng")["known"] == []

    def test_an_empty_query_matches_nothing(self, memory: CallMemory) -> None:
        result = tool(memory, "remember")("   ")

        assert result["known"] == []
        assert result["she_said"] == []

    def test_it_still_surfaces_unfinished_threads(self, memory: CallMemory) -> None:
        """Folded in from get_open_threads. Nothing published handles unfinished
        threads as a memory type, so they had to survive the consolidation."""
        result = tool(memory, "remember")("shop")

        assert any("shop" in topic for topic in result["unfinished"])

    def test_a_forbidden_subject_is_never_offered(self, memory: CallMemory) -> None:
        """Her sister. Two deflections and the agent stops raising her."""
        result = tool(memory, "remember")("sister")

        assert all("sister" not in topic for topic in result["unfinished"])

    def test_asking_seeds_the_next_search(self, memory: CallMemory) -> None:
        """What she has already been talking about steers later traversal."""
        tool(memory, "remember")("Ah Chwee")

        assert "Ah Chwee" in memory.mentioned


class TestPrivacy:
    def test_marking_private_is_obeyed_without_argument(
        self, memory: CallMemory
    ) -> None:
        result = tool(memory, "mark_private")("the quarrel with my sister")

        assert memory.private_marks == ["the quarrel with my sister"]
        assert "won't write that down" in result["tell_her"]


class TestCare:
    def test_a_concern_reaches_the_family_immediately(self, memory: CallMemory) -> None:
        """A fall should not wait for her to hang up."""
        delivered: list[tuple[str, str]] = []
        memory.on_concern = lambda kind, detail: delivered.append((kind, detail))

        result = tool(memory, "flag_concern")(
            "fall", "slipped in the bathroom this morning"
        )

        assert delivered == [("fall", "slipped in the bathroom this morning")]
        assert result["family_notified"] is True

    def test_she_is_told_it_was_passed_on(self, memory: CallMemory) -> None:
        """The agent is transparent when it flags something. Nothing happens
        behind her back."""
        memory.on_concern = lambda kind, detail: None

        result = tool(memory, "flag_concern")("fall", "a fall")

        assert "Wei Lun" in result["tell_her"]

    def test_it_does_not_claim_delivery_that_did_not_happen(
        self, memory: CallMemory
    ) -> None:
        """Saying it told her family when it did not is a lie to an eighty-
        year-old about her own safety."""

        def explode(kind: str, detail: str) -> None:
            raise ConnectionError("firestore down")

        memory.on_concern = explode
        result = tool(memory, "flag_concern")("pain", "chest feels tight")

        assert result["family_notified"] is False
        assert "Wei Lun" not in result["tell_her"]

    def test_nor_when_nothing_is_wired_up_at_all(self, memory: CallMemory) -> None:
        result = tool(memory, "flag_concern")("pain", "chest feels tight")

        assert result["family_notified"] is False
        assert "Wei Lun" not in result["tell_her"]

    def test_the_concern_is_still_recorded_locally(self, memory: CallMemory) -> None:
        tool(memory, "flag_concern")("fall", "a fall")

        assert memory.concerns[0]["kind"] == "fall"

    def test_it_keeps_her_on_the_line(self, memory: CallMemory) -> None:
        assert tool(memory, "flag_concern")("pain", "chest feels tight")[
            "stay_on_the_line"
        ]


class TestGuidanceRidesAlong:
    """Tool responses are the only channel that reaches the agent mid-call
    without her hearing it (FINDINGS.md)."""

    def test_every_tool_carries_current_guidance(self, memory: CallMemory) -> None:
        memory.affect = AffectState(energy=Energy.DEPLETED)

        for name in ("get_pending_ask", "remember"):
            call = tool(memory, name)
            result = call("Ah Chwee") if name == "remember" else call()

            assert "Ending early is a success" in result["_guidance"]

    def test_the_guidance_changes_with_her_state(self, memory: CallMemory) -> None:
        memory.affect = AffectState(affect=Affect.EXCITED)
        excited = tool(memory, "remember")("Ah Chwee")["_guidance"]

        memory.affect = AffectState(energy=Energy.DEPLETED)
        depleted = tool(memory, "remember")("Ah Chwee")["_guidance"]

        assert excited != depleted
        assert "Do not interrupt" in excited

    def test_guidance_never_names_the_state(self, memory: CallMemory) -> None:
        memory.affect = AffectState(energy=Energy.DEPLETED)

        result = tool(memory, "remember")("Ah Chwee")

        assert "depleted" not in result["_guidance"]
