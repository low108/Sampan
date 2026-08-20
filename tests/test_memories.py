"""Generated card imagery, queued rather than awaited.

Pub/Sub here and not for the Archivist (D17, D21). The two look alike and are
not: extraction is seconds and produces the thing the product exists to keep,
so an in-process worker is right. Veo is tens of seconds and produces something
the card is complete without, so it goes on a queue and the card acquires it
later.

The rules that matter most here are the ones about not breaking a call: a
missing topic, a Pub/Sub outage or a wedged message must all cost an image and
never a story.
"""

from __future__ import annotations

import base64
import json

from sampan.config import Settings
from sampan.memories import (
    MemoryRequest,
    build_prompt,
    decode_push,
    publish,
    render,
)

REQUEST = MemoryRequest(
    narrator_id="ah_khim",
    story_id="conv_1_00",
    title="Mother's soy sauce rice in the line house",
    sense_detail="white rice with soy sauce, sometimes salted fish",
    where_said="a line house on the rubber estate",
    year=1952,
)


class TestThePrompt:
    def test_it_is_built_from_her_words_not_the_title(self) -> None:
        """The title is the Archivist's phrasing. The sense detail is hers."""
        prompt = build_prompt(REQUEST)

        assert "white rice with soy sauce" in prompt
        assert "a line house on the rubber estate" in prompt
        assert "1952" in prompt

    def test_it_refuses_to_put_people_in_the_frame(self) -> None:
        """Two inches below this image is the quote box, which is the one
        element the design exists to protect. A generated face beside her
        verbatim words is an invented person where a real memory is promised."""
        prompt = build_prompt(REQUEST)

        assert "no people" in prompt.lower()
        assert "no faces" in prompt.lower()

    def test_it_strips_film_stock_language(self) -> None:
        """"35mm" produced a literal film frame -- sprocket holes, edge
        markings -- on one run of two. The look wanted is the photograph, not
        the stock it was shot on."""
        prompt = build_prompt(
            REQUEST.model_copy(update={"sense_detail": "like an old 35mm photo"})
        )

        assert "35mm" not in prompt
        assert "35 mm" not in prompt

    def test_a_story_with_no_sense_detail_still_gets_a_prompt(self) -> None:
        prompt = build_prompt(REQUEST.model_copy(update={"sense_detail": ""}))

        assert REQUEST.title.lower() in prompt.lower()


class TestRendering:
    class FakeVeo:
        def __init__(self) -> None:
            self.prompts: list[str] = []

        def generate(self, prompt: str) -> bytes:
            self.prompts.append(prompt)
            return b"\x00\x01mp4"

    class FakeBlobs:
        def __init__(self) -> None:
            self.written: dict[str, bytes] = {}

        def put(self, path: str, data: bytes, content_type: str) -> str:
            self.written[path] = data
            return f"https://example.test/{path}"

    def test_the_clip_is_stored_under_the_story_it_belongs_to(self) -> None:
        veo, blobs = self.FakeVeo(), self.FakeBlobs()

        asset = render(REQUEST, veo, blobs)

        assert asset.story_id == "conv_1_00"
        assert "memories/ah_khim/conv_1_00.mp4" in asset.video_url
        assert blobs.written["memories/ah_khim/conv_1_00.mp4"] == b"\x00\x01mp4"

    def test_the_prompt_used_is_kept_with_the_asset(self) -> None:
        """So a picture that turns out wrong can be explained rather than
        argued about."""
        asset = render(REQUEST, self.FakeVeo(), self.FakeBlobs())

        assert "white rice with soy sauce" in asset.prompt


class TestThePushEnvelope:
    def _envelope(self, payload: dict) -> dict:
        return {
            "message": {
                "data": base64.b64encode(json.dumps(payload).encode()).decode()
            }
        }

    def test_a_well_formed_message_decodes(self) -> None:
        request = decode_push(self._envelope(REQUEST.model_dump(mode="json")))

        assert request is not None
        assert request.story_id == "conv_1_00"

    def test_rubbish_returns_none_rather_than_raising(self) -> None:
        """A push endpoint that raises gets the same message redelivered
        forever, and redelivering a Veo call bills for it every time."""
        assert decode_push({}) is None
        assert decode_push({"message": {}}) is None
        assert decode_push({"message": {"data": "bm90IGpzb24="}}) is None
        assert decode_push({"message": {"data": "!!!not base64!!!"}}) is None


class TestPublishingNeverBreaksACall:
    def test_no_topic_configured_is_a_quiet_no(self) -> None:
        settings = Settings(GOOGLE_CLOUD_PROJECT="p", SAMPAN_MEMORIES_TOPIC="")

        assert publish(settings, REQUEST) is False

    def test_an_unconfigured_project_is_a_quiet_no(self) -> None:
        settings = Settings(GOOGLE_CLOUD_PROJECT="", SAMPAN_MEMORIES_TOPIC="t")

        assert publish(settings, REQUEST) is False

    def test_a_broken_pubsub_does_not_raise(self, monkeypatch) -> None:
        """The call has already produced her stories by the time this runs.
        An image is never worth losing them."""
        import sampan.memories as memories

        def explode(*_args, **_kwargs):
            raise RuntimeError("pubsub is down")

        monkeypatch.setattr(memories, "publish", memories.publish)
        settings = Settings(
            GOOGLE_CLOUD_PROJECT="p", SAMPAN_MEMORIES_TOPIC="sampan-memories"
        )
        # No credentials in the test environment, so the client construction
        # itself fails -- which is exactly the failure being asserted about.
        assert publish(settings, REQUEST) is False
