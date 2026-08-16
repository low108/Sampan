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
                topic="关店的原因",
                interrupted=True,
                left_off_at="关店以后的日子",
            ),
            Thread(thread_id="t2", topic="姐姐", left_off_at="她们后来怎样"),
            Thread(thread_id="t3", topic="结婚照", left_off_at="拍照那天"),
        ],
        entities=[
            Entity(
                entity_id="e1",
                type=EntityType.PERSON,
                canonical_name="阿水",
                aliases=["王亚水"],
                detail="童年邻居,现在走路要拿拐杖",
            ),
            Entity(
                entity_id="e2",
                type=EntityType.PLACE,
                canonical_name="板底街",
                detail="爸爸的咖啡店在这里",
            ),
        ],
        sensitivities=[SensitiveTopic(topic="姐姐", refusals=1)],
        ask=Ask(
            ask_id="a1",
            from_name="伟伦",
            relation="儿子",
            question="阿公有没有留下什么东西?",
        ),
    )


def tool(memory: CallMemory, name: str):
    return next(t for t in build_tools(memory) if t.__name__ == name)


class TestPendingAsk:
    def test_hands_back_the_asker_by_name(self, memory: CallMemory) -> None:
        result = tool(memory, "get_pending_ask")()

        assert result["from_name"] == "伟伦"
        assert "伟伦问" in result["say_it_like"]

    def test_records_that_it_was_delivered(self, memory: CallMemory) -> None:
        tool(memory, "get_pending_ask")()

        assert memory.ask_delivered is True

    def test_no_ask_is_reported_plainly(self) -> None:
        empty = CallMemory()

        assert tool(empty, "get_pending_ask")()["has_ask"] is False


class TestOpenThreads:
    def test_the_interrupted_thread_comes_first(self, memory: CallMemory) -> None:
        threads = tool(memory, "get_open_threads")()["threads"]

        assert threads[0]["topic"] == "关店的原因"
        assert threads[0]["was_interrupted"] is True

    def test_a_forbidden_thread_is_withheld(self, memory: CallMemory) -> None:
        """She said 讲别的 about her sister. The tool must not hand the agent
        a thread it is not allowed to open."""
        topics = [t["topic"] for t in tool(memory, "get_open_threads")()["threads"]]

        assert "姐姐" not in topics

    def test_each_thread_says_where_she_stopped(self, memory: CallMemory) -> None:
        threads = tool(memory, "get_open_threads")()["threads"]

        assert all(t["left_off_at"] for t in threads)


class TestRecall:
    def test_finds_a_person_by_name(self, memory: CallMemory) -> None:
        found = tool(memory, "recall")("阿水")["found"]

        assert found[0]["name"] == "阿水"
        assert "拐杖" in found[0]["detail"]

    def test_finds_by_an_alias(self, memory: CallMemory) -> None:
        assert tool(memory, "recall")("王亚水")["found"]

    def test_an_unknown_name_returns_nothing_rather_than_guessing(
        self, memory: CallMemory
    ) -> None:
        assert tool(memory, "recall")("陈大文")["found"] == []

    def test_an_empty_query_matches_nothing(self, memory: CallMemory) -> None:
        assert tool(memory, "recall")("")["found"] == []


class TestNotePreference:
    def test_records_a_valid_preference(self, memory: CallMemory) -> None:
        result = tool(memory, "note_preference")("hearing", "左耳不好")

        assert result["recorded"] is True
        assert memory.noted_preferences[0].type is PreferenceType.HEARING

    def test_rejects_a_kind_it_does_not_know(self, memory: CallMemory) -> None:
        result = tool(memory, "note_preference")("favourite_colour", "蓝色")

        assert result["recorded"] is False
        assert memory.noted_preferences == []


class TestPrivacy:
    def test_marking_private_is_obeyed_without_argument(
        self, memory: CallMemory
    ) -> None:
        result = tool(memory, "mark_private")("跟姐姐吵架的事")

        assert memory.private_marks == ["跟姐姐吵架的事"]
        assert "不写进去" in result["tell_her"]


class TestCare:
    def test_a_concern_is_recorded_and_she_is_told(self, memory: CallMemory) -> None:
        """The agent is transparent when it flags something. Nothing happens
        behind her back."""
        result = tool(memory, "flag_concern")("fall", "早上在浴室滑倒")

        assert memory.concerns[0]["kind"] == "fall"
        assert result["family_notified"] is True
        assert "跟伟伦讲" in result["tell_her"]

    def test_it_keeps_her_on_the_line(self, memory: CallMemory) -> None:
        assert tool(memory, "flag_concern")("pain", "胸口闷")["stay_on_the_line"]


class TestGuidanceRidesAlong:
    """Tool responses are the only channel that reaches the agent mid-call
    without her hearing it (FINDINGS.md)."""

    def test_every_tool_carries_current_guidance(self, memory: CallMemory) -> None:
        memory.affect = AffectState(energy=Energy.DEPLETED)

        for name in ("get_pending_ask", "get_open_threads", "note_preference"):
            call = tool(memory, name)
            result = (
                call("hearing", "左耳不好") if name == "note_preference" else call()
            )

            assert "提早结束是好事" in result["_guidance"]

    def test_the_guidance_changes_with_her_state(self, memory: CallMemory) -> None:
        memory.affect = AffectState(affect=Affect.EXCITED)
        excited = tool(memory, "get_open_threads")()["_guidance"]

        memory.affect = AffectState(energy=Energy.DEPLETED)
        depleted = tool(memory, "get_open_threads")()["_guidance"]

        assert excited != depleted
        assert "不要打断" in excited

    def test_guidance_never_names_the_state(self, memory: CallMemory) -> None:
        memory.affect = AffectState(energy=Energy.DEPLETED)

        result = tool(memory, "get_open_threads")()

        assert "depleted" not in result["_guidance"]
