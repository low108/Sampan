"""The affect state machine and response policy — pure logic, no model call.

These are the rules most likely to break subtly, and the ones that decide
whether an eighty-year-old feels understood or interrogated.
"""

from __future__ import annotations

import pytest

from sampan.affect import (
    apply_assessment,
    describe_for_instruction,
    policy,
    wrap_pcm_as_wav,
)
from sampan.models import (
    Affect,
    AffectFlag,
    AffectState,
    Assessment,
    Energy,
    Engagement,
    QuestionStyle,
    TopicAction,
)


def reading(
    energy: Energy = Energy.FRESH,
    engagement: Engagement = Engagement.ENGAGED,
    affect: Affect = Affect.NEUTRAL,
    flags: list[AffectFlag] | None = None,
) -> Assessment:
    return Assessment(
        energy=energy, engagement=engagement, affect=affect, flags=flags or []
    )


def settle(state: AffectState, assessment: Assessment) -> AffectState:
    """Two agreeing readings — what it takes to actually move."""
    return apply_assessment(apply_assessment(state, assessment), assessment)


class TestHysteresis:
    def test_one_odd_reading_does_not_move_the_state(self) -> None:
        """Otherwise the agent lurches every ninety seconds."""
        state = apply_assessment(AffectState(), reading(energy=Energy.DEPLETED))

        assert state.energy is Energy.FRESH

    def test_two_agreeing_readings_do(self) -> None:
        state = settle(AffectState(), reading(energy=Energy.FADING))

        assert state.energy is Energy.FADING

    def test_two_disagreeing_readings_do_not(self) -> None:
        state = apply_assessment(AffectState(), reading(affect=Affect.SAD))
        state = apply_assessment(state, reading(affect=Affect.WARM))

        assert state.affect is Affect.NEUTRAL

    def test_a_reading_that_agrees_with_the_state_clears_the_pending_one(self) -> None:
        state = apply_assessment(AffectState(), reading(affect=Affect.SAD))
        state = apply_assessment(state, reading())

        assert state.pending is None
        assert state.affect is Affect.NEUTRAL

    def test_a_transition_records_why(self) -> None:
        state = settle(
            AffectState(),
            Assessment(
                energy=Energy.FADING,
                engagement=Engagement.ENGAGED,
                affect=Affect.NEUTRAL,
                signals=["sentences getting shorter"],
            ),
        )

        assert any("sentences getting shorter" in entry for entry in state.transitions)


class TestEnergyIsMonotonic:
    def test_energy_does_not_recover_on_its_own(self) -> None:
        """People do not get less tired mid-call."""
        tired = settle(AffectState(), reading(energy=Energy.FADING))

        recovered = settle(tired, reading(energy=Energy.FRESH))

        assert recovered.energy is Energy.FADING

    def test_excitement_partially_reverses_it(self) -> None:
        """She lights up on the right story. That is real, and worth honouring."""
        tired = settle(AffectState(), reading(energy=Energy.FADING))

        lit_up = settle(tired, reading(energy=Energy.FADING, affect=Affect.EXCITED))

        assert lit_up.energy is Energy.FRESH

    def test_energy_still_worsens_freely(self) -> None:
        fading = settle(AffectState(), reading(energy=Energy.FADING))

        assert settle(fading, reading(energy=Energy.DEPLETED)).energy is Energy.DEPLETED


class TestImmediateSignals:
    def test_distress_fires_on_a_single_reading(self) -> None:
        """Waiting for corroboration here is not a trade-off worth making."""
        state = apply_assessment(AffectState(), reading(flags=[AffectFlag.DISTRESS]))

        assert AffectFlag.DISTRESS in state.flags

    def test_agitation_fires_on_a_single_reading(self) -> None:
        """In an elderly person sudden agitation can be pain or infection
        rather than mood."""
        state = apply_assessment(AffectState(), reading(affect=Affect.AGITATED))

        assert state.affect is Affect.AGITATED

    def test_a_flag_that_clears_is_dropped(self) -> None:
        state = apply_assessment(AffectState(), reading(flags=[AffectFlag.LOOPING]))

        assert apply_assessment(state, reading()).flags == []


