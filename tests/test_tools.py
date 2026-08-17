"""Companion tools — bound to one call's memory, no model involved."""

from __future__ import annotations

import pytest

from sampan.models import (
    Affect,
    AffectState,
    Ask,
    Energy,
    Entity,
    EntityType,
    PreferenceType,
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


class TestOpenThreads:
    def test_the_interrupted_thread_comes_first(self, memory: CallMemory) -> None:
        threads = tool(memory, "get_open_threads")()["threads"]

        assert threads[0]["topic"] == "why the shop closed"
        assert threads[0]["was_interrupted"] is True

    def test_a_forbidden_thread_is_withheld(self, memory: CallMemory) -> None:
        """She said talk about something else about her sister. The tool must not hand
        the agent
        a thread it is not allowed to open."""
        topics = [t["topic"] for t in tool(memory, "get_open_threads")()["threads"]]

        assert "sister" not in topics

    def test_each_thread_says_where_she_stopped(self, memory: CallMemory) -> None:
        threads = tool(memory, "get_open_threads")()["threads"]

        assert all(t["left_off_at"] for t in threads)


class TestRecall:
    def test_finds_a_person_by_name(self, memory: CallMemory) -> None:
        found = tool(memory, "recall")("Ah Chwee")["found"]

        assert found[0]["name"] == "Ah Chwee"
        assert "walking stick" in found[0]["detail"]

    def test_finds_by_an_alias(self, memory: CallMemory) -> None:
        assert tool(memory, "recall")("Ong Ah Chwee")["found"]

    def test_an_unknown_name_returns_nothing_rather_than_guessing(
        self, memory: CallMemory
    ) -> None:
        assert tool(memory, "recall")("")["found"] == []

    def test_an_empty_query_matches_nothing(self, memory: CallMemory) -> None:
        assert tool(memory, "recall")("")["found"] == []


class TestNotePreference:
    def test_records_a_valid_preference(self, memory: CallMemory) -> None:
        result = tool(memory, "note_preference")("hearing", "left ear is weak")

        assert result["recorded"] is True
        assert memory.noted_preferences[0].type is PreferenceType.HEARING

    def test_rejects_a_kind_it_does_not_know(self, memory: CallMemory) -> None:
        result = tool(memory, "note_preference")("favourite_colour", "")

        assert result["recorded"] is False
        assert memory.noted_preferences == []


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

        for name in ("get_pending_ask", "get_open_threads", "note_preference"):
            call = tool(memory, name)
            result = (
                call("hearing", "left ear is weak")
                if name == "note_preference"
                else call()
            )

            assert "Ending early is a success" in result["_guidance"]

    def test_the_guidance_changes_with_her_state(self, memory: CallMemory) -> None:
        memory.affect = AffectState(affect=Affect.EXCITED)
        excited = tool(memory, "get_open_threads")()["_guidance"]

        memory.affect = AffectState(energy=Energy.DEPLETED)
        depleted = tool(memory, "get_open_threads")()["_guidance"]

        assert excited != depleted
        assert "Do not interrupt" in excited

    def test_guidance_never_names_the_state(self, memory: CallMemory) -> None:
        memory.affect = AffectState(energy=Energy.DEPLETED)

        result = tool(memory, "get_open_threads")()

        assert "depleted" not in result["_guidance"]
