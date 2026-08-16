"""Preferences and sensitive topics — pure logic, no model call.

The behaviour session 6 depends on: after she says 「讲别的」 about her sister,
the agent never raises her again — so that when she brings her up herself,
three sessions later, it lands.
"""

from __future__ import annotations

from sampan.models import (
    AvoidanceKind,
    Preference,
    PreferenceObservation,
    PreferenceType,
    SensitiveTopic,
    TopicSignal,
)
from sampan.preferences import (
    describe_for_instruction,
    do_not_raise,
    fold_preferences,
    fold_sensitivities,
    may_raise,
)


def observed(
    kind: PreferenceType, value: str, confidence: float = 0.7
) -> PreferenceObservation:
    return PreferenceObservation(type=kind, value=value, confidence=confidence)


def signal(topic: str, kind: AvoidanceKind, evidence: str = "") -> TopicSignal:
    return TopicSignal(topic=topic, kind=kind, evidence=evidence)


REFUSED = AvoidanceKind.REFUSED
DEFLECTED = AvoidanceKind.DEFLECTED
ENGAGED = AvoidanceKind.ENGAGED


class TestFoldingPreferences:
    def test_a_new_preference_is_recorded_with_its_source(self) -> None:
        prefs = fold_preferences(
            [],
            [observed(PreferenceType.HEARING, "左耳不好")],
            conversation_id="conv_001",
        )

        assert prefs[0].value == "左耳不好"
        assert prefs[0].first_seen_in == "conv_001"

    def test_seeing_it_again_raises_confidence(self) -> None:
        first = fold_preferences(
            [],
            [observed(PreferenceType.BEST_TIME, "早上", 0.6)],
            conversation_id="conv_001",
        )

        second = fold_preferences(
            first,
            [observed(PreferenceType.BEST_TIME, "早上", 0.6)],
            conversation_id="conv_003",
        )

        assert second[0].observations == 2
        assert second[0].confidence > 0.6
        assert second[0].last_seen_in == "conv_003"

    def test_a_more_confident_contradiction_replaces_the_value(self) -> None:
        first = fold_preferences(
            [],
            [observed(PreferenceType.PACE, "讲快一点", 0.4)],
            conversation_id="conv_001",
        )

        second = fold_preferences(
            first,
            [observed(PreferenceType.PACE, "讲慢一点", 0.9)],
            conversation_id="conv_002",
        )

        assert second[0].value == "讲慢一点"

    def test_a_weaker_contradiction_does_not(self) -> None:
        first = fold_preferences(
            [],
            [observed(PreferenceType.PACE, "讲慢一点", 0.9)],
            conversation_id="conv_001",
        )

        second = fold_preferences(
            first,
            [observed(PreferenceType.PACE, "讲快一点", 0.3)],
            conversation_id="conv_002",
        )

        assert second[0].value == "讲慢一点"

    def test_one_preference_per_type(self) -> None:
        prefs = fold_preferences(
            [],
            [
                observed(PreferenceType.PACE, "讲慢一点"),
                observed(PreferenceType.PACE, "讲慢一点"),
                observed(PreferenceType.HEARING, "左耳不好"),
            ],
            conversation_id="conv_001",
        )

        assert len(prefs) == 2

    def test_does_not_mutate_what_it_was_given(self) -> None:
        existing = [
            Preference(type=PreferenceType.PACE, value="讲慢一点", confidence=0.5)
        ]

        fold_preferences(
            existing,
            [observed(PreferenceType.PACE, "讲慢一点")],
            conversation_id="conv_002",
        )

        assert existing[0].observations == 1


