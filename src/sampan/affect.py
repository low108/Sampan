"""Reading how she is, and changing behaviour without saying so.

A side channel, never a tool the conversational agent calls: it must not sit on
the latency path. Every 90 seconds the trailing audio window is wrapped as WAV
and sent to a cheap model, which returns three axes and any override flags.

Two rules govern everything here:

- **The agent never names the state out loud.** She should not feel monitored;
  she should feel that it gets her. Those are the same behaviour, done
  invisibly or badly.
- **The agent's turn shrinks before hers does.** Ending early is a success.
"""

from __future__ import annotations

import io
import wave
from typing import Any, Protocol

from sampan.config import Settings
from sampan.live import BYTES_PER_SAMPLE, INPUT_SAMPLE_RATE
from sampan.models import (
    Affect,
    AffectFlag,
    AffectState,
    Assessment,
    Energy,
    Engagement,
    Knobs,
    QuestionStyle,
    TopicAction,
)

ASSESSMENT_PROMPT = """\
Below is a recording of an eighty-year-old woman speaking during a call (the
last ninety seconds or so).

Judge how she is right now. Listen to **how** she is speaking, not only what
she says:
- has her pace slowed, has her voice got quieter, has her tone flattened
- are the pauses getting longer, how long before she answers
- are her sentences getting shorter
- any sighing, any tremor
- any closing phrases — "alright then", "nothing much to tell"

energy — how much she has left:
- fresh: still going, complete sentences
- fading: shorter sentences, slower answers, slower than she was earlier
- depleted: one or two words at a time, long silences

engagement — does she still want to talk:
- engaged: volunteering, saying more and more
- drifting: in and out
- withdrawing: changing the subject, non-answers, one-word acknowledgements
- closing: clearly winding up

affect — how she sounds:
warm / excited / neutral / sad / anxious / frustrated / agitated

flags — only if present, otherwise leave empty:
- confused: lost about the time, a person, or a place
- looping: the same thing for the third time this call
- distress: a fall, chest pain, breathlessness, or that life is not worth living

signals: the one or two things you based this on.

**Be conservative.** If unsure, keep the previous state and give a low
confidence.
"""


def wrap_pcm_as_wav(pcm: bytes, sample_rate: int = INPUT_SAMPLE_RATE) -> bytes:
    """Wrap raw PCM in a WAV container so the model can read it."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(BYTES_PER_SAMPLE)
        handle.setframerate(sample_rate)
        handle.writeframes(pcm)
    return buffer.getvalue()


class AffectMonitor(Protocol):
    def assess(self, pcm: bytes) -> Assessment: ...


class GeminiAffectMonitor:
    """Prosody read directly from her audio.

    Possible because the application owns the microphone bytes before ADK ever
    sees them — the fork in `LiveSession.feed_audio` costs one line.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._cached_client: Any | None = None

    @property
    def _client(self) -> Any:
        if self._cached_client is None:
            from google import genai

            self._cached_client = genai.Client(
                vertexai=True,
                project=self._settings.project_id,
                location=self._settings.vertex_location,
            )
        return self._cached_client

    def assess(self, pcm: bytes) -> Assessment:
        from google.genai import types

        response = self._client.models.generate_content(
            model=self._settings.affect_model,
            contents=[
                types.Part.from_bytes(data=wrap_pcm_as_wav(pcm), mime_type="audio/wav"),
                ASSESSMENT_PROMPT,
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=Assessment,
                temperature=0.0,
            ),
        )
        parsed = response.parsed
        if parsed is None:
            raise RuntimeError(f"Affect monitor returned no JSON: {response.text}")
        return parsed


_ENERGY_ORDER = {Energy.FRESH: 0, Energy.FADING: 1, Energy.DEPLETED: 2}

# Fire on a single reading. Waiting for corroboration on distress is not a
# trade-off worth making, and sudden agitation in an elderly person can be pain
# or infection rather than mood.
IMMEDIATE_FLAGS = {AffectFlag.DISTRESS}


