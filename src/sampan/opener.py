"""How a call starts.

Score candidates, gate them on what previous calls taught us, offer at most
two. The plan is a fallback, never an agenda — the instruction it renders
tells the agent to drop it the moment she starts talking about something else,
and never to steer back.

This is seam 2 (docs/spec-p0.md): deterministic given a stored state, so it is
tested against the state the Archivist actually produced.
"""

from __future__ import annotations

from datetime import date

from sampan.models import (
    Ask,
    Candidate,
    CandidateKind,
    ClosureReason,
    Domain,
    SensitiveTopic,
    SessionPlan,
    Thread,
)
from sampan.preferences import may_raise
from sampan.threads import open_threads

# She was cut off mid-sentence. Saying so proves the agent was listening, and
# nothing else available comes close.
SCORE_INTERRUPTED = 100.0
# One per call, always attributed by name.
SCORE_ASK = 90.0
SCORE_DATE = 45.0
SCORE_THREAD = 40.0
SCORE_DOMAIN = 20.0

MAX_OFFERS = 2

# Topic intimacy. Hardship and regret are not session-one material; the agent
# earns its way inward over weeks.
DOMAIN_DEPTH: dict[Domain, int] = {
    Domain.TASTE: 0,
    Domain.PLAY: 0,
    Domain.WORK: 0,
    Domain.HOME: 0,
    Domain.PEOPLE: 1,
    Domain.EVENTS: 1,
    Domain.TRADITION: 1,
    Domain.OBJECTS: 1,
    Domain.SKILLS: 1,
    Domain.LOVE: 2,
    Domain.ROOT: 2,
    Domain.JOURNEY: 2,
    Domain.HARDSHIP: 3,
    Domain.WISDOM: 3,
}

DOMAIN_PROMPTS: dict[Domain, str] = {
    Domain.TASTE: "以前最喜欢吃的东西",
    Domain.PLAY: "小时候玩的",
    Domain.WORK: "以前做过的工",
    Domain.HOME: "以前住过的厝",
    Domain.PEOPLE: "从前的邻居朋友",
    Domain.EVENTS: "以前的婚礼、节日",
    Domain.TRADITION: "以前过节的规矩",
    Domain.OBJECTS: "家里留下来的老东西",
    Domain.SKILLS: "她会煮的、会做的",
    Domain.LOVE: "她跟阿公是怎么认识的",
    Domain.ROOT: "祖辈从中国来的事",
    Domain.JOURNEY: "从乡下搬到城市的事",
    Domain.HARDSHIP: "以前苦的日子",
    Domain.WISDOM: "她想跟孙辈讲的话",
}


# Trust unlocks depth. Deliberately slow: three good calls before hardship.
def unlocked_depth(session_count: int) -> int:
    if session_count >= 6:
        return 3
    if session_count >= 3:
        return 2
    if session_count >= 1:
        return 1
    return 0


FESTIVALS: dict[tuple[int, int], tuple[str, Domain]] = {
    (4, 4): ("清明", Domain.ROOT),
    (4, 5): ("清明", Domain.ROOT),
    (8, 15): ("中元", Domain.TRADITION),
    (9, 17): ("中秋", Domain.TRADITION),
    (1, 29): ("新年", Domain.TRADITION),
}


def _greeting(last_closure: ClosureReason | None, festival: str | None) -> str:
    """Open with one specific small thing, never a generic hello."""
    if festival:
        return f"提一下快到{festival}了,问她以前怎么过"
    if last_closure is ClosureReason.FATIGUE:
        return "问她上次聊完有没有睡好"
    if last_closure is ClosureReason.INTERRUPTED:
        return "问她上次那位邻居的事"
    return "问她今天早上吃了什么"


def _thread_candidates(
    threads: list[Thread], sensitivities: list[SensitiveTopic]
) -> list[Candidate]:
    candidates: list[Candidate] = []
    for thread in open_threads(threads):
        if not may_raise(thread.topic, sensitivities):
            continue
        if thread.interrupted:
            candidates.append(
                Candidate(
                    kind=CandidateKind.THREAD,
                    label=thread.topic,
                    say=(
                        f"上次讲{thread.topic}讲到一半就断了。"
                        f"她还没讲到:{thread.left_off_at or thread.topic}"
                    ),
                    score=SCORE_INTERRUPTED,
                    reason="上次被打断,她还想讲",
                )
            )
        else:
            candidates.append(
                Candidate(
                    kind=CandidateKind.THREAD,
                    label=thread.topic,
                    say=(
                        f"{thread.topic} —— 还没讲完的是:"
                        f"{thread.left_off_at or thread.topic}"
                    ),
                    score=SCORE_THREAD + min(thread.touch_count, 3),
                    reason="讲过但还没讲完",
                )
            )
    return candidates


