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
    from_name="伟伦",
    relation="儿子",
    question="阿公有没有留下什么东西?",
)


class TestInterruptedThreadWins:
    def test_it_outranks_everything_else(self) -> None:
        plan = build_session_plan(
            threads=[
                thread("阿公过番"),
                thread("关店以后的事", interrupted=True, left_off_at="关店之后的日子"),
                thread("结婚照"),
            ],
            ask=WEI_LUN,
        )

        assert plan.offers[0].label == "关店以后的事"
        assert plan.offers[0].kind is CandidateKind.THREAD

    def test_the_offer_says_what_she_had_not_reached(self) -> None:
        """Vague is useless. The agent has to be able to say it out loud."""
        plan = build_session_plan(
            threads=[
                thread("关店以后的事", interrupted=True, left_off_at="关店之后的日子")
            ]
        )

        assert "关店之后的日子" in plan.offers[0].say

    def test_a_merely_open_thread_does_not(self) -> None:
        plan = build_session_plan(
            threads=[thread("阿公过番", touches=3), thread("结婚照")], ask=WEI_LUN
        )

        assert plan.offers[0].kind is CandidateKind.ASK


class TestFamilyAsk:
    def test_the_asker_is_named(self) -> None:
        """She has to hear who was thinking about her. The agent takes no
        credit for it."""
        plan = build_session_plan(ask=WEI_LUN)

        assert "伟伦" in plan.offers[0].say
        assert plan.ask is not None

    def test_it_reaches_the_rendered_instruction(self) -> None:
        rendered = render_plan(build_session_plan(ask=WEI_LUN))

        assert "伟伦" in rendered
        assert "功劳是伟伦的" in rendered

    def test_no_ask_means_no_ask_block(self) -> None:
        assert "语音" not in render_plan(build_session_plan())


class TestOfferLimit:
    def test_never_more_than_two(self) -> None:
        """Elderly plus voice: a menu of four is cognitive load, not choice."""
        plan = build_session_plan(
            threads=[thread(f"话题{i}", touches=i) for i in range(6)], ask=WEI_LUN
        )

        assert len(plan.offers) <= MAX_OFFERS

    def test_everything_scored_is_kept_for_the_overlay(self) -> None:
        plan = build_session_plan(
            threads=[thread(f"话题{i}") for i in range(5)], ask=WEI_LUN
        )

        assert len(plan.considered) > len(plan.offers)

    def test_a_light_option_is_always_prepared(self) -> None:
        """For the days she answers flatly and should not be pushed."""
        plan = build_session_plan(threads=[thread("关店")], session_count=2)

        assert plan.light_offer is not None


class TestSensitivityGating:
    def test_a_forbidden_thread_is_never_offered(self) -> None:
        plan = build_session_plan(
            threads=[thread("姐姐"), thread("咖啡店")],
            sensitivities=[SensitiveTopic(topic="姐姐", refusals=1)],
        )

        assert all("姐姐" not in offer.label for offer in plan.offers)

    def test_it_is_not_even_scored(
        self,
    ) -> None:
        plan = build_session_plan(
            threads=[thread("姐姐")],
            sensitivities=[SensitiveTopic(topic="姐姐", refusals=1)],
        )

        assert all("姐姐" not in c.label for c in plan.considered)

    def test_a_subject_she_reopened_is_offerable_again(self) -> None:
        plan = build_session_plan(
            threads=[thread("关店的原因")],
            sensitivities=[
                SensitiveTopic(topic="关店的原因", refusals=1, engagements=1)
            ],
        )

        assert any("关店" in c.label for c in plan.considered)


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

        assert "睡" in plan.greeting

    def test_an_interruption_is_asked_after(self) -> None:
        plan = build_session_plan(last_closure=ClosureReason.INTERRUPTED)

        assert "邻居" in plan.greeting

    def test_a_festival_takes_precedence(self) -> None:
        """清明 is the ancestor-remembrance festival. An agent collecting
        ancestral stories calling then is the whole point."""
        plan = build_session_plan(today=date(2026, 4, 4))

        assert "清明" in plan.greeting

    def test_the_greeting_is_never_generic(self) -> None:
        assert build_session_plan().greeting.strip()


class TestFirstMeeting:
    """An agent that reintroduces itself every week has no memory, whatever
    the rest of the state says."""

    def test_the_first_call_introduces_itself(self) -> None:
        rendered = render_plan(build_session_plan(session_count=0))

        assert "我是小船" in rendered
        assert "伟伦叫我来" in rendered

    def test_a_later_call_does_not(self) -> None:
        rendered = render_plan(build_session_plan(session_count=4))

        assert "我是小船" not in rendered
        assert "不要自我介绍" in rendered

    def test_a_later_call_says_how_many_times_they_have_spoken(self) -> None:
        assert "4 次" in render_plan(build_session_plan(session_count=4))

    def test_the_greeting_lives_in_the_plan_not_the_persona(self) -> None:
        """The persona has no access to session state, so a hardcoded
        first-meeting line there fires on every call forever."""
        from sampan.companion import BASE_INSTRUCTION

        assert "我是小船。你儿子伟伦叫我来" not in BASE_INSTRUCTION


class TestRendering:
    def test_the_plan_is_marked_as_a_fallback_not_an_agenda(self) -> None:
        rendered = render_plan(build_session_plan(threads=[thread("咖啡店")]))

        assert "不是流程" in rendered

    def test_it_tells_the_agent_to_follow_her_instead(self) -> None:
        """The single most important line: if she starts somewhere else, the
        plan is void and the agent never steers back."""
        rendered = render_plan(build_session_plan(threads=[thread("咖啡店")]))

        assert "全部作废" in rendered
        assert "不要绕回来" in rendered

    def test_it_tells_the_agent_to_read_her_first(self) -> None:
        rendered = render_plan(build_session_plan(threads=[thread("咖啡店")]))

        assert "头两句" in rendered
