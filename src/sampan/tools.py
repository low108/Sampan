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
    # Called the moment a concern is raised, so a fall reaches the family
    # before she hangs up. Without it, flag_concern would tell her something
    # untrue.
    on_concern: Callable[[str, str], None] | None = None
    # Reaches her own words, not just what was extracted from them.
    search_transcripts: Callable[[str], list[dict[str, Any]]] | None = None
    # She asked for something to be forgotten. Honoured, not queued.
    on_forget: Callable[[str], None] | None = None
    forget_requests: list[str] = field(default_factory=list)


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
        """Check whether family left a question for her. Use at the start.

        Always say who asked. The credit is theirs, not yours.
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
                "say_it_like": f"{memory.ask.from_name} asked: {memory.ask.question}",
            },
        )

    def get_open_threads() -> dict[str, Any]:
        """Subjects left unfinished last time, ordered by what to raise first."""
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
        """Look up a person, place or thing she has mentioned before.

        Args:
            query: the name to look for, e.g. "Ah Chwee", "Jalan Bandar".
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
        # Extracted records lose sequence, context and affect, so the graph is
        # only an index — her own words are the thing worth reaching.
        said = (
            memory.search_transcripts(needle)
            if needle and memory.search_transcripts is not None
            else []
        )
        return _with_guidance(memory, {"found": hits[:5], "she_said": said})

    def note_preference(kind: str, value: str) -> dict[str, Any]:
        """Note how she likes to be treated. **Never say it out loud.**

        Args:
            kind: one of hearing / pace / session_length / best_time /
                question_style / silence_tolerance / topic_favourite /
                listen_talk_ratio.
            value: one short phrase, e.g. "left ear is weak".
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
        """Keep a piece of what she just said, so it is not lost.

        Args:
            topic: a short label.
            detail: what she said, in her words.
        """
        memory.fragments.append({"topic": topic, "detail": detail})
        return _with_guidance(memory, {"saved": True})

    def mark_private(topic: str) -> dict[str, Any]:
        """Use when she says something should not be shown to the family.

        Do it. Do not ask why, and do not talk her out of it.

        Args:
            topic: which thing she means.
        """
        memory.private_marks.append(topic)
        return _with_guidance(
            memory, {"private": True, "tell_her": "Alright, I won't write that down."}
        )

    def what_do_you_remember(about: str = "") -> dict[str, Any]:
        """Use when she asks "what do you remember about me?" Answer honestly.

        She has a right to know what is held about her. Say it in ordinary
        words; do not read out a list.

        Args:
            about: a particular subject she asked about, e.g. "my sister".
                Leave empty for everything.
        """
        needle = about.strip()
        people = [
            e.canonical_name
            for e in memory.entities
            if e.type.value == "person" and (not needle or needle in e.canonical_name)
        ]
        places = [
            e.canonical_name
            for e in memory.entities
            if e.type.value == "place" and (not needle or needle in e.canonical_name)
        ]
        unfinished = [
            t.topic for t in memory.threads if not needle or needle in t.topic
        ]
        return _with_guidance(
            memory,
            {
                "people": people[:8],
                "places": places[:8],
                "unfinished": unfinished[:5],
                "how_you_talk_to_her": [p.value for p in memory.preferences],
                "tell_her": (
                    "Answer plainly. If she wants any of it gone, use "
                    "forget_this — do not talk her out of it."
                ),
            },
        )

    def forget_this(subject: str) -> dict[str, Any]:
        """Use when she says "don't keep that" or "forget it".

        Do it. Do not ask why, do not argue, do not explain why you kept it.

        Args:
            subject: what she wants forgotten, in her words.
        """
        memory.forget_requests.append(subject)
        done = False
        if memory.on_forget is not None:
            try:
                memory.on_forget(subject)
                done = True
            except Exception:
                done = False
        return _with_guidance(
            memory,
            {
                "forgotten": done,
                "tell_her": (
                    "Alright, I have taken it out."
                    if done
                    else "Alright, I won't bring it up again."
                ),
            },
        )

    def flag_concern(kind: str, detail: str) -> dict[str, Any]:
        """Use when she mentions a fall, chest pain, breathlessness, or that life
        is not worth living.

        Afterwards tell her honestly that you are letting her family know.
        Never do it behind her back.

        Args:
            kind: fall / pain / breathing / hopelessness / confusion / other
            detail: what she said.
        """
        memory.concerns.append({"kind": kind, "detail": detail})
        delivered = False
        if memory.on_concern is not None:
            try:
                memory.on_concern(kind, detail)
                delivered = True
            except Exception:
                # Say only what is true. If it did not reach the family, the
                # agent must not tell her that it did.
                delivered = False
        return _with_guidance(
            memory,
            {
                "family_notified": delivered,
                "tell_her": (
                    "Ah Ma, I have noted this down so Wei Lun will see it."
                    if delivered
                    else "Ah Ma, I have noted this down."
                ),
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
        what_do_you_remember,
        forget_this,
        flag_concern,
    ]
