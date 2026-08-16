"""The voice loop's testable parts — no model, no browser, no audio device."""

from __future__ import annotations

import base64
from types import SimpleNamespace

import pytest

from sampan.companion import build_instruction
from sampan.config import Settings
from sampan.live import (
    AFFECT_WINDOW_SECONDS,
    INPUT_SAMPLE_RATE,
    OUTPUT_SAMPLE_RATE,
    AudioRingBuffer,
    build_run_config,
    encode_event,
    pump,
)
from sampan.models import (
    AvoidanceKind,
    Preference,
    PreferenceType,
    SensitiveTopic,
    TopicSignal,
)
from sampan.preferences import fold_sensitivities


def pcm(seconds: float) -> bytes:
    return b"\x00\x01" * int(seconds * INPUT_SAMPLE_RATE)


class TestAudioRingBuffer:
    """Bounded on purpose: she may talk for fifteen minutes and none of it
    needs holding beyond the affect monitor's window."""

    def test_keeps_what_it_is_given(self) -> None:
        buffer = AudioRingBuffer()
        buffer.append(pcm(1))

        assert buffer.seconds == 1.0
        assert len(buffer.snapshot()) == INPUT_SAMPLE_RATE * 2

    def test_drops_the_oldest_audio_once_full(self) -> None:
        buffer = AudioRingBuffer()

        for _ in range(AFFECT_WINDOW_SECONDS + 30):
            buffer.append(pcm(1))

        assert buffer.seconds <= AFFECT_WINDOW_SECONDS

    def test_a_long_call_does_not_grow_without_bound(self) -> None:
        buffer = AudioRingBuffer()

        for _ in range(15 * 60):
            buffer.append(pcm(1))

        assert len(buffer.snapshot()) <= buffer.max_bytes

    def test_clearing_empties_it(self) -> None:
        buffer = AudioRingBuffer()
        buffer.append(pcm(2))

        buffer.clear()

        assert buffer.seconds == 0
        assert buffer.snapshot() == b""


class TestRunConfig:
    def test_asks_for_audio_back(self) -> None:
        config = build_run_config(Settings())

        assert config.response_modalities == ["AUDIO"]

    def test_enables_session_resumption(self) -> None:
        """Live API audio sessions cap at roughly fifteen minutes, and a
        grandmother mid-story will hit that."""
        assert build_run_config(Settings()).session_resumption is not None

    def test_enables_native_affective_dialog(self) -> None:
        assert build_run_config(Settings()).enable_affective_dialog is True

    def test_transcribes_both_sides(self) -> None:
        """Her words feed the Archivist; the agent's feed the demo overlay."""
        config = build_run_config(Settings())

        assert config.input_audio_transcription is not None
        assert config.output_audio_transcription is not None


class TestEncodingEvents:
    def test_audio_is_base64_with_its_sample_rate(self) -> None:
        event = SimpleNamespace(
            content=SimpleNamespace(
                parts=[
                    SimpleNamespace(
                        inline_data=SimpleNamespace(data=b"\x01\x02"), text=None
                    )
                ]
            )
        )

        message = encode_event(event)

        assert message is not None
        assert base64.b64decode(message["audio"]) == b"\x01\x02"
        assert message["sample_rate"] == OUTPUT_SAMPLE_RATE

    def test_transcripts_are_labelled_by_speaker(self) -> None:
        event = SimpleNamespace(
            content=None,
            input_transcription=SimpleNamespace(text="我小时候在树胶园"),
            output_transcription=SimpleNamespace(text="然后呢?"),
        )

        message = encode_event(event)

        assert message == {
            "user_transcript": "我小时候在树胶园",
            "agent_transcript": "然后呢?",
        }

    def test_barge_in_is_forwarded_so_the_client_can_stop_playing(self) -> None:
        message = encode_event(SimpleNamespace(content=None, interrupted=True))

        assert message == {"interrupted": True}

    def test_an_event_with_nothing_useful_is_dropped(self) -> None:
        """The socket should carry only what the client will act on."""
        assert encode_event(SimpleNamespace(content=None)) is None


