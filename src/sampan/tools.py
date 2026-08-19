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
from sampan.facts import Fact
from sampan.models import (
    AffectState,
    Ask,
    Entity,
    Preference,
    PreferenceObservation,
    SensitiveTopic,
    Thread,
)
from sampan.preferences import may_raise
from sampan.retrieval import FactGraph, search_facts
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
    # The edges of the graph, loaded before the call. Retrieval reads these.
    facts: list[Fact] = field(default_factory=list)
    # One subject the call may lean toward, carried from the session plan. It
    # rides on tool responses because that is the only channel reaching the
    # agent mid-call without her hearing it.
    target_domain: str = ""
    # Entities named so far in *this* conversation. They seed the graph
    # traversal, which is how agent-initiated retrieval still reflects where
    # the conversation already is -- nothing can be injected per turn.
    mentioned: list[str] = field(default_factory=list)

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
    if memory.target_domain:
        # Phrased as an observation, never a request. The agent is told where
        # she has not been, not where to take her.
        payload["_not_yet_spoken_of"] = memory.target_domain
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

    def remember(query: str) -> dict[str, Any]:
        """Look up what is known about a person, place or thing she mentioned.

        Use it when she refers to something she has spoken about before and you
        need to know what was already said. If nothing comes back, say so --
        do not pretend to remember.

        Args:
            query: the name to look for, e.g. "Ah Chwee", "Jalan Bandar".
        """
        needle = query.strip()
        if not needle:
            return _with_guidance(
                memory, {"known": [], "she_said": [], "unfinished": []}
            )

        # Seeds are the thing asked about plus everyone already named in this
        # call, so the same query answers differently depending on where the
        # conversation has been.
        matched = [
            e.entity_id
            for e in memory.entities
            if e.merged_into is None and e.knows(needle)
        ] or [
            e.entity_id
            for e in memory.entities
            if e.merged_into is None and needle.lower() in e.canonical_name.lower()
        ]
        seeds = list(dict.fromkeys([*matched, *memory.mentioned]))

        facts = search_facts(
            needle, FactGraph(facts=memory.facts, entities=memory.entities), seeds=seeds
        )

        # The graph is an index. Her own words are the thing worth reaching --
        # extracted records lose sequence, context and affect.
        said = (
            memory.search_transcripts(needle)
            if memory.search_transcripts is not None
            else []
        )

        unfinished = [
            t.topic
            for t in rank_for_opener(memory.threads)
            if may_raise(t.topic, memory.sensitivities)
            and (needle.lower() in t.topic.lower() or not facts)
        ]

        if needle not in memory.mentioned:
            memory.mentioned.append(needle)

        return _with_guidance(
            memory,
            {
                "known": [{"fact": f.render(), "she_said": f.quote} for f in facts],
                "she_said": said,
                "unfinished": unfinished[:3],
            },
        )

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

    # Five, down from nine. `recall`, `get_open_threads` and
    # `what_do_you_remember` are one `remember` call now; `note_preference` and
    # `save_fragment` are gone because the Archivist infers both from the
    # transcript afterwards, and it does so better than an agent noticing
    # mid-conversation while trying to listen.
    return [
        get_pending_ask,
        remember,
        mark_private,
        forget_this,
        flag_concern,
    ]
