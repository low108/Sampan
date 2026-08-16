"""Preferences and sensitive topics — the layer that makes session 20 differ
from session 1.

Both are silent feedback capture. She never has to tell the agent she is hard
of hearing, or that she does not want to talk about her sister; it notices and
stops. That is the whole 'adapts to the user's way of thinking' requirement,
and it is deliberately invisible — an agent that announces what it has learned
about you is unsettling rather than attentive.
"""

from __future__ import annotations

from sampan.models import (
    AvoidanceKind,
    Preference,
    PreferenceObservation,
    SensitiveTopic,
    TopicSignal,
    normalise,
)


def fold_preferences(
    existing: list[Preference],
    observations: list[PreferenceObservation],
    *,
    conversation_id: str,
) -> list[Preference]:
    """Merge one conversation's observations into the accumulated set.

    Repetition raises confidence; a more confident contradiction replaces the
    value. One preference per type — the instruction has room for a fact, not
    for a debate.
    """
    known = {p.type: p.model_copy(deep=True) for p in existing}

    for observation in observations:
        current = known.get(observation.type)
        if current is None:
            known[observation.type] = Preference(
                type=observation.type,
                value=observation.value,
                confidence=observation.confidence,
                evidence=observation.evidence,
                first_seen_in=conversation_id,
                last_seen_in=conversation_id,
            )
            continue

        current.observations += 1
        current.last_seen_in = conversation_id
        if normalise(observation.value) == normalise(current.value):
            current.confidence = min(1.0, current.confidence + 0.15)
        elif observation.confidence > current.confidence:
            current.value = observation.value
            current.confidence = observation.confidence
            current.evidence = observation.evidence

    return list(known.values())


def _matches(topic: str, known: SensitiveTopic) -> bool:
    a, b = normalise(topic), normalise(known.topic)
    return bool(a) and bool(b) and (a == b or a in b or b in a)


def fold_sensitivities(
    existing: list[SensitiveTopic],
    signals: list[TopicSignal],
    *,
    conversation_id: str,
) -> list[SensitiveTopic]:
    """Record how she responded to each topic raised."""
    topics = [t.model_copy(deep=True) for t in existing]

    for signal in signals:
        match = next((t for t in topics if _matches(signal.topic, t)), None)
        if match is None:
            match = SensitiveTopic(topic=signal.topic, first_seen_in=conversation_id)
            topics.append(match)

        match.last_seen_in = conversation_id
        if signal.kind is AvoidanceKind.REFUSED:
            match.refusals += 1
        elif signal.kind is AvoidanceKind.DEFLECTED:
            match.deflections += 1
        else:
            match.engagements += 1
        if signal.evidence:
            match.evidence = signal.evidence

    return topics


def do_not_raise(topics: list[SensitiveTopic]) -> list[SensitiveTopic]:
    """Subjects the agent must not bring up on its own."""
    return [t for t in topics if t.do_not_raise]


def may_raise(topic: str, topics: list[SensitiveTopic]) -> bool:
    """Whether the agent may open this subject unprompted.

    She may always raise it herself — this gates the agent, never her.
    """
    match = next((t for t in topics if _matches(topic, t)), None)
    return match is None or not match.do_not_raise


def describe_for_instruction(
    preferences: list[Preference], topics: list[SensitiveTopic]
) -> str:
    """Render the learned layer into the Companion's system instruction.

    This string is the visible proof of memory: diffing it between session 1
    and session 5 shows the agent has changed because of what it heard.
    """
    lines: list[str] = []

    if preferences:
        lines.append("你已经知道的事(不要讲出来,做到就好):")
        for preference in sorted(preferences, key=lambda p: p.type.value):
            lines.append(f"- {preference.type.value}: {preference.value}")

    avoid = do_not_raise(topics)
    if avoid:
        lines.append("")
        lines.append("这些话题不要主动提起。她自己讲就顺着她讲:")
        for topic in avoid:
            lines.append(f"- {topic.topic}")

    return "\n".join(lines)