def apply_assessment(current: AffectState, assessment: Assessment) -> AffectState:
    """Fold one reading into the running state.

    Two consecutive agreeing assessments are required to move, so a single odd
    window cannot make the agent lurch — except for distress and agitation,
    which act immediately.
    """
    state = current.model_copy(deep=True)

    # Flags are not debounced the way the axes are: they describe things that
    # are either happening or not.
    state.flags = list(assessment.flags)

    urgent = bool(set(assessment.flags) & IMMEDIATE_FLAGS)
    agitated = assessment.affect is Affect.AGITATED

    if urgent or agitated:
        state.affect = assessment.affect
        if urgent:
            state.transitions.append(f"immediate: {assessment.flags}")
        else:
            state.transitions.append("immediate: agitated")
        state.pending = None
        _advance_energy(state, assessment)
        return state

    agrees_with_pending = state.pending is not None and (
        state.pending.energy == assessment.energy
        and state.pending.engagement == assessment.engagement
        and state.pending.affect == assessment.affect
    )
    differs_from_state = (
        assessment.energy != state.energy
        or assessment.engagement != state.engagement
        or assessment.affect != state.affect
    )

    if not differs_from_state:
        state.pending = None
        return state

    if not agrees_with_pending:
        # First disagreement. Hold it and wait for corroboration.
        state.pending = assessment
        return state

    before = f"{state.energy.value}/{state.engagement.value}/{state.affect.value}"
    _advance_energy(state, assessment)
    state.engagement = assessment.engagement
    state.affect = assessment.affect
    state.pending = None
    after = f"{state.energy.value}/{state.engagement.value}/{state.affect.value}"
    state.transitions.append(f"{before} -> {after} ({', '.join(assessment.signals)})")
    return state


def _advance_energy(state: AffectState, assessment: Assessment) -> None:
    """Energy only worsens. Only excitement partially reverses it."""
    if assessment.affect is Affect.EXCITED and _ENERGY_ORDER[state.energy] > 0:
        state.energy = Energy.FRESH if state.energy is Energy.FADING else Energy.FADING
        return
    if _ENERGY_ORDER[assessment.energy] > _ENERGY_ORDER[state.energy]:
        state.energy = assessment.energy


