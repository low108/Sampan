"""What the Companion can do mid-call.

Tools are bound to one call's memory, so they read her real accumulated state
rather than a snapshot baked into the instruction.

They also carry the affect guidance. That is not incidental: a live session
cannot be steered mid-call (see FINDINGS.md), and a tool response is the only
channel that reaches the agent without her hearing it.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from sampan.affect import policy
from sampan.models import (
    AffectState,
    Ask,
    Entity,
    Preference,
    PreferenceObservation,
    PreferenceType,
    SensitiveTopic,
    Thread,
)
from sampan.preferences import may_raise
from sampan.threads import rank_for_opener


@dataclass
class CallMemory:
    """Everything one call can read and everything it records.

    Written back by the Archivist afterwards; the tools only append.
    """

    threads: list[Thread] = field(default_factory=list)
    entities: list[Entity] = field(default_factory=list)
    preferences: list[Preference] = field(default_factory=list)
    sensitivities: list[SensitiveTopic] = field(default_factory=list)
    ask: Ask | None = None
    affect: AffectState = field(default_factory=AffectState)

    # Collected during the call, folded in afterwards.
    noted_preferences: list[PreferenceObservation] = field(default_factory=list)
    fragments: list[dict[str, str]] = field(default_factory=list)
    private_marks: list[str] = field(default_factory=list)
    concerns: list[dict[str, str]] = field(default_factory=list)
    ask_delivered: bool = False


def _with_guidance(memory: CallMemory, payload: dict[str, Any]) -> dict[str, Any]:
    """Attach current behavioural guidance to any tool response.

    The only way to reach the agent mid-call without her hearing it.
    """
    knobs = policy(memory.affect)
    payload["_guidance"] = knobs.guidance
    payload["_turn_length"] = knobs.turn_length
    return payload


def build_tools(memory: CallMemory) -> list[Callable[..., Any]]:
    """Bind the Companion's tools to one call."""

    def get_pending_ask() -> dict[str, Any]:
        """看看有没有家人留话给阿嬷。开场的时候用。

        一定要讲出是谁问的。功劳是家人的,不是你的。
        """
        if memory.ask is None:
            return _with_guidance(memory, {"has_ask": False})
        memory.ask_delivered = True
        return _with_guidance(
            memory,
            {
                "has_ask": True,
                "from_name": memory.ask.from_name,
                "relation": memory.ask.relation,
                "question": memory.ask.question,
                "say_it_like": f"{memory.ask.from_name}问:{memory.ask.question}",
            },
        )

    def get_open_threads() -> dict[str, Any]:
        """上次讲到一半、还没讲完的事,按该先讲哪个排好。"""
        ranked = [
            {
                "topic": t.topic,
                "left_off_at": t.left_off_at,
                "was_interrupted": t.interrupted,
            }
            for t in rank_for_opener(memory.threads)
            if may_raise(t.topic, memory.sensitivities)
        ]
        return _with_guidance(memory, {"threads": ranked[:5]})

    def recall(query: str) -> dict[str, Any]:
        """查一查阿嬷以前讲过的人、地方、东西。

        Args:
            query: 要找的人名、地名或东西,例如「阿水」「板底街」。
        """
        needle = query.strip()
        hits = [
            {"name": e.canonical_name, "type": e.type.value, "detail": e.detail}
            for e in memory.entities
            if needle
            and (
                needle in e.canonical_name
                or any(needle in alias for alias in e.aliases)
                or needle in e.detail
            )
        ]
        return _with_guidance(memory, {"found": hits[:5]})

    def note_preference(kind: str, value: str) -> dict[str, Any]:
        """记下阿嬷喜欢怎样被对待。**不要讲出来**,记下就好。

        Args:
            kind: hearing / pace / session_length / best_time /
                question_style / silence_tolerance / topic_favourite /
                listen_talk_ratio 其中一个。
            value: 短短一句,例如「左耳不好」。
        """
        try:
            preference_type = PreferenceType(kind)
        except ValueError:
            return _with_guidance(memory, {"recorded": False, "reason": "unknown kind"})
        memory.noted_preferences.append(
            PreferenceObservation(type=preference_type, value=value, confidence=0.7)
        )
        return _with_guidance(memory, {"recorded": True})

    def save_fragment(topic: str, detail: str) -> dict[str, Any]:
        """把她刚讲的一小段先记下来,免得漏掉。

        Args:
            topic: 短短一个标题。
            detail: 她讲了什么,用她的话。
        """
        memory.fragments.append({"topic": topic, "detail": detail})
        return _with_guidance(memory, {"saved": True})

    def mark_private(topic: str) -> dict[str, Any]:
        """阿嬷说这件事不要给家里人看的时候用。

        她讲了就照做,不要问为什么,也不要劝她。

        Args:
            topic: 她指的是哪一件事。
        """
        memory.private_marks.append(topic)
        return _with_guidance(
            memory, {"private": True, "tell_her": "好,这个我不写进去。"}
        )

    def flag_concern(kind: str, detail: str) -> dict[str, Any]:
        """阿嬷讲到跌倒、胸口痛、喘不过气、或者活着没意思的时候用。

        用了之后要老实告诉她你会让家人知道 —— 不要瞒着她。

        Args:
            kind: fall / pain / breathing / hopelessness / confusion / other
            detail: 她讲了什么。
        """
        memory.concerns.append({"kind": kind, "detail": detail})
        return _with_guidance(
            memory,
            {
                "family_notified": True,
                "tell_her": "阿嬷,这个我会跟伟伦讲一声,让他知道。",
                "stay_on_the_line": True,
            },
        )

    return [
        get_pending_ask,
        get_open_threads,
        recall,
        note_preference,
        save_fragment,
        mark_private,
        flag_concern,
    ]
