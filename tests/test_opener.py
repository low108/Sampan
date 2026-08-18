"""The session opener — seam 2. Deterministic, no model call.

The demo's central beat: with the seeded state, the call opens on the thread
the doorbell cut short, and Wei Lun's question arrives with his name on it.
"""

from __future__ import annotations

from datetime import date

import pytest

from sampan.models import (
    Ask,
    CandidateKind,
    ClosureReason,
    Domain,
    SensitiveTopic,
    Thread,
)
from sampan.opener import MAX_OFFERS, build_session_plan, render_plan, unlocked_depth


def thread(
    topic: str,
    *,
    interrupted: bool = False,
    left_off_at: str = "",
    touches: int = 1,
) -> Thread:
    return Thread(
        thread_id=f"thr_{topic}",
        topic=topic,
        interrupted=interrupted,
        left_off_at=left_off_at,
        touch_count=touches,
    )


WEI_LUN = Ask(
    ask_id="ask_001",
    from_name="Wei Lun",
    relation="son",
    question="Did Ah Gong leave anything behind?",
)


class TestInterruptedThreadWins:
    def test_it_outranks_everything_else(self) -> None:
        plan = build_session_plan(
            threads=[
                thread("Ah Gong's crossing"),
                thread(
                    "what happened after the shop closed",
                    interrupted=True,
                    left_off_at="the years after the shop closed",
                ),
                thread("the wedding photograph"),
            ],
            ask=WEI_LUN,
        )

        assert plan.offers[0].label == "what happened after the shop closed"
        assert plan.offers[0].kind is CandidateKind.THREAD

    def test_the_offer_says_what_she_had_not_reached(self) -> None:
        """Vague is useless. The agent has to be able to say it out loud."""
        plan = build_session_plan(
            threads=[
                thread(
                    "what happened after the shop closed",
                    interrupted=True,
                    left_off_at="the years after the shop closed",
                )
            ]
        )

        assert "the years after the shop closed" in plan.offers[0].say

    def test_a_merely_open_thread_does_not(self) -> None:
        plan = build_session_plan(
            threads=[
                thread("Ah Gong's crossing", touches=3),
                thread("the wedding photograph"),
            ],
            ask=WEI_LUN,
        )

        assert plan.offers[0].kind is CandidateKind.ASK


class TestFamilyAsk:
    def test_the_asker_is_named(self) -> None:
        """She has to hear who was thinking about her. The agent takes no
        credit for it."""
        plan = build_session_plan(ask=WEI_LUN)

        assert "Wei Lun" in plan.offers[0].say
        assert plan.ask is not None

    def test_it_reaches_the_rendered_instruction(self) -> None:
        rendered = render_plan(build_session_plan(ask=WEI_LUN))

        assert "Wei Lun" in rendered
        assert "The credit is Wei Lun's" in rendered

    def test_no_ask_means_no_ask_block(self) -> None:
        assert "recording" not in render_plan(build_session_plan())


class TestOfferLimit:
    def test_never_more_than_two(self) -> None:
        """Elderly plus voice: a menu of four is cognitive load, not choice."""
        plan = build_session_plan(
            threads=[thread(f"topic {i}", touches=i) for i in range(6)], ask=WEI_LUN
        )

        assert len(plan.offers) <= MAX_OFFERS

    def test_everything_scored_is_kept_for_the_overlay(self) -> None:
        plan = build_session_plan(
            threads=[thread(f"topic {i}") for i in range(5)], ask=WEI_LUN
        )

        assert len(plan.considered) > len(plan.offers)

    def test_a_light_option_is_always_prepared(self) -> None:
        """For the days she answers flatly and should not be pushed."""
        plan = build_session_plan(threads=[thread("the shop closing")], session_count=2)

        assert plan.light_offer is not None


class TestSensitivityGating:
    def test_a_forbidden_thread_is_never_offered(self) -> None:
        plan = build_session_plan(
            threads=[thread("sister"), thread("the coffee shop")],
            sensitivities=[SensitiveTopic(topic="sister", refusals=1)],
        )

        assert all("sister" not in offer.label for offer in plan.offers)

    def test_it_is_not_even_scored(
        self,
    ) -> None:
        plan = build_session_plan(
            threads=[thread("sister")],
            sensitivities=[SensitiveTopic(topic="sister", refusals=1)],
        )

        assert all("sister" not in c.label for c in plan.considered)

    def test_a_subject_she_reopened_is_offerable_again(self) -> None:
        plan = build_session_plan(
            threads=[thread("why the shop closed")],
            sensitivities=[
                SensitiveTopic(topic="why the shop closed", refusals=1, engagements=1)
            ],
        )

        assert any("shop closed" in c.label for c in plan.considered)


class TestDepthGating:
    @pytest.mark.parametrize(
        ("sessions", "depth"), [(0, 0), (1, 1), (3, 2), (6, 3), (20, 3)]
    )
    def test_trust_unlocks_slowly(self, sessions: int, depth: int) -> None:
        assert unlocked_depth(sessions) == depth

    def test_hardship_is_not_first_session_material(self) -> None:
        plan = build_session_plan(session_count=0)

        domains = [c.label for c in plan.considered if c.kind is CandidateKind.DOMAIN]
        assert Domain.HARDSHIP.value not in domains

    def test_a_covered_domain_is_not_suggested_again(self) -> None:
        plan = build_session_plan(
            session_count=1, covered_domains={Domain.TASTE, Domain.PLAY}
        )

        domains = [c.label for c in plan.considered if c.kind is CandidateKind.DOMAIN]
        assert Domain.TASTE.value not in domains


