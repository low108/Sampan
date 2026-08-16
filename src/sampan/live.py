"""The voice loop.

    Browser --WebSocket--> Cloud Run (FastAPI + ADK) --> Gemini Live API
                                |
                                +-- audio fork --> affect monitor

ADK is server-side and has no client-direct path, so the browser cannot talk to
the Live API itself: doing so would remove ADK entirely, taking tools, sessions
and the audio fork with it. The extra hop is the price of keeping them.

The fork is the two lines in `feed_audio`. ADK never touches the microphone —
the application pushes PCM into the queue — so a copy costs nothing and needs
no ADK hook. (There is no plugin callback for live audio; none is needed.)
"""

from __future__ import annotations

import asyncio
import base64
from collections import deque
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from typing import Any

from google.adk.agents import LiveRequestQueue, RunConfig
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from sampan.config import Settings

APP_NAME = "sampan"

# Live API contract: 16-bit PCM, 16 kHz mono in; 24 kHz out.
INPUT_MIME = "audio/pcm;rate=16000"
INPUT_SAMPLE_RATE = 16_000
OUTPUT_SAMPLE_RATE = 24_000
BYTES_PER_SAMPLE = 2

# Enough audio for the affect monitor's trailing window (ticket 13) without
# holding a whole call in memory.
AFFECT_WINDOW_SECONDS = 90
_RING_MAX_BYTES = AFFECT_WINDOW_SECONDS * INPUT_SAMPLE_RATE * BYTES_PER_SAMPLE


@dataclass
class AudioRingBuffer:
    """A rolling window of the user's audio, for the affect monitor.

    Deliberately bounded: an elderly user may talk for fifteen minutes and none
    of it needs to be held in memory beyond the analysis window.
    """

    max_bytes: int = _RING_MAX_BYTES
    _chunks: deque[bytes] = field(default_factory=deque)
    _size: int = 0

    def append(self, chunk: bytes) -> None:
        self._chunks.append(chunk)
        self._size += len(chunk)
        while self._size > self.max_bytes and self._chunks:
            self._size -= len(self._chunks.popleft())

    def snapshot(self) -> bytes:
        return b"".join(self._chunks)

    @property
    def seconds(self) -> float:
        return self._size / (INPUT_SAMPLE_RATE * BYTES_PER_SAMPLE)

    def clear(self) -> None:
        self._chunks.clear()
        self._size = 0


def build_run_config(settings: Settings) -> RunConfig:
    """Live API settings that are part of the contract, not preferences.

    `session_resumption` matters most: Live API audio sessions cap at roughly
    fifteen minutes, and a grandmother mid-story will hit that.
    """
    return RunConfig(
        response_modalities=[types.Modality.AUDIO],
        # Native affect adaptation. It shapes the model's replies but returns
        # no readout, so it complements the affect monitor rather than
        # replacing it.
        enable_affective_dialog=True,
        session_resumption=types.SessionResumptionConfig(transparent=True),
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
        max_llm_calls=500,
    )


