"""Anchors and relative-time resolution — pure logic, no model call."""

from __future__ import annotations

import pytest

from sampan.anchors import apply_anchors, direction, fold_anchors
from sampan.models import Anchor, AnchorCandidate, Precision, When

MARRIAGE = Anchor(anchor_id="anchor_marriage", label="结婚", year=1968, confidence=0.9)
SHOP_CLOSE = Anchor(
    anchor_id="anchor_shop_close", label="关店", year=1969, confidence=0.8
)


def when(
    phrase: str,
    *,
    anchor_ref: str | None = "anchor_marriage",
    start: int | None = None,
    end: int | None = None,
    confidence: float = 0.7,
) -> When:
    return When(
        raw_phrase=phrase,
        start_year=start,
        end_year=end,
        precision=Precision.RELATIVE,
        anchor_ref=anchor_ref,
        confidence=confidence,
    )


class TestDirection:
    @pytest.mark.parametrize("phrase", ["结婚以前", "结婚之前", "还没结婚的时候"])
    def test_reads_before(self, phrase: str) -> None:
        assert direction(phrase) == "before"

    @pytest.mark.parametrize("phrase", ["店关了以后", "结婚之后", "关店过后"])
    def test_reads_after(self, phrase: str) -> None:
        assert direction(phrase) == "after"

    @pytest.mark.parametrize("phrase", ["结婚那年", "那时候", "大水那一年"])
    def test_reads_same_year(self, phrase: str) -> None:
        assert direction(phrase) == "same"

    def test_a_phrase_with_no_marker_gives_no_direction(self) -> None:
        assert direction("小时候") is None


class TestApplyingAnchors:
    def test_before_sets_only_an_upper_bound(self) -> None:
        """How long before is unknown. Inventing a start year would put a
        false date on the timeline."""
        resolved = apply_anchors(when("结婚以前"), [MARRIAGE])

        assert resolved.end_year == 1968
        assert resolved.start_year is None

    def test_after_sets_only_a_lower_bound(self) -> None:
        resolved = apply_anchors(
            when("店关了以后", anchor_ref="anchor_shop_close"), [SHOP_CLOSE]
        )

        assert resolved.start_year == 1969
        assert resolved.end_year is None

    def test_that_year_pins_both_ends(self) -> None:
        resolved = apply_anchors(when("结婚那年"), [MARRIAGE])

        assert (resolved.start_year, resolved.end_year) == (1968, 1968)

    def test_keeps_her_own_words(self) -> None:
        resolved = apply_anchors(when("结婚以前"), [MARRIAGE])

        assert resolved.raw_phrase == "结婚以前"

    def test_never_claims_more_confidence_than_the_anchor(self) -> None:
        resolved = apply_anchors(
            when("结婚以前", confidence=0.95),
            [
                Anchor(
                    anchor_id="anchor_marriage", label="结婚", year=1968, confidence=0.5
                )
            ],
        )

        assert resolved.confidence == 0.5

    def test_leaves_an_already_dated_story_alone(self) -> None:
        """The model often infers a year straight from the transcript, and
        that is better evidence than an anchor offset."""
        resolved = apply_anchors(when("一九五八年", start=1958, end=1958), [MARRIAGE])

        assert (resolved.start_year, resolved.end_year) == (1958, 1958)

    def test_an_unknown_anchor_leaves_the_time_untouched(self) -> None:
        resolved = apply_anchors(when("搬家以前", anchor_ref="anchor_move"), [MARRIAGE])

        assert resolved.start_year is None and resolved.end_year is None

    def test_no_anchor_reference_leaves_the_time_untouched(self) -> None:
        resolved = apply_anchors(when("以前", anchor_ref=None), [MARRIAGE])

        assert resolved.end_year is None

    def test_a_directionless_phrase_is_not_guessed_at(self) -> None:
        resolved = apply_anchors(when("小时候"), [MARRIAGE])

        assert resolved.start_year is None and resolved.end_year is None

    def test_does_not_mutate_the_time_it_was_given(self) -> None:
        original = when("结婚以前")

        apply_anchors(original, [MARRIAGE])

        assert original.end_year is None


class TestFoldingAnchors:
    def test_a_new_anchor_is_recorded_with_its_source(self) -> None:
        anchors = fold_anchors(
            [],
            [
                AnchorCandidate(
                    anchor_id="anchor_marriage", label="结婚", year=1968, confidence=0.9
                )
            ],
            conversation_id="conv_002",
        )

        assert anchors[0].year == 1968
        assert anchors[0].first_seen_in == "conv_002"

    def test_repeating_an_anchor_corroborates_it(self) -> None:
        anchors = fold_anchors(
            [MARRIAGE],
            [
                AnchorCandidate(
                    anchor_id="anchor_marriage", label="结婚", year=1968, confidence=0.6
                )
            ],
            conversation_id="conv_005",
        )

        assert anchors[0].corroborations == 2
        assert anchors[0].confidence > MARRIAGE.confidence

    def test_a_less_confident_disagreement_does_not_move_the_year(self) -> None:
        """Elders misremember. One hesitant mention should not overturn a date
        she stated plainly three sessions ago."""
        anchors = fold_anchors(
            [MARRIAGE],
            [
                AnchorCandidate(
                    anchor_id="anchor_marriage", label="结婚", year=1965, confidence=0.3
                )
            ],
            conversation_id="conv_006",
        )

        assert anchors[0].year == 1968

    def test_a_more_confident_correction_does_move_it(self) -> None:
        anchors = fold_anchors(
            [
                Anchor(
                    anchor_id="anchor_marriage", label="结婚", year=1965, confidence=0.4
                )
            ],
            [
                AnchorCandidate(
                    anchor_id="anchor_marriage",
                    label="结婚",
                    year=1968,
                    confidence=0.95,
                )
            ],
            conversation_id="conv_006",
        )

        assert anchors[0].year == 1968

    def test_does_not_mutate_the_anchors_it_was_given(self) -> None:
        fold_anchors(
            [MARRIAGE],
            [
                AnchorCandidate(
                    anchor_id="anchor_marriage", label="结婚", year=1968, confidence=0.6
                )
            ],
            conversation_id="conv_005",
        )

        assert MARRIAGE.corroborations == 1
