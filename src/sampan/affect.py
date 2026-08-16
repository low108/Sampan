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
下面是一位八十岁老人家在通话中说话的一段录音(最近一分半钟)。

请判断她现在的状态。你听的是**她怎么讲**,不只是讲什么:
- 讲话速度有没有变慢、声音有没有变小、语气有没有变平
- 停顿变长了没有、答话前要想多久
- 句子是不是越来越短
- 有没有叹气、有没有颤抖
- 有没有「好啦」「没有什么啦」这种想收尾的话

energy —— 她还有多少精神:
- fresh: 讲得动,句子完整
- fading: 句子变短、答得慢、速度比刚才慢
- depleted: 只剩一两个字,长时间沉默

engagement —— 她还想不想讲:
- engaged: 自己主动讲、越讲越多
- drifting: 有一句没一句
- withdrawing: 转开话题、答非所问、只应一声
- closing: 明显要结束了

affect —— 她的情绪:
warm / excited / neutral / sad / anxious / frustrated / agitated

flags —— 有就填,没有就空着:
- confused: 搞不清楚时间、人、地方
- looping: 同一件事这通电话里讲了第三次
- distress: 讲到跌倒、胸口痛、喘不过气、活着没意思

signals: 你根据哪几点判断的,一两句就好。

**宁可保守。** 拿不准就照上一次的状态,confidence 填低一点。
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
            turn_length="很短",
            question_type=QuestionStyle.CLOSED,
            silence_tolerance="不要留白,一直陪着她讲",
            topic_action=TopicAction.HOLD,
            guidance="留在线上陪她,不要挂断。已经通知她家人了。",
            care_flag="distress",
        )

    if AffectFlag.CONFUSED in state.flags:
        return Knobs(
            turn_length="很短,一句就好",
            question_type=QuestionStyle.CLOSED,
            silence_tolerance="多等一下",
            topic_action=TopicAction.HOLD,
            guidance=(
                "不要纠正她的年份、人名,也不要告诉她谁已经走了。"
                "顺着她的话讲,讲具体的、眼前的事。"
            ),
            care_flag="confused",
        )

    if AffectFlag.LOOPING in state.flags:
        return Knobs(
            turn_length="短",
            question_type=QuestionStyle.CLOSED,
            silence_tolerance="正常",
            topic_action=TopicAction.HOLD,
            guidance="她讲过的事又讲一次,当作第一次听。绝对不要说「你讲过了」。",
            care_flag="looping",
        )

    if state.affect is Affect.AGITATED:
        return Knobs(
            turn_length="很短",
            question_type=QuestionStyle.NONE,
            silence_tolerance="多留白",
            topic_action=TopicAction.HOLD,
            guidance=(
                "不要打断,不要争,也不要纠正她讲的内容。"
                "认同她的感受,不是认同她讲的事实。她要停就让她停。"
            ),
            care_flag="agitated",
        )

    if state.energy is Energy.DEPLETED:
        return Knobs(
            turn_length="一句话",
            question_type=QuestionStyle.NONE,
            silence_tolerance="不用填",
            topic_action=TopicAction.CLOSE,
            guidance="三十秒内温温地收尾。不要再问,不要再挖。提早结束是好事。",
        )

    if state.affect is Affect.FRUSTRATED:
        return Knobs(
            turn_length="很短",
            question_type=QuestionStyle.NONE,
            silence_tolerance="多留白",
            topic_action=TopicAction.HOLD,
            guidance="不要再问了。认了这个错,不要辩。「你讲,我听就好。」",
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
            turn_length="很短",
            question_type=QuestionStyle.NONE,
            silence_tolerance="多留白",
            topic_action=TopicAction.PIVOT,
            guidance=(
                "这个话题她讲不下去了。不要追问,也不要安慰。"
                "轻轻放下,换一件轻松的小事,或者干脆安静陪她一下。"
            ),
        )

    if state.affect is Affect.SAD:
        return Knobs(
            turn_length="很短",
            question_type=QuestionStyle.NONE,
            silence_tolerance="留很久的白,不要急着填",
            topic_action=TopicAction.HOLD,
            guidance=(
                "不要安慰她「不要想太多」,也不要转开话题。"
                "慢下来,把她讲的话轻轻讲回去。她愿意讲的难过,不是要你解决的。"
            ),
        )

    if state.engagement is Engagement.WITHDRAWING:
        return Knobs(
            turn_length="短",
            question_type=QuestionStyle.CLOSED,
            silence_tolerance="多留白",
            topic_action=TopicAction.PIVOT,
            guidance=(
                "她是在躲这个话题,不一定是想收线。轻轻换一个轻松的题目。"
                "再躲一次就收尾,不要追。"
            ),
        )

    if state.engagement is Engagement.CLOSING or state.energy is Energy.FADING:
        return Knobs(
            turn_length="比刚才短",
            question_type=QuestionStyle.CLOSED,
            silence_tolerance="多留白",
            topic_action=TopicAction.CLOSE,
            guidance=(
                "先把你自己的话变短,不要等她开口讲累。不要再开新话题。"
                "两三句内收尾,收尾时讲出还没讲完的那件事,当作下次的邀请。"
            ),
        )

    if state.affect is Affect.EXCITED:
        return Knobs(
            turn_length="只应一声",
            question_type=QuestionStyle.NONE,
            silence_tolerance="少",
            topic_action=TopicAction.DEEPEN,
            guidance=(
                "她讲得正起劲。**不要打断**,「嗯」「然后呢?」就够了。"
                "这是最好收故事的时候,让她一直讲。"
            ),
        )

    return Knobs(
        turn_length="短",
        question_type=QuestionStyle.OPEN,
        silence_tolerance="正常",
        topic_action=TopicAction.DEEPEN,
        guidance="她状态还好。可以往深一点问,但一次只问一个。",
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

    Carries the guidance, never the label: an agent told 「她累了」 will say so
    out loud, and being told you sound tired by a machine is not company.
    """
    knobs = policy(state)
    return "\n".join(
        [
            "现在这个时候:",
            f"- {knobs.guidance}",
            f"- 你的话:{knobs.turn_length}",
            f"- 停顿:{knobs.silence_tolerance}",
        ]
    )
