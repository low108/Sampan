"""Thread folding — pure logic, no model call.

The behaviour the demo depends on: after a conversation cut short by the
doorbell, the coffee-shop thread is open *and* flagged interrupted, so the next
call can open with 「上次讲到一半,隔壁的来按门铃」.
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
            [update("爸爸的咖啡店", left_off_at="店后来怎么关的")],
            NATURAL,
            conversation_id="conv_001",
        )

        assert len(threads) == 1
        assert threads[0].status is ThreadStatus.OPEN
        assert threads[0].opened_in == "conv_001"
        assert threads[0].left_off_at == "店后来怎么关的"

    def test_advancing_reuses_the_existing_thread(self) -> None:
        first = fold_threads(
            [], [update("爸爸的咖啡店")], NATURAL, conversation_id="conv_001"
        )

        second = fold_threads(
            first,
            [update("爸爸的咖啡店", ThreadAction.ADVANCED, "关店以后的事")],
            NATURAL,
            conversation_id="conv_002",
        )

        assert len(second) == 1
        assert second[0].touch_count == 2
        assert second[0].last_touched == "conv_002"
        assert second[0].left_off_at == "关店以后的事"

    def test_a_drifting_label_still_matches(self) -> None:
        """She calls it 爸爸的咖啡店 one week and 咖啡店 the next."""
        first = fold_threads(
            [], [update("爸爸的咖啡店")], NATURAL, conversation_id="conv_001"
        )

        second = fold_threads(
            first,
            [update("咖啡店", ThreadAction.ADVANCED)],
            NATURAL,
            conversation_id="conv_002",
        )

        assert len(second) == 1

    def test_closing_a_thread_takes_it_out_of_the_open_set(self) -> None:
        first = fold_threads(
            [], [update("结婚照")], NATURAL, conversation_id="conv_001"
        )

        second = fold_threads(
            first,
            [update("结婚照", ThreadAction.CLOSED)],
            NATURAL,
            conversation_id="conv_002",
        )

        assert open_threads(second) == []

    def test_does_not_mutate_the_threads_it_was_given(self) -> None:
        existing = fold_threads(
            [], [update("咖啡店")], NATURAL, conversation_id="conv_001"
        )

        fold_threads(
            existing,
            [update("咖啡店", ThreadAction.CLOSED)],
            NATURAL,
            conversation_id="conv_002",
        )

        assert existing[0].status is ThreadStatus.OPEN


class TestInterruption:
    """The distinction the whole module exists for."""

    def test_the_doorbell_flags_the_thread_she_was_on(self) -> None:
        threads = fold_threads(
            [],
            [update("爸爸的咖啡店", left_off_at="关店以后的事")],
            closure(
                ClosureReason.INTERRUPTED,
                active_topic="爸爸的咖啡店",
                evidence="等一下,有人按门铃",
            ),
            conversation_id="conv_004",
        )

        assert threads[0].interrupted is True

    def test_tiredness_leaves_the_thread_open_but_not_interrupted(self) -> None:
        """She was not cut off; the story is finished for today. Reopening it
        as though she were interrupted reads as nagging."""
        threads = fold_threads(
            [],
            [update("爸爸的咖啡店")],
            closure(ClosureReason.FATIGUE, evidence="有一点点累"),
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
            [], [update("咖啡店")], closure(reason), conversation_id="conv_001"
        )

        assert threads[0].interrupted is False

    def test_only_the_active_topic_is_flagged(self) -> None:
        threads = fold_threads(
            [],
            [update("阿公过番"), update("爸爸的咖啡店")],
            closure(ClosureReason.INTERRUPTED, active_topic="爸爸的咖啡店"),
            conversation_id="conv_004",
        )

        flagged = [t.topic for t in threads if t.interrupted]
        assert flagged == ["爸爸的咖啡店"]

    def test_falls_back_to_the_last_thread_touched(self) -> None:
        """If the model can't name what she was on, the most recent thread is
        the best available guess."""
        threads = fold_threads(
            [],
            [update("阿公过番"), update("爸爸的咖啡店")],
            closure(ClosureReason.INTERRUPTED),
            conversation_id="conv_004",
        )

        assert [t.topic for t in threads if t.interrupted] == ["爸爸的咖啡店"]

    def test_an_interruption_is_cleared_once_she_returns_to_it(self) -> None:
        interrupted = fold_threads(
            [],
            [update("咖啡店")],
            closure(ClosureReason.INTERRUPTED, active_topic="咖啡店"),
            conversation_id="conv_004",
        )
        assert interrupted[0].interrupted is True

        resumed = fold_threads(
            interrupted,
            [update("咖啡店", ThreadAction.ADVANCED)],
            closure(ClosureReason.FATIGUE),
            conversation_id="conv_005",
        )

        assert resumed[0].interrupted is False

    def test_a_thread_closed_in_the_same_call_is_not_interrupted(self) -> None:
        threads = fold_threads(
            [],
            [update("咖啡店", ThreadAction.CLOSED)],
            closure(ClosureReason.INTERRUPTED, active_topic="咖啡店"),
            conversation_id="conv_004",
        )

        assert threads[0].interrupted is False

    def test_an_untouched_thread_keeps_its_earlier_interruption(self) -> None:
        """A thread she didn't revisit this call is still where she left it."""
        old = [
            Thread(
                thread_id="thr_old",
                topic="阿公过番",
                interrupted=True,
                last_touched="conv_001",
            )
        ]

        threads = fold_threads(
            old, [update("咖啡店")], NATURAL, conversation_id="conv_002"
        )

        assert next(t for t in threads if t.topic == "阿公过番").interrupted is True


class TestRanking:
    def test_an_interrupted_thread_outranks_everything(self) -> None:
        threads = fold_threads(
            [],
            [update("阿公过番"), update("结婚照"), update("爸爸的咖啡店")],
            closure(ClosureReason.INTERRUPTED, active_topic="爸爸的咖啡店"),
            conversation_id="conv_004",
        )

        assert rank_for_opener(threads)[0].topic == "爸爸的咖啡店"

    def test_closed_threads_are_never_offered(self) -> None:
        threads = fold_threads(
            [],
            [update("结婚照", ThreadAction.CLOSED), update("阿公过番")],
            NATURAL,
            conversation_id="conv_001",
        )

        assert [t.topic for t in rank_for_opener(threads)] == ["阿公过番"]