class TestGreeting:
    def test_a_tired_ending_is_asked_after(self) -> None:
        plan = build_session_plan(last_closure=ClosureReason.FATIGUE)

        assert "slept well" in plan.greeting

    def test_an_interruption_is_asked_after(self) -> None:
        plan = build_session_plan(last_closure=ClosureReason.INTERRUPTED)

        assert "neighbour" in plan.greeting

    def test_a_festival_takes_precedence(self) -> None:
        """Qingming is the ancestor-remembrance festival. An agent collecting
        ancestral stories calling then is the whole point."""
        plan = build_session_plan(today=date(2026, 4, 4))

        assert "Qingming" in plan.greeting

    def test_the_greeting_is_never_generic(self) -> None:
        assert build_session_plan().greeting.strip()


class TestFirstMeeting:
    """An agent that reintroduces itself every week has no memory, whatever
    the rest of the state says."""

    def test_the_first_call_introduces_itself(self) -> None:
        rendered = render_plan(build_session_plan(session_count=0))

        assert "I am Xiao Chuan" in rendered
        assert "Wei Lun asked me" in rendered

    def test_a_later_call_does_not(self) -> None:
        rendered = render_plan(build_session_plan(session_count=4))

        assert "I am Xiao Chuan" not in rendered
        assert "Do not introduce yourself" in rendered

    def test_a_later_call_says_how_many_times_they_have_spoken(self) -> None:
        assert "4 times" in render_plan(build_session_plan(session_count=4))

    def test_the_greeting_lives_in_the_plan_not_the_persona(self) -> None:
        """The persona has no access to session state, so a hardcoded
        first-meeting line there fires on every call forever."""
        from sampan.companion import BASE_INSTRUCTION

        assert "I am Xiao Chuan" not in BASE_INSTRUCTION


class TestRendering:
    def test_the_plan_is_marked_as_a_fallback_not_an_agenda(self) -> None:
        rendered = render_plan(build_session_plan(threads=[thread("the coffee shop")]))

        assert "a fallback, not a script" in rendered

    def test_it_tells_the_agent_to_follow_her_instead(self) -> None:
        """The single most important line: if she starts somewhere else, the
        plan is void and the agent never steers back."""
        rendered = render_plan(build_session_plan(threads=[thread("the coffee shop")]))

        assert (
            "Everything\n        above is void"
            in rendered.replace("\n", " ").replace("  ", " ")
            or "is void" in rendered
        )
        assert "never steer back" in rendered

    def test_it_tells_the_agent_to_read_her_first(self) -> None:
        rendered = render_plan(build_session_plan(threads=[thread("the coffee shop")]))

        assert "first two turns" in rendered


class TestLeaning:
    """A lean, not a push.

    The domains a family archive most wants — where she came from, what she ate
    — are the ones least likely to come up unprompted. But an elder who feels
    steered stops talking, so the difference between leaning and steering is the
    whole product.
    """

    def test_a_subject_is_chosen_to_lean_toward(self) -> None:
        plan = build_session_plan(session_count=6)

        assert plan.target_domain is not None

    def test_it_never_reaches_past_the_trust_gate(self) -> None:
        """ROOT sits at depth 2. Ancestry is not first-conversation material,
        and steering must not route around a decision about trust."""
        from sampan.models import Domain

        first = build_session_plan(session_count=0)

        assert first.target_domain is not Domain.ROOT

    def test_ancestry_becomes_reachable_once_trust_is_earned(self) -> None:
        from sampan.models import Domain

        later = build_session_plan(session_count=6)

        assert later.target_domain is Domain.ROOT

    def test_a_covered_subject_is_not_chosen_again(self) -> None:
        from sampan.models import Domain

        plan = build_session_plan(session_count=6, covered_domains={Domain.ROOT})

        assert plan.target_domain is not Domain.ROOT

    def test_a_refused_subject_is_never_chosen(self) -> None:
        from sampan.models import Domain
        from sampan.opener import DOMAIN_PROMPTS, choose_target

        target = choose_target(
            covered=set(),
            session_count=6,
            sensitivities=[
                SensitiveTopic(topic=DOMAIN_PROMPTS[Domain.ROOT], refusals=1)
            ],
        )

        assert target is not Domain.ROOT

    def test_the_instruction_forbids_raising_it(self) -> None:
        """The load-bearing assertion. A lean the agent acts on is a push."""
        rendered = render_plan(build_session_plan(session_count=6))

        assert "Do not raise it" in rendered
        assert "do not work toward it" in rendered

    def test_never_steering_back_is_still_the_last_word(self) -> None:
        rendered = render_plan(build_session_plan(session_count=6))

        assert rendered.rstrip().endswith("you never steer back.**")

    def test_nothing_is_said_when_there_is_nowhere_to_lean(self) -> None:
        from sampan.models import Domain

        plan = build_session_plan(session_count=0, covered_domains=set(Domain))

        assert plan.target_domain is None
        assert "natural opening" not in render_plan(plan)
