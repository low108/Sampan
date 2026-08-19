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
    Domain.TASTE: "what she liked to eat",
    Domain.PLAY: "what she played as a child",
    Domain.WORK: "the work she used to do",
    Domain.HOME: "the houses she has lived in",
    Domain.PEOPLE: "the neighbours and friends of those days",
    Domain.EVENTS: "weddings and festivals",
    Domain.TRADITION: "how festivals were kept",
    Domain.OBJECTS: "old things still in the house",
    Domain.SKILLS: "what she can cook and make",
    Domain.LOVE: "how she and Ah Gong met",
    Domain.ROOT: "the family coming over from China",
    Domain.JOURNEY: "moving from the kampung to the town",
    Domain.HARDSHIP: "the hard years",
    Domain.WISDOM: "what she wants her grandchildren to know",
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
    # Qingming is the ancestor-remembrance festival, which is exactly when an
    # agent collecting ancestral stories should be calling.
    (4, 4): ("Qingming", Domain.ROOT),
    (4, 5): ("Qingming", Domain.ROOT),
    (8, 15): ("Hungry Ghost", Domain.TRADITION),
    (9, 17): ("Mid-Autumn", Domain.TRADITION),
    (1, 29): ("Chinese New Year", Domain.TRADITION),
}


def _greeting(last_closure: ClosureReason | None, festival: str | None) -> str:
    """Open with one specific small thing, never a generic hello."""
    if festival:
        return f"mention that {festival} is coming, ask how she used to keep it"
    if last_closure is ClosureReason.FATIGUE:
        return "ask whether she slept well after last time"
    if last_closure is ClosureReason.INTERRUPTED:
        return "ask about the neighbour who came to the door last time"
    return "ask what she had this morning"


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
                        f"Last time {thread.topic} was cut off halfway. "
                        f"She had not yet reached: "
                        f"{thread.left_off_at or thread.topic}"
                    ),
                    score=SCORE_INTERRUPTED,
                    reason="cut off last time; she still wants to tell it",
                )
            )
        else:
            candidates.append(
                Candidate(
                    kind=CandidateKind.THREAD,
                    label=thread.topic,
                    say=(
                        f"{thread.topic} — still unfinished: "
                        f"{thread.left_off_at or thread.topic}"
                    ),
                    score=SCORE_THREAD + min(thread.touch_count, 3),
                    reason="raised before, not finished",
                )
            )
    return candidates


def _ask_candidate(
    ask: Ask | None, sensitivities: list[SensitiveTopic]
) -> Candidate | None:
    """A family question, always with the asker's name in it."""
    if ask is None or not may_raise(ask.question, sensitivities):
        return None
    who = f"{ask.from_name}" + (f" ({ask.relation})" if ask.relation else "")
    return Candidate(
        kind=CandidateKind.ASK,
        label=ask.question,
        say=f"{who} asked: {ask.question}",
        score=SCORE_ASK,
        reason=f"{ask.from_name} left her a question",
    )


def choose_target(
    covered: set[Domain],
    session_count: int,
    sensitivities: list[SensitiveTopic],
    preferred: tuple[Domain, ...] = (Domain.ROOT, Domain.TASTE),
) -> Domain | None:
    """One subject to lean toward, if the conversation opens toward it.

    Chosen only from domains trust has unlocked and she has not covered. The
    depth gate is doing real work here: ROOT sits at level 2, so ancestry is
    not reachable until the third call. That was a decision about trust, not an
    accident, and steering must not route around it.

    A refused subject is not merely deprioritised, it is never eligible.
    """
    depth = unlocked_depth(session_count)
    eligible = [
        domain
        for domain, level in DOMAIN_DEPTH.items()
        if level <= depth
        and domain not in covered
        and may_raise(DOMAIN_PROMPTS[domain], sensitivities)
    ]
    if not eligible:
        return None
    for wanted in preferred:
        if wanted in eligible:
            return wanted
    return min(eligible, key=lambda d: (DOMAIN_DEPTH[d], d.value))


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
        say=f"not talked about yet: {DOMAIN_PROMPTS[domain]}",
        score=SCORE_DOMAIN,
        reason=f"never covered, and deep enough by call {session_count + 1}",
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
                say=(f"{festival_entry[0]} is coming — ask how she used to keep it"),
                score=SCORE_DATE,
                reason="a festival is close",
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
        target_domain=choose_target(covered, session_count, sensitivities),
    )


def render_plan(plan: SessionPlan) -> str:
    """Turn the plan into the session block of the agent's instruction."""
    lines = []
    if plan.session_count == 0:
        lines.append(
            "This is the first meeting. Open like this: "
            '"Ah Ma, I am Xiao Chuan. Your son Wei Lun asked me to keep you '
            'company, and to write your stories down for the family."'
        )
    else:
        lines.append(
            f"You have spoken with Ah Ma {plan.session_count} times already. "
            "**Do not introduce yourself and do not say who you are.** "
            "Pick up like someone she knows."
        )
    lines.append("")
    lines.append("How to open this call (**a fallback, not a script**):")
    lines.append(f"1. Greet her, and {plan.greeting}.")

    if plan.ask is not None:
        who = plan.ask.from_name
        lines.append(
            f"2. Play {who}'s recording, then say plainly that {who} asked "
            f'— "{who} was asking…". The credit is {who}\'s, not yours.'
        )

    lines.append("3. Listen to her first two turns and judge how she is today.")
    lines.append("   - Low: offer one light thing, or simply let her talk.")
    if plan.light_offer is not None:
        lines.append(f"     The light one: {plan.light_offer.say}")
    lines.append("   - Fine: offer at most two, and never as a menu:")
    for offer in plan.offers:
        lines.append(f"     - {offer.say}")

    if plan.target_domain is not None:
        # Deliberately placed above the never-steer-back rule, so the rule is
        # the last thing read. A lean is an ear, not an agenda: if the opening
        # does not arrive, nothing happens and nothing is lost.
        lines.append("")
        lines.append(
            "If a natural opening appears — and only then — you would like to "
            f"hear about {DOMAIN_PROMPTS[plan.target_domain]}. "
            "**Do not raise it, do not work toward it, and do not return to "
            "it if she moves away.** It is somewhere she has not been, not "
            "somewhere she must go."
        )

    lines.append("")
    lines.append(
        "**If she starts talking about something else, follow her. Everything "
        "above is void, and you never steer back.**"
    )
    return "\n".join(lines)