class TestPolicy:
    def test_distress_keeps_her_on_the_line(self) -> None:
        knobs = policy(AffectState(flags=[AffectFlag.DISTRESS]))

        assert knobs.care_flag == "distress"
        assert "Do not hang up" in knobs.guidance

    def test_confusion_is_validated_never_corrected(self) -> None:
        """Reality-orienting a confused elder is the opposite of the standard
        of care."""
        knobs = policy(AffectState(flags=[AffectFlag.CONFUSED]))

        assert "Do not correct her" in knobs.guidance
        assert "someone has died" in knobs.guidance

    def test_a_repeated_story_is_received_as_new(self) -> None:
        knobs = policy(AffectState(flags=[AffectFlag.LOOPING]))

        assert "already told you" in knobs.guidance
        assert "first time" in knobs.guidance

    def test_agitation_is_never_argued_with(self) -> None:
        knobs = policy(AffectState(affect=Affect.AGITATED))

        assert knobs.question_type is QuestionStyle.NONE
        assert "Do not interrupt" in knobs.guidance

    def test_depletion_closes_the_call_without_extracting(self) -> None:
        knobs = policy(AffectState(energy=Energy.DEPLETED))

        assert knobs.topic_action is TopicAction.CLOSE
        assert knobs.question_type is QuestionStyle.NONE
        assert "Ending early is a success" in knobs.guidance

    def test_sadness_is_not_cheered_up_or_pivoted_away_from(self) -> None:
        """Sadness while engaged is not a problem to fix. It is often the
        point."""
        knobs = policy(AffectState(affect=Affect.SAD))

        assert knobs.topic_action is TopicAction.HOLD
        assert "do not change the subject" in knobs.guidance
        assert "long silences" in knobs.silence_tolerance

    def test_withdrawal_is_read_as_about_the_topic_first(self) -> None:
        knobs = policy(AffectState(engagement=Engagement.WITHDRAWING))

        assert knobs.topic_action is TopicAction.PIVOT
        assert "not the same as wanting" in knobs.guidance

    def test_fading_shortens_the_agent_before_it_shortens_her(self) -> None:
        knobs = policy(AffectState(energy=Energy.FADING))

        assert "Shorten your own turns first" in knobs.guidance
        assert knobs.topic_action is TopicAction.CLOSE

    def test_fading_names_the_unfinished_thread_on_the_way_out(self) -> None:
        assert (
            "invitation to return" in policy(AffectState(energy=Energy.FADING)).guidance
        )

    def test_excitement_gets_out_of_the_way(self) -> None:
        """Her highest-yield state. Interrupting it is the worst thing the
        agent can do."""
        knobs = policy(AffectState(affect=Affect.EXCITED))

        assert knobs.topic_action is TopicAction.DEEPEN
        assert knobs.question_type is QuestionStyle.NONE
        assert "Do not interrupt" in knobs.guidance

    def test_a_good_state_deepens(self) -> None:
        knobs = policy(AffectState())

        assert knobs.topic_action is TopicAction.DEEPEN
        assert knobs.question_type is QuestionStyle.OPEN


class TestAxesInCombination:
    """The pair that justifies three axes instead of one label.

    Verified against real audio: a tired, trailing-off delivery reads as
    fading/withdrawing/sad, while a slow grieving delivery of a story she
    chooses to tell reads as fresh/engaged/sad. One label would collapse them.
    """

    def test_sad_while_telling_holds_the_subject(self) -> None:
        knobs = policy(
            AffectState(
                energy=Energy.FRESH, engagement=Engagement.ENGAGED, affect=Affect.SAD
            )
        )

        assert knobs.topic_action is TopicAction.HOLD
        assert "do not change the subject" in knobs.guidance

    def test_sad_while_shutting_down_lets_it_go(self) -> None:
        knobs = policy(
            AffectState(
                energy=Energy.FADING,
                engagement=Engagement.WITHDRAWING,
                affect=Affect.SAD,
            )
        )

        assert knobs.topic_action is TopicAction.PIVOT
        assert "cannot carry this subject" in knobs.guidance

    def test_the_two_sad_states_are_treated_differently(self) -> None:
        """Regression: sadness used to be checked before engagement, so both
        got the same response and the extra axes bought nothing."""
        telling = policy(AffectState(engagement=Engagement.ENGAGED, affect=Affect.SAD))
        shutting_down = policy(
            AffectState(engagement=Engagement.WITHDRAWING, affect=Affect.SAD)
        )

        assert telling.topic_action is not shutting_down.topic_action
        assert telling.guidance != shutting_down.guidance

    def test_neither_tries_to_cheer_her_up(self) -> None:
        for engagement in (Engagement.ENGAGED, Engagement.WITHDRAWING):
            knobs = policy(AffectState(engagement=engagement, affect=Affect.SAD))

            assert knobs.question_type is QuestionStyle.NONE
            assert "console" in knobs.guidance or "not to dwell" in knobs.guidance


class TestPrecedence:
    def test_distress_outranks_everything(self) -> None:
        state = AffectState(
            energy=Energy.DEPLETED,
            affect=Affect.EXCITED,
            flags=[AffectFlag.DISTRESS, AffectFlag.LOOPING],
        )

        assert policy(state).care_flag == "distress"

    def test_exhaustion_outranks_a_good_mood(self) -> None:
        state = AffectState(energy=Energy.DEPLETED, affect=Affect.EXCITED)

        assert policy(state).topic_action is TopicAction.CLOSE


class TestInstructionBlock:
    def test_carries_the_guidance(self) -> None:
        block = describe_for_instruction(AffectState(energy=Energy.FADING))

        assert "Shorten your own turns first" in block

    @pytest.mark.parametrize(
        "state",
        [
            AffectState(energy=Energy.DEPLETED),
            AffectState(affect=Affect.SAD),
            AffectState(engagement=Engagement.WITHDRAWING),
            AffectState(flags=[AffectFlag.LOOPING]),
        ],
    )
    def test_never_hands_the_agent_a_label_to_say_out_loud(
        self, state: AffectState
    ) -> None:
        """She should feel understood, not monitored. Those are the same
        behaviour, done invisibly or badly."""
        block = describe_for_instruction(state)

        for label in ("depleted", "withdrawing", "looping", "affect", "energy"):
            assert label not in block


class TestWavWrapping:
    def test_produces_a_readable_wav(self) -> None:
        import wave

        wav = wrap_pcm_as_wav(b"\x00\x01" * 16000)

        with wave.open(__import__("io").BytesIO(wav)) as handle:
            assert handle.getnchannels() == 1
            assert handle.getframerate() == 16000
            assert handle.getnframes() == 16000
