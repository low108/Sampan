"""Thread folding — pure logic, no model call.

The behaviour the demo depends on: after a conversation cut short by the
doorbell, the coffee-shop thread is open *and* flagged interrupted, so the next
call can open with 「,door」.
"""

from __future__ import annotations

import pytest

from sampan.models import (
    Closure,
    ClosureReason,
    Thread,
    ThreadAction,
    ThreadStatus,
    ThreadUpdate,
)
from sampan.threads import fold_threads, open_threads, rank_for_opener


def update(
    topic: str, action: ThreadAction = ThreadAction.OPENED, left_off_at: str = ""
) -> ThreadUpdate:
    return ThreadUpdate(topic=topic, action=action, left_off_at=left_off_at)


def closure(
    reason: ClosureReason, active_topic: str = "", evidence: str = ""
) -> Closure:
    return Closure(reason=reason, active_topic=active_topic, evidence=evidence)


NATURAL = closure(ClosureReason.NATURAL)


class TestOpeningAndAdvancing:
    def test_a_new_topic_becomes_an_open_thread(self) -> None:
        threads = fold_threads(
            [],
            [update("father's coffee shop", left_off_at="how the shop came to close")],
            NATURAL,
            conversation_id="conv_001",
        )

        assert len(threads) == 1
        assert threads[0].status is ThreadStatus.OPEN
        assert threads[0].opened_in == "conv_001"
        assert threads[0].left_off_at == "how the shop came to close"

    def test_advancing_reuses_the_existing_thread(self) -> None:
        first = fold_threads(
            [], [update("father's coffee shop")], NATURAL, conversation_id="conv_001"
        )

        second = fold_threads(
            first,
            [
                update(
                    "father's coffee shop",
                    ThreadAction.ADVANCED,
                    "what happened after the shop closed",
                )
            ],
            NATURAL,
            conversation_id="conv_002",
        )

        assert len(second) == 1
        assert second[0].touch_count == 2
        assert second[0].last_touched == "conv_002"
        assert second[0].left_off_at == "what happened after the shop closed"

    def test_a_drifting_label_still_matches(self) -> None:
        """She calls it father's coffee shop one week and the coffee shop the next."""
        first = fold_threads(
            [], [update("father's coffee shop")], NATURAL, conversation_id="conv_001"
        )

        second = fold_threads(
            first,
            [update("the coffee shop", ThreadAction.ADVANCED)],
            NATURAL,
            conversation_id="conv_002",
        )

        assert len(second) == 1

    def test_closing_a_thread_takes_it_out_of_the_open_set(self) -> None:
        first = fold_threads(
            [], [update("the wedding photograph")], NATURAL, conversation_id="conv_001"
        )

        second = fold_threads(
            first,
            [update("the wedding photograph", ThreadAction.CLOSED)],
            NATURAL,
            conversation_id="conv_002",
        )

        assert open_threads(second) == []

    def test_does_not_mutate_the_threads_it_was_given(self) -> None:
        existing = fold_threads(
            [], [update("the coffee shop")], NATURAL, conversation_id="conv_001"
        )

        fold_threads(
            existing,
            [update("the coffee shop", ThreadAction.CLOSED)],
            NATURAL,
            conversation_id="conv_002",
        )

        assert existing[0].status is ThreadStatus.OPEN