class FakeSession:
    """Stands in for a LiveSession: pump only needs events() and close()."""

    def __init__(self, events: list, raise_on_exit: Exception | None = None) -> None:
        self._events = events
        self._raise_on_exit = raise_on_exit
        self.closed = 0

    async def events(self):
        for event in self._events:
            yield event
        if self._raise_on_exit is not None:
            raise self._raise_on_exit

    def close(self) -> None:
        self.closed += 1


def audio_event(data: bytes = b"\x01\x02"):
    return SimpleNamespace(
        content=SimpleNamespace(
            parts=[SimpleNamespace(inline_data=SimpleNamespace(data=data), text=None)]
        )
    )


class TestPump:
    async def test_forwards_what_the_client_can_use(self) -> None:
        sent: list[dict] = []
        session = FakeSession([audio_event(), SimpleNamespace(content=None)])

        await pump(session, sent.append)  # type: ignore[arg-type]

        assert len(sent) == 1
        assert "audio" in sent[0]

    async def test_swallows_the_generator_teardown_error(self) -> None:
        """ADK's run_live generator raises RuntimeError if it is left early,
        and a browser disconnect does that on every single call."""
        session = FakeSession(
            [audio_event()],
            raise_on_exit=RuntimeError("generator didn't stop after athrow()"),
        )

        await pump(session, lambda _: None)  # type: ignore[arg-type]

        assert session.closed >= 1

    async def test_does_not_swallow_an_unrelated_runtime_error(self) -> None:
        session = FakeSession(
            [audio_event()], raise_on_exit=RuntimeError("something actually wrong")
        )

        with pytest.raises(RuntimeError, match="actually wrong"):
            await pump(session, lambda _: None)  # type: ignore[arg-type]

    async def test_a_client_that_hangs_up_ends_the_call(self) -> None:
        """Closing the queue winds the generator down. Tearing it out does not."""

        def explode(_: dict) -> None:
            raise ConnectionError("client gone")

        session = FakeSession([audio_event(), audio_event()])

        await pump(session, explode)  # type: ignore[arg-type]

        assert session.closed >= 1

    async def test_always_closes_the_session(self) -> None:
        session = FakeSession([])

        await pump(session, lambda _: None)  # type: ignore[arg-type]

        assert session.closed >= 1


class TestInstruction:
    def test_names_itself_honestly_and_credits_the_family(self) -> None:
        instruction = build_instruction()

        assert "小船" in instruction
        assert "不是人" in instruction
        assert "伟伦" in instruction

    def test_forbids_telling_her_she_has_repeated_herself(self) -> None:
        assert "你讲过了" in build_instruction()

    def test_caps_clarifying_questions(self) -> None:
        assert "最多问两个" in build_instruction()

    def test_an_unseeded_agent_carries_no_learned_layer(self) -> None:
        assert "---" not in build_instruction()

    def test_learned_preferences_change_the_instruction(self) -> None:
        """The visible proof of memory: session 5's instruction differs from
        session 1's because of what she said in between."""
        first = build_instruction()
        later = build_instruction(
            preferences=[
                Preference(
                    type=PreferenceType.HEARING, value="左耳不好", confidence=0.9
                )
            ],
            sensitivities=fold_sensitivities(
                [],
                [TopicSignal(topic="姐姐", kind=AvoidanceKind.REFUSED)],
                conversation_id="conv_003",
            ),
        )

        assert later != first
        assert "左耳不好" in later
        assert "姐姐" in later

    def test_a_subject_she_reopened_is_not_carried_as_forbidden(self) -> None:
        instruction = build_instruction(
            sensitivities=[
                SensitiveTopic(topic="关店的原因", refusals=1, engagements=1)
            ]
        )

        assert "关店的原因" not in instruction
