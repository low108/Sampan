"""Open threads — the unfinished stories the agent comes back to.

The single most valuable memory feature and among the cheapest: opening a call
with 「上次讲到一半,隔壁的来按门铃,你说改天再讲」 proves more about memory in
one sentence than any amount of retrieval.

The distinction this module exists to preserve is *why* a thread was left open.
A doorbell means she was mid-story and wants to return. Tiredness means the
story is done for today, and reopening it reads as nagging.
"""

from __future__ import annotations

import uuid

from sampan.models import (
    Closure,
    ClosureReason,
    Thread,
    ThreadAction,
    ThreadStatus,
    ThreadUpdate,
    normalise,
)


def _matches(topic: str, thread: Thread) -> bool:
    """Topic labels drift between sessions — 爸爸的咖啡店 one week, 咖啡店 the
    next. Match on containment rather than equality."""
    a, b = normalise(topic), normalise(thread.topic)
    if not a or not b:
        return False
    return a == b or a in b or b in a


def _find(topic: str, threads: list[Thread]) -> Thread | None:
    matches = [t for t in threads if _matches(topic, t)]
    if not matches:
        return None
    # Prefer an open thread; a closed one with the same label is history.
    open_matches = [t for t in matches if t.status is ThreadStatus.OPEN]
    return (open_matches or matches)[0]


def fold_threads(
    existing: list[Thread],
    updates: list[ThreadUpdate],
    closure: Closure,
    *,
    conversation_id: str,
) -> list[Thread]:
    """Apply one conversation's thread movements to the carried-over set."""
    threads = [t.model_copy(deep=True) for t in existing]

    for update in updates:
        thread = _find(update.topic, threads)

        if thread is None:
            thread = Thread(
                thread_id=f"thr_{uuid.uuid4().hex[:12]}",
                topic=update.topic,
                opened_in=conversation_id,
            )
            threads.append(thread)

        thread.last_touched = conversation_id
        thread.touch_count += 1
        if update.left_off_at:
            thread.left_off_at = update.left_off_at

        if update.action is ThreadAction.CLOSED:
            thread.status = ThreadStatus.CLOSED
            thread.interrupted = False
        else:
            thread.status = ThreadStatus.OPEN

    _mark_interruption(threads, closure, conversation_id)
    return threads


def _mark_interruption(
    threads: list[Thread], closure: Closure, conversation_id: str
) -> None:
    """Flag the thread she was actually on when the call was cut short.

    Only ever set for an external interruption. Fatigue leaves threads open but
    not interrupted, because the two call for opposite behaviour next time.
    """
    touched = [t for t in threads if t.last_touched == conversation_id]
    for thread in touched:
        thread.interrupted = False

    if closure.reason is not ClosureReason.INTERRUPTED:
        return

    candidates = [t for t in touched if t.status is ThreadStatus.OPEN]
    if not candidates:
        return

    named = _find(closure.active_topic, candidates) if closure.active_topic else None
    # Fall back to the last thread touched: that is what she was on.
    (named or candidates[-1]).interrupted = True


def open_threads(threads: list[Thread]) -> list[Thread]:
    return [t for t in threads if t.status is ThreadStatus.OPEN]


def rank_for_opener(threads: list[Thread]) -> list[Thread]:
    """Order candidate threads for the next call's opening offer.

    An interrupted thread outranks everything: she was cut off mid-sentence and
    saying so proves the agent was listening. Ticket 12 layers affect gating and
    the family ask on top of this ordering.
    """
    return sorted(
        open_threads(threads),
        key=lambda t: (not t.interrupted, -t.touch_count, t.topic),
    )
