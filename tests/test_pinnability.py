"""The pinnability rubric — pure logic, no model call.

Deliberately fast and exact: the threshold is a product decision, and it is the
rule most likely to break subtly when the extraction prompt changes.
"""

from __future__ import annotations

import pytest

from sampan.models import (
    Domain,
    Emotion,
    PersonMention,
    PinType,
    Precision,
    StoryCandidate,
    StoryStatus,
    When,
    Where,
    assess,
)


def story(
    *,
    where: str = "Sungai Siput",
    raw_phrase: str = "when I was six or seven",
    who: bool = True,
    what: str = "I went catching fish in the river with Ah Chwee",
    sense: str = "he fell in and got soaked",
    why: str = "it was the last year before I had to start working",
) -> StoryCandidate:
    """A complete story, with fields removable one at a time."""
    return StoryCandidate(
        title="catching fish at the river",
        domain=Domain.PLAY,
        narrative="That river, we went every afternoon after school……",
        when=When(raw_phrase=raw_phrase, precision=Precision.RELATIVE, confidence=0.7),
        where=Where(raw_name=where, confidence=0.8),
        who=[PersonMention(surface_form="Ah Chwee", role="neighbour", confidence=0.9)]
        if who
        else [],
        what=what,
        sense_detail=sense,
        why_it_matters=why,
        emotion=Emotion(valence=0.6, labels=["joy"]),
        pin_type=PinType.PLACE,
    )


class TestScoring:
    def test_a_complete_story_scores_six_and_pins(self) -> None:
        scored = assess(story())

        assert scored.score == 6
        assert scored.status == StoryStatus.PINNABLE
        assert scored.missing_fields == []

    def test_four_of_six_is_enough_to_pin(self) -> None:
        scored = assess(story(sense="", why=""))

        assert scored.score == 4
        assert scored.status == StoryStatus.PINNABLE

    def test_three_of_six_is_a_fragment(self) -> None:
        scored = assess(story(sense="", why="", who=False))

        assert scored.score == 3
        assert scored.status == StoryStatus.FRAGMENT


class TestMandatoryFields:
    @pytest.mark.parametrize(
        ("kwarg", "missing"), [("where", "where"), ("raw_phrase", "when")]
    )
    def test_where_and_when_are_mandatory_however_high_the_score(
        self, kwarg: str, missing: str
    ) -> None:
        """A story with five of six fields still cannot go on a map without a
        place and a time."""
        scored = assess(story(**{kwarg: ""}))  # type: ignore[arg-type]

        assert scored.score == 5
        assert scored.status == StoryStatus.FRAGMENT
        assert missing in scored.missing_fields


class TestMissingFields:
    def test_names_what_a_later_session_should_ask_about(self) -> None:
        """A fragment missing `when` becomes next session's
        「the coffee shop — before I married?」"""
        scored = assess(story(raw_phrase="", why=""))

        assert set(scored.missing_fields) == {"when", "why"}

    def test_an_era_counts_as_a_when(self) -> None:
        """'During the Emergency' is a time. Elders rarely give years."""
        scored = assess(story(raw_phrase="during the Emergency"))

        assert "when" not in scored.missing_fields
        assert scored.status == StoryStatus.PINNABLE

    def test_whitespace_is_not_a_field(self) -> None:
        scored = assess(story(sense="   "))

        assert "sense" in scored.missing_fields