class TestInterruption:
    """The distinction the whole module exists for."""

    def test_the_doorbell_flags_the_thread_she_was_on(self) -> None:
        threads = fold_threads(
            [],
            [
                update(
                    "father's coffee shop",
                    left_off_at="what happened after the shop closed",
                )
            ],
            closure(
                ClosureReason.INTERRUPTED,
                active_topic="father's coffee shop",
                evidence="wait, someone is at the door",
            ),
            conversation_id="conv_004",
        )

        assert threads[0].interrupted is True

    def test_tiredness_leaves_the_thread_open_but_not_interrupted(self) -> None:
        """She was not cut off; the story is finished for today. Reopening it
        as though she were interrupted reads as nagging."""
        threads = fold_threads(
            [],
            [update("father's coffee shop")],
            closure(ClosureReason.FATIGUE, evidence="a little bit tired"),
            conversation_id="conv_002",
        )

        assert threads[0].status is ThreadStatus.OPEN
        assert threads[0].interrupted is False

    @pytest.mark.parametrize(
        "reason",
        [ClosureReason.NATURAL, ClosureReason.REFUSED, ClosureReason.UNKNOWN],
    )
    def test_no_other_ending_marks_an_interruption(self, reason: ClosureReason) -> None:
        threads = fold_threads(
            [], [update("the coffee shop")], closure(reason), conversation_id="conv_001"
        )

        assert threads[0].interrupted is False

    def test_only_the_active_topic_is_flagged(self) -> None:
        threads = fold_threads(
            [],
            [update("Ah Gong's crossing"), update("father's coffee shop")],
            closure(ClosureReason.INTERRUPTED, active_topic="father's coffee shop"),
            conversation_id="conv_004",
        )

        flagged = [t.topic for t in threads if t.interrupted]
        assert flagged == ["father's coffee shop"]

    def test_falls_back_to_the_last_thread_touched(self) -> None:
        """If the model can't name what she was on, the most recent thread is
        the best available guess."""
        threads = fold_threads(
            [],
            [update("Ah Gong's crossing"), update("father's coffee shop")],
            closure(ClosureReason.INTERRUPTED),
            conversation_id="conv_004",
        )

        assert [t.topic for t in threads if t.interrupted] == ["father's coffee shop"]

    def test_an_interruption_is_cleared_once_she_returns_to_it(self) -> None:
        interrupted = fold_threads(
            [],
            [update("the coffee shop")],
            closure(ClosureReason.INTERRUPTED, active_topic="the coffee shop"),
            conversation_id="conv_004",
        )
        assert interrupted[0].interrupted is True

        resumed = fold_threads(
            interrupted,
            [update("the coffee shop", ThreadAction.ADVANCED)],
            closure(ClosureReason.FATIGUE),
            conversation_id="conv_005",
        )

        assert resumed[0].interrupted is False

    def test_a_thread_closed_in_the_same_call_is_not_interrupted(self) -> None:
        threads = fold_threads(
            [],
            [update("the coffee shop", ThreadAction.CLOSED)],
            closure(ClosureReason.INTERRUPTED, active_topic="the coffee shop"),
            conversation_id="conv_004",
        )

        assert threads[0].interrupted is False

    def test_an_untouched_thread_keeps_its_earlier_interruption(self) -> None:
        """A thread she didn't revisit this call is still where she left it."""
        old = [
            Thread(
                thread_id="thr_old",
                topic="Ah Gong's crossing",
                interrupted=True,
                last_touched="conv_001",
            )
        ]

        threads = fold_threads(
            old, [update("the coffee shop")], NATURAL, conversation_id="conv_002"
        )

        assert (
            next(t for t in threads if t.topic == "Ah Gong's crossing").interrupted
            is True
        )


class TestRanking:
    def test_an_interrupted_thread_outranks_everything(self) -> None:
        threads = fold_threads(
            [],
            [
                update("Ah Gong's crossing"),
                update("the wedding photograph"),
                update("father's coffee shop"),
            ],
            closure(ClosureReason.INTERRUPTED, active_topic="father's coffee shop"),
            conversation_id="conv_004",
        )

        assert rank_for_opener(threads)[0].topic == "father's coffee shop"

    def test_closed_threads_are_never_offered(self) -> None:
        threads = fold_threads(
            [],
            [
                update("the wedding photograph", ThreadAction.CLOSED),
                update("Ah Gong's crossing"),
            ],
            NATURAL,
            conversation_id="conv_001",
        )

        assert [t.topic for t in rank_for_opener(threads)] == ["Ah Gong's crossing"]