class TestSensitivity:
    def test_one_flat_refusal_is_enough(self) -> None:
        """「讲别的」 is not ambiguous. She should not have to say it twice."""
        topics = fold_sensitivities(
            [], [signal("姐姐", REFUSED, "讲别的")], conversation_id="conv_003"
        )

        assert topics[0].do_not_raise is True

    def test_one_soft_deflection_is_not(self) -> None:
        """Drifting onto something else might just be conversation."""
        topics = fold_sensitivities(
            [], [signal("女儿", DEFLECTED)], conversation_id="conv_003"
        )

        assert topics[0].do_not_raise is False
        assert topics[0].sensitive is True

    def test_two_deflections_are(self) -> None:
        first = fold_sensitivities(
            [], [signal("女儿", DEFLECTED)], conversation_id="conv_003"
        )

        second = fold_sensitivities(
            first, [signal("女儿", DEFLECTED)], conversation_id="conv_004"
        )

        assert second[0].do_not_raise is True

    def test_engaging_with_it_later_gives_the_subject_back(self) -> None:
        """She refused to discuss why the shop closed, then told the story
        herself when her son asked. It is hers again."""
        refused = fold_sensitivities(
            [],
            [signal("关店的原因", REFUSED, "不要讲这个")],
            conversation_id="conv_002",
        )
        assert refused[0].do_not_raise is True

        engaged = fold_sensitivities(
            refused, [signal("关店的原因", ENGAGED)], conversation_id="conv_004"
        )

        assert engaged[0].do_not_raise is False

    def test_but_it_stays_marked_sensitive(self) -> None:
        """Still approached gently, even once she has opened it herself."""
        topics = fold_sensitivities(
            [SensitiveTopic(topic="关店的原因", refusals=1)],
            [signal("关店的原因", ENGAGED)],
            conversation_id="conv_004",
        )

        assert topics[0].do_not_raise is False
        assert topics[0].sensitive is True

    def test_a_drifting_label_matches_an_existing_topic(self) -> None:
        first = fold_sensitivities(
            [], [signal("姐姐", DEFLECTED)], conversation_id="conv_003"
        )

        second = fold_sensitivities(
            first, [signal("我姐姐", DEFLECTED)], conversation_id="conv_005"
        )

        assert len(second) == 1
        assert second[0].do_not_raise is True

    def test_records_the_line_that_showed_it(self) -> None:
        topics = fold_sensitivities(
            [], [signal("姐姐", REFUSED, "讲别的")], conversation_id="conv_003"
        )

        assert topics[0].evidence == "讲别的"


class TestGating:
    def test_the_agent_may_not_open_a_refused_subject(self) -> None:
        topics = fold_sensitivities(
            [], [signal("姐姐", REFUSED)], conversation_id="conv_003"
        )

        assert may_raise("姐姐", topics) is False

    def test_anything_unmentioned_is_open(self) -> None:
        assert may_raise("咖啡店", []) is True

    def test_lists_what_must_not_be_raised(self) -> None:
        topics = fold_sensitivities(
            [],
            [signal("姐姐", REFUSED), signal("咖啡店", ENGAGED)],
            conversation_id="conv_003",
        )

        assert [t.topic for t in do_not_raise(topics)] == ["姐姐"]


class TestInstructionRendering:
    """The visible proof of memory: this string differs between sessions."""

    def test_an_unseeded_agent_carries_nothing(self) -> None:
        assert describe_for_instruction([], []) == ""

    def test_learned_preferences_reach_the_instruction(self) -> None:
        prefs = fold_preferences(
            [],
            [observed(PreferenceType.HEARING, "左耳不好")],
            conversation_id="conv_001",
        )

        rendered = describe_for_instruction(prefs, [])

        assert "左耳不好" in rendered

    def test_a_refused_subject_reaches_the_instruction(self) -> None:
        topics = fold_sensitivities(
            [], [signal("姐姐", REFUSED)], conversation_id="conv_003"
        )

        rendered = describe_for_instruction([], topics)

        assert "姐姐" in rendered
        assert "不要主动提起" in rendered

    def test_a_subject_she_reopened_is_not_listed(self) -> None:
        topics = fold_sensitivities(
            [SensitiveTopic(topic="关店的原因", refusals=1, engagements=1)],
            [],
            conversation_id="conv_005",
        )

        assert "关店" not in describe_for_instruction([], topics)

    def test_the_instruction_carries_no_quotes_back_to_her(self) -> None:
        """Evidence is kept for the family-facing view and for debugging, but
        must not reach the agent's mouth. An agent that can quote 「讲别的」
        back at her is a surveillance device, not company."""
        topics = fold_sensitivities(
            [], [signal("姐姐", REFUSED, "讲别的")], conversation_id="conv_003"
        )
        prefs = fold_preferences(
            [],
            [
                PreferenceObservation(
                    type=PreferenceType.HEARING,
                    value="左耳不好",
                    evidence="你讲大声一点,我左边耳朵不好",
                    confidence=0.9,
                )
            ],
            conversation_id="conv_001",
        )

        rendered = describe_for_instruction(prefs, topics)

        assert "讲别的" not in rendered
        assert "你讲大声一点" not in rendered

    def test_the_instruction_tells_the_agent_to_stay_quiet_about_it(self) -> None:
        prefs = fold_preferences(
            [],
            [observed(PreferenceType.HEARING, "左耳不好")],
            conversation_id="conv_001",
        )

        assert "不要讲出来" in describe_for_instruction(prefs, [])
