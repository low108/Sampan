"""Preferences and sensitive topics — pure logic, no model call.

The behaviour session 6 depends on: after she says "talk about something else" about
her sister,
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
            [observed(PreferenceType.HEARING, "left ear is weak")],
            conversation_id="conv_001",
        )

        assert prefs[0].value == "left ear is weak"
        assert prefs[0].first_seen_in == "conv_001"

    def test_seeing_it_again_raises_confidence(self) -> None:
        first = fold_preferences(
            [],
            [observed(PreferenceType.BEST_TIME, "morning", 0.6)],
            conversation_id="conv_001",
        )

        second = fold_preferences(
            first,
            [observed(PreferenceType.BEST_TIME, "morning", 0.6)],
            conversation_id="conv_003",
        )

        assert second[0].observations == 2
        assert second[0].confidence > 0.6
        assert second[0].last_seen_in == "conv_003"

    def test_a_more_confident_contradiction_replaces_the_value(self) -> None:
        first = fold_preferences(
            [],
            [observed(PreferenceType.PACE, "speak faster", 0.4)],
            conversation_id="conv_001",
        )

        second = fold_preferences(
            first,
            [observed(PreferenceType.PACE, "speak more slowly", 0.9)],
            conversation_id="conv_002",
        )

        assert second[0].value == "speak more slowly"

    def test_a_weaker_contradiction_does_not(self) -> None:
        first = fold_preferences(
            [],
            [observed(PreferenceType.PACE, "speak more slowly", 0.9)],
            conversation_id="conv_001",
        )

        second = fold_preferences(
            first,
            [observed(PreferenceType.PACE, "speak faster", 0.3)],
            conversation_id="conv_002",
        )

        assert second[0].value == "speak more slowly"

    def test_one_preference_per_type(self) -> None:
        prefs = fold_preferences(
            [],
            [
                observed(PreferenceType.PACE, "speak more slowly"),
                observed(PreferenceType.PACE, "speak more slowly"),
                observed(PreferenceType.HEARING, "left ear is weak"),
            ],
            conversation_id="conv_001",
        )

        assert len(prefs) == 2

    def test_does_not_mutate_what_it_was_given(self) -> None:
        existing = [
            Preference(
                type=PreferenceType.PACE, value="speak more slowly", confidence=0.5
            )
        ]

        fold_preferences(
            existing,
            [observed(PreferenceType.PACE, "speak more slowly")],
            conversation_id="conv_002",
        )

        assert existing[0].observations == 1


class TestSensitivity:
    def test_one_flat_refusal_is_enough(self) -> None:
        """Saying "talk about something else" is not ambiguous. She should not have to
        say it twice."""
        topics = fold_sensitivities(
            [],
            [signal("sister", REFUSED, "talk about something else")],
            conversation_id="conv_003",
        )

        assert topics[0].do_not_raise is True

    def test_one_soft_deflection_is_not(self) -> None:
        """Drifting onto something else might just be conversation."""
        topics = fold_sensitivities(
            [], [signal("daughter", DEFLECTED)], conversation_id="conv_003"
        )

        assert topics[0].do_not_raise is False
        assert topics[0].sensitive is True

    def test_two_deflections_are(self) -> None:
        first = fold_sensitivities(
            [], [signal("daughter", DEFLECTED)], conversation_id="conv_003"
        )

        second = fold_sensitivities(
            first, [signal("daughter", DEFLECTED)], conversation_id="conv_004"
        )

        assert second[0].do_not_raise is True

    def test_engaging_with_it_later_gives_the_subject_back(self) -> None:
        """She refused to discuss why the shop closed, then told the story
        herself when her son asked. It is hers again."""
        refused = fold_sensitivities(
            [],
            [signal("why the shop closed", REFUSED, "don't talk about this")],
            conversation_id="conv_002",
        )
        assert refused[0].do_not_raise is True

        engaged = fold_sensitivities(
            refused,
            [signal("why the shop closed", ENGAGED)],
            conversation_id="conv_004",
        )

        assert engaged[0].do_not_raise is False

    def test_but_it_stays_marked_sensitive(self) -> None:
        """Still approached gently, even once she has opened it herself."""
        topics = fold_sensitivities(
            [SensitiveTopic(topic="why the shop closed", refusals=1)],
            [signal("why the shop closed", ENGAGED)],
            conversation_id="conv_004",
        )

        assert topics[0].do_not_raise is False
        assert topics[0].sensitive is True

    def test_a_drifting_label_matches_an_existing_topic(self) -> None:
        first = fold_sensitivities(
            [], [signal("sister", DEFLECTED)], conversation_id="conv_003"
        )

        second = fold_sensitivities(
            first, [signal("my sister", DEFLECTED)], conversation_id="conv_005"
        )

        assert len(second) == 1
        assert second[0].do_not_raise is True

    def test_records_the_line_that_showed_it(self) -> None:
        topics = fold_sensitivities(
            [],
            [signal("sister", REFUSED, "talk about something else")],
            conversation_id="conv_003",
        )

        assert topics[0].evidence == "talk about something else"


class TestGating:
    def test_the_agent_may_not_open_a_refused_subject(self) -> None:
        topics = fold_sensitivities(
            [], [signal("sister", REFUSED)], conversation_id="conv_003"
        )

        assert may_raise("sister", topics) is False

    def test_anything_unmentioned_is_open(self) -> None:
        assert may_raise("the coffee shop", []) is True

    def test_lists_what_must_not_be_raised(self) -> None:
        topics = fold_sensitivities(
            [],
            [signal("sister", REFUSED), signal("the coffee shop", ENGAGED)],
            conversation_id="conv_003",
        )

        assert [t.topic for t in do_not_raise(topics)] == ["sister"]


class TestInstructionRendering:
    """The visible proof of memory: this string differs between sessions."""

    def test_an_unseeded_agent_carries_nothing(self) -> None:
        assert describe_for_instruction([], []) == ""

    def test_learned_preferences_reach_the_instruction(self) -> None:
        prefs = fold_preferences(
            [],
            [observed(PreferenceType.HEARING, "left ear is weak")],
            conversation_id="conv_001",
        )

        rendered = describe_for_instruction(prefs, [])

        assert "left ear is weak" in rendered

    def test_a_refused_subject_reaches_the_instruction(self) -> None:
        topics = fold_sensitivities(
            [], [signal("sister", REFUSED)], conversation_id="conv_003"
        )

        rendered = describe_for_instruction([], topics)

        assert "sister" in rendered
        assert "Do not raise these subjects yourself" in rendered

    def test_a_subject_she_reopened_is_not_listed(self) -> None:
        topics = fold_sensitivities(
            [SensitiveTopic(topic="why the shop closed", refusals=1, engagements=1)],
            [],
            conversation_id="conv_005",
        )

        assert "the shop closing" not in describe_for_instruction([], topics)

    def test_the_instruction_carries_no_quotes_back_to_her(self) -> None:
        """Evidence is kept for the family-facing view and for debugging, but
        must not reach the agent's mouth. An agent that can quote "talk about
        something else"
        back at her is a surveillance device, not company."""
        topics = fold_sensitivities(
            [],
            [signal("sister", REFUSED, "talk about something else")],
            conversation_id="conv_003",
        )
        prefs = fold_preferences(
            [],
            [
                PreferenceObservation(
                    type=PreferenceType.HEARING,
                    value="left ear is weak",
                    evidence="speak louder, my left ear is not good",
                    confidence=0.9,
                )
            ],
            conversation_id="conv_001",
        )

        rendered = describe_for_instruction(prefs, topics)

        assert "talk about something else" not in rendered
        assert "speak louder" not in rendered

    def test_the_instruction_tells_the_agent_to_stay_quiet_about_it(self) -> None:
        prefs = fold_preferences(
            [],
            [observed(PreferenceType.HEARING, "left ear is weak")],
            conversation_id="conv_001",
        )

        assert "do not say them" in describe_for_instruction(prefs, [])