def _ask_candidate(
    ask: Ask | None, sensitivities: list[SensitiveTopic]
) -> Candidate | None:
    """A family question, always with the asker's name in it."""
    if ask is None or not may_raise(ask.question, sensitivities):
        return None
    who = f"{ask.from_name}" + (f"({ask.relation})" if ask.relation else "")
    return Candidate(
        kind=CandidateKind.ASK,
        label=ask.question,
        say=f"{who}问:{ask.question}",
        score=SCORE_ASK,
        reason=f"{ask.from_name}留了话给她",
    )


def _domain_candidate(
    covered: set[Domain], session_count: int, sensitivities: list[SensitiveTopic]
) -> Candidate | None:
    depth = unlocked_depth(session_count)
    options = [
        domain
        for domain, level in DOMAIN_DEPTH.items()
        if level <= depth
        and domain not in covered
        and may_raise(DOMAIN_PROMPTS[domain], sensitivities)
    ]
    if not options:
        return None
    domain = min(options, key=lambda d: (DOMAIN_DEPTH[d], d.value))
    return Candidate(
        kind=CandidateKind.DOMAIN,
        label=domain.value,
        say=f"还没聊过的:{DOMAIN_PROMPTS[domain]}",
        score=SCORE_DOMAIN,
        reason=f"还没聊过,深浅够得上(第{session_count + 1}次)",
    )


def build_session_plan(
    *,
    threads: list[Thread] | None = None,
    sensitivities: list[SensitiveTopic] | None = None,
    ask: Ask | None = None,
    covered_domains: set[Domain] | None = None,
    session_count: int = 0,
    last_closure: ClosureReason | None = None,
    today: date | None = None,
) -> SessionPlan:
    """Decide how to open the next call."""
    threads = threads or []
    sensitivities = sensitivities or []
    covered = covered_domains or set()
    today = today or date.today()

    festival_entry = FESTIVALS.get((today.month, today.day))
    festival = festival_entry[0] if festival_entry else None

    candidates = _thread_candidates(threads, sensitivities)
    if (from_family := _ask_candidate(ask, sensitivities)) is not None:
        candidates.append(from_family)
    if festival_entry is not None:
        candidates.append(
            Candidate(
                kind=CandidateKind.DATE,
                label=festival_entry[0],
                say=f"快到{festival_entry[0]}了,问她以前怎么过",
                score=SCORE_DATE,
                reason="快到节日了",
            )
        )
    if (domain := _domain_candidate(covered, session_count, sensitivities)) is not None:
        candidates.append(domain)

    ranked = sorted(candidates, key=lambda c: -c.score)
    offers = ranked[:MAX_OFFERS]

    # If she is flat or tired, one light option is all she gets offered.
    light = next(
        (c for c in ranked if c.kind in (CandidateKind.DOMAIN, CandidateKind.DATE)),
        None,
    )

    return SessionPlan(
        greeting=_greeting(last_closure, festival),
        session_count=session_count,
        ask=ask if from_family is not None else None,
        offers=offers,
        light_offer=light,
        considered=ranked,
    )


def render_plan(plan: SessionPlan) -> str:
    """Turn the plan into the session block of the agent's instruction."""
    lines = []
    if plan.session_count == 0:
        lines.append(
            "这是第一次见面。开场这样讲:"
            "「阿嬷,我是小船。你儿子伟伦叫我来陪你聊天,把你的故事写下来给家里人。」"
        )
    else:
        lines.append(
            f"你跟阿嬷已经聊过 {plan.session_count} 次了。"
            "**不要自我介绍,也不要讲你是谁**,直接像熟人一样接下去讲。"
        )
    lines.append("")
    lines.append("这次聊天的开场(**只是备案,不是流程**):")
    lines.append(f"1. 先打招呼,{plan.greeting}。")

    if plan.ask is not None:
        who = plan.ask.from_name
        lines.append(
            f"2. 放{who}的语音,然后讲明是{who}问的 ——「{who}问……」。"
            f"功劳是{who}的,不是你的。"
        )

    lines.append("3. 听她头两句,先判断她今天有没有精神。")
    lines.append("   - 没什么精神:只提一个轻松的,或者干脆让她自己讲。")
    if plan.light_offer is not None:
        lines.append(f"     轻松的:{plan.light_offer.say}")
    lines.append("   - 有精神:最多给她两个选择,不要像在念菜单:")
    for offer in plan.offers:
        lines.append(f"     · {offer.say}")

    lines.append("")
    lines.append("**她要是自己讲起别的,就跟着她走,上面这些全部作废,不要绕回来。**")
    return "\n".join(lines)