@dataclass
class LiveSession:
    """One phone call.

    Owns the queue the browser feeds and the ring buffer the affect monitor
    reads. Closing it is idempotent so a dropped WebSocket and an explicit
    hang-up can both call it.
    """

    runner: Runner
    queue: LiveRequestQueue
    run_config: RunConfig
    user_id: str
    session_id: str
    audio: AudioRingBuffer = field(default_factory=AudioRingBuffer)
    on_audio: Callable[[bytes], None] | None = None
    _closed: bool = False

    def feed_audio(self, chunk: bytes) -> None:
        """Push one PCM chunk to the model, and keep a copy.

        These two lines are the entire audio fork. Everything the affect
        monitor needs is available here because ADK never captured the
        microphone in the first place.
        """
        self.queue.send_realtime(types.Blob(data=chunk, mime_type=INPUT_MIME))
        self.audio.append(chunk)
        if self.on_audio is not None:
            self.on_audio(chunk)

    def feed_text(self, text: str) -> None:
        """Used by the family voice-note path and by tests."""
        self.queue.send_content(
            types.Content(role="user", parts=[types.Part(text=text)])
        )

    # NOTE: there is deliberately no `steer()` here.
    #
    # A live session's system instruction is sent once at connect, so a dynamic
    # instruction provider never reaches it, and every way of injecting
    # direction mid-call was tried and fails:
    #   role="user"   — the agent reads the stage direction out loud, fence and
    #                   all, to an eighty-year-old
    #   role="system" — the agent acknowledges it aloud (「好的,明白了」)
    #   role="model"  — turn-taking breaks; it stops answering her
    #
    # So affect steers three other ways instead: it shapes the *next* call's
    # instruction, it rides back on tool responses (which are never spoken),
    # and `enable_affective_dialog` handles in-turn adaptation natively.
    # See FINDINGS.md.

    async def events(self) -> AsyncIterator[Any]:
        async for event in self.runner.run_live(
            user_id=self.user_id,
            session_id=self.session_id,
            live_request_queue=self.queue,
            run_config=self.run_config,
        ):
            yield event

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self.queue.close()


async def open_session(
    agent: Any,
    settings: Settings,
    *,
    user_id: str,
    session_id: str | None = None,
    session_service: Any | None = None,
) -> LiveSession:
    """Start a call. The browser then feeds audio and drains events."""
    service = session_service or InMemorySessionService()
    session = await service.create_session(
        app_name=APP_NAME, user_id=user_id, session_id=session_id
    )
    runner = Runner(app_name=APP_NAME, agent=agent, session_service=service)
    return LiveSession(
        runner=runner,
        queue=LiveRequestQueue(),
        run_config=build_run_config(settings),
        user_id=user_id,
        session_id=session.id,
    )


def encode_event(event: Any) -> dict[str, Any] | None:
    """Translate one ADK event into something the browser can use.

    Returns None for events the client has no use for, so the socket carries
    only what it will act on.
    """
    payload: dict[str, Any] = {}

    content = getattr(event, "content", None)
    if content is not None and getattr(content, "parts", None):
        for part in content.parts:
            inline = getattr(part, "inline_data", None)
            if inline is not None and inline.data:
                payload["audio"] = base64.b64encode(inline.data).decode("ascii")
                payload["sample_rate"] = OUTPUT_SAMPLE_RATE
            if getattr(part, "text", None):
                payload["text"] = part.text
            # Surfaced for the demo overlay: watching the agent reach for
            # memory mid-sentence is the clearest evidence that it has any.
            call = getattr(part, "function_call", None)
            if call is not None and getattr(call, "name", None):
                payload.setdefault("tool_calls", []).append(call.name)

    for flag in ("turn_complete", "interrupted"):
        if getattr(event, flag, None):
            payload[flag] = True

    for attribute, key in (
        ("input_transcription", "user_transcript"),
        ("output_transcription", "agent_transcript"),
    ):
        transcription = getattr(event, attribute, None)
        if transcription is not None and getattr(transcription, "text", None):
            payload[key] = transcription.text

    return payload or None


async def pump(session: LiveSession, send: Callable[[dict[str, Any]], Any]) -> None:
    """Drain model events to the client until the call ends.

    Never leave `run_live` early. Its generator raises
    `RuntimeError: generator didn't stop after athrow()` if you break, return
    or cancel out of it — and a browser disconnect does exactly that on every
    call. Close the queue instead and let the generator finish on its own; the
    RuntimeError is suppressed for the cases where it cannot.
    """
    try:
        async for event in session.events():
            message = encode_event(event)
            if message is None:
                continue
            try:
                result = send(message)
                if asyncio.iscoroutine(result):
                    await result
            except Exception:
                # The client hung up. Stop feeding the model and let the
                # generator wind down rather than tearing it out.
                session.close()
    except asyncio.CancelledError:
        session.close()
        raise
    except RuntimeError as error:
        if "generator didn't stop" not in str(error):
            raise
    finally:
        session.close()