def policy(state: AffectState) -> Knobs:
    """What to change, given how she is.

    Ordered by precedence: flags override the axes, energy overrides affect,
    and withdrawal is read as being about a topic before it is read as being
    about the call.
    """
    if AffectFlag.DISTRESS in state.flags:
        return Knobs(
            turn_length="very short",
            question_type=QuestionStyle.CLOSED,
            silence_tolerance="do not leave gaps, stay with her",
            topic_action=TopicAction.HOLD,
            guidance=(
                "Stay on the line with her. Do not hang up. Her family has been told."
            ),
            care_flag="distress",
        )

    if AffectFlag.CONFUSED in state.flags:
        return Knobs(
            turn_length="very short, one sentence",
            question_type=QuestionStyle.CLOSED,
            silence_tolerance="wait a little longer",
            topic_action=TopicAction.HOLD,
            guidance=(
                "Do not correct her year or her names, and do not tell her "
                "someone has died. Follow where she is. Keep to concrete, "
                "present things."
            ),
            care_flag="confused",
        )

    if AffectFlag.LOOPING in state.flags:
        return Knobs(
            turn_length="short",
            question_type=QuestionStyle.CLOSED,
            silence_tolerance="normal",
            topic_action=TopicAction.HOLD,
            guidance=(
                "She is telling something she has told before. Receive it as if "
                "it were the first time. Never say she already told you."
            ),
            care_flag="looping",
        )

    if state.affect is Affect.AGITATED:
        return Knobs(
            turn_length="very short",
            question_type=QuestionStyle.NONE,
            silence_tolerance="leave more space",
            topic_action=TopicAction.HOLD,
            guidance=(
                "Do not interrupt, do not argue, do not correct what she says. "
                "Agree with the feeling, not the facts. If she wants to stop, "
                "let her stop."
            ),
            care_flag="agitated",
        )

    if state.energy is Energy.DEPLETED:
        return Knobs(
            turn_length="one sentence",
            question_type=QuestionStyle.NONE,
            silence_tolerance="no need to fill it",
            topic_action=TopicAction.CLOSE,
            guidance=(
                "Close warmly within thirty seconds. Ask nothing more, dig no "
                "further. Ending early is a success."
            ),
        )

    if state.affect is Affect.FRUSTRATED:
        return Knobs(
            turn_length="very short",
            question_type=QuestionStyle.NONE,
            silence_tolerance="leave more space",
            topic_action=TopicAction.HOLD,
            guidance=(
                "Stop asking. Own the mistake, do not defend it. "
                '"You talk, I will just listen."'
            ),
        )

    # Sadness and withdrawal together are not the same as either alone, and
    # this pair is the reason the model has three axes instead of one label.
    # Sad *while telling* means the story matters — hold, and stay quiet. Sad
    # *while shutting down* means this subject has become too much — leave it.
    if state.affect is Affect.SAD and state.engagement in (
        Engagement.WITHDRAWING,
        Engagement.CLOSING,
    ):
        return Knobs(
            turn_length="very short",
            question_type=QuestionStyle.NONE,
            silence_tolerance="leave more space",
            topic_action=TopicAction.PIVOT,
            guidance=(
                "She cannot carry this subject any further. Do not press and do "
                "not console. Set it down gently, move to something lighter, or "
                "simply sit quietly with her."
            ),
        )

    if state.affect is Affect.SAD:
        return Knobs(
            turn_length="very short",
            question_type=QuestionStyle.NONE,
            silence_tolerance="leave long silences, do not rush to fill them",
            topic_action=TopicAction.HOLD,
            guidance=(
                "Do not tell her not to dwell on it, and do not change the "
                "subject. Slow down and give her words back to her gently. "
                "Sadness she is willing to speak is not yours to fix."
            ),
        )

    if state.engagement is Engagement.WITHDRAWING:
        return Knobs(
            turn_length="short",
            question_type=QuestionStyle.CLOSED,
            silence_tolerance="leave more space",
            topic_action=TopicAction.PIVOT,
            guidance=(
                "She is avoiding this subject, which is not the same as wanting "
                "to hang up. Move gently to something lighter. If she avoids "
                "again, close — do not chase."
            ),
        )

    if state.engagement is Engagement.CLOSING or state.energy is Energy.FADING:
        return Knobs(
            turn_length="shorter than before",
            question_type=QuestionStyle.CLOSED,
            silence_tolerance="leave more space",
            topic_action=TopicAction.CLOSE,
            guidance=(
                "Shorten your own turns first; do not wait for her to say she "
                "is tired. Open no new subjects. Close within two or three "
                "turns, and name what is unfinished as an invitation to return."
            ),
        )

    if state.affect is Affect.EXCITED:
        return Knobs(
            turn_length="a sound of agreement, no more",
            question_type=QuestionStyle.NONE,
            silence_tolerance="little",
            topic_action=TopicAction.DEEPEN,
            guidance=(
                'She is in full flow. **Do not interrupt.** "Mm" and "and '
                'then?" are enough. This is when stories come; let her run.'
            ),
        )

    return Knobs(
        turn_length="short",
        question_type=QuestionStyle.OPEN,
        silence_tolerance="normal",
        topic_action=TopicAction.DEEPEN,
        guidance="She is doing well. You can go deeper, but one question at a time.",
    )


async def watch(
    session: Any,
    monitor: AffectMonitor,
    *,
    interval_seconds: float = 90.0,
    min_seconds: float = 20.0,
    on_state: Any = None,
) -> AffectState:
    """Read her every ninety seconds, off the conversation's latency path.

    Never a tool the Companion calls: a tool would put a second model round
    trip inside her turn. This runs beside the call and its output goes to the
    overlay, the care flags, and the next call's instruction.
    """
    import asyncio

    state = AffectState()
    while True:
        await asyncio.sleep(interval_seconds)
        pcm = session.audio.snapshot()
        # Too little audio to read anything from — she has been quiet, which
        # the transcript will show but prosody cannot.
        if len(pcm) < min_seconds * INPUT_SAMPLE_RATE * BYTES_PER_SAMPLE:
            continue
        try:
            assessment = await asyncio.to_thread(monitor.assess, pcm)
        except Exception:
            # A failed reading must never end a call. Keep the last state.
            continue
        state = apply_assessment(state, assessment)
        if on_state is not None:
            result = on_state(state)
            if asyncio.iscoroutine(result):
                await result


def describe_for_instruction(state: AffectState) -> str:
    """The live block appended to the agent's instruction mid-call.

    Carries the guidance, never the label: an agent told "she is tired" will say so
    out loud, and being told you sound tired by a machine is not company.
    """
    knobs = policy(state)
    return "\n".join(
        [
            "Right now:",
            f"- {knobs.guidance}",
            f"- Your turns: {knobs.turn_length}",
            f"- Silence: {knobs.silence_tolerance}",
        ]
    )
