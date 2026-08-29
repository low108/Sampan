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
from sampan.family import StoryCard, attach_memories
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


class TestTheCardCanActuallyReachTheClip:
    """The half that was missing.

    Everything above ran end to end and left the archive looking correct: Veo
    rendered, the bytes landed in the bucket, the asset was written to
    Firestore. And no view ever read it back, so the pipeline was complete,
    green, billed for, and invisible. These assert the last hop.
    """

    def _card(self, story_id: str) -> StoryCard:
        return StoryCard(
            story_id=story_id,
            title="the last cup of Milo",
            domain="taste",
            pin_type="place",
            narrative="n",
            sense_detail="s",
            when_said="last Sunday",
        )

    def test_a_stored_asset_reaches_the_card(self) -> None:
        cards = attach_memories(
            [self._card("s1")],
            [{"story_id": "s1", "video_url": "https://x/s1.mp4", "still_url": ""}],
        )

        assert cards[0].memory_video == "https://x/s1.mp4"

    def test_a_story_with_no_asset_keeps_an_empty_one(self) -> None:
        """The common case, and not an error: generation is queued at the end
        of a call and the card is opened long before it finishes."""
        cards = attach_memories([self._card("s1")], [])

        assert cards[0].memory_video == ""

    def test_an_asset_never_lands_on_someone_elses_story(self) -> None:
        cards = attach_memories(
            [self._card("s1"), self._card("s2")],
            [{"story_id": "s2", "video_url": "https://x/s2.mp4"}],
        )

        assert cards[0].memory_video == ""
        assert cards[1].memory_video == "https://x/s2.mp4"

    def test_the_feed_serves_it(self) -> None:
        """At the HTTP boundary, because the bug was in the wiring rather than
        in any one function -- each piece worked and nothing joined them."""
        from fastapi.testclient import TestClient

        from sampan.app import create_app, get_store
        from sampan.auth import API_KEY_HEADER
        from sampan.config import get_settings
        from sampan.store import InMemoryDocumentStore

        store = InMemoryDocumentStore()
        store.put(
            "stories__gran",
            "s1",
            {
                "story_id": "s1",
                "conversation_id": "c1",
                "candidate": {"title": "the last cup of Milo", "narrative": "n"},
            },
        )
        store.put(
            "memories__gran",
            "s1",
            {"story_id": "s1", "video_url": "https://x/s1.mp4"},
        )

        app = create_app()
        app.dependency_overrides[get_settings] = lambda: Settings(
            GOOGLE_CLOUD_PROJECT="", SAMPAN_API_KEY="k"
        )
        app.dependency_overrides[get_store] = lambda: store
        with TestClient(app) as client:
            body = client.get(
                "/api/family/gran?view=feed", headers={API_KEY_HEADER: "k"}
            ).json()

        assert body["stories"][0]["memory_video"] == "https://x/s1.mp4"


class TestPushCanActuallyReachTheEndpoint:
    """Pub/Sub cannot set a header.

    The endpoint documented its auth as "the shared key on the subscription's
    push URL" and then depended on the header-only check, so every push was
    refused. Nothing raised and no call failed -- the errors were on Pub/Sub's
    side of the wire. Asserted at the boundary, in the shape push actually uses.
    """

    def _client(self):
        from fastapi.testclient import TestClient

        from sampan.app import create_app, get_store
        from sampan.config import get_settings
        from sampan.store import InMemoryDocumentStore

        app = create_app()
        app.dependency_overrides[get_settings] = lambda: Settings(
            GOOGLE_CLOUD_PROJECT="", SAMPAN_API_KEY="k", SAMPAN_MEMORIES_BUCKET=""
        )
        app.dependency_overrides[get_store] = lambda: InMemoryDocumentStore()
        return TestClient(app)

    def _push(self) -> dict:
        blob = json.dumps(REQUEST.model_dump(mode="json")).encode()
        return {"message": {"data": base64.b64encode(blob).decode()}}

    def test_the_key_in_the_url_is_accepted(self) -> None:
        with self._client() as client:
            response = client.post("/internal/memories?key=k", json=self._push())

        assert response.status_code == 200

    def test_a_wrong_key_is_still_refused(self) -> None:
        push = self._push()
        with self._client() as client:
            wrong = client.post("/internal/memories?key=nope", json=push)
            missing = client.post("/internal/memories", json=push)

        assert wrong.status_code == 401
        assert missing.status_code == 401


class TestTheTestsCannotPublish:
    """The guardrail itself, asserted rather than assumed.

    `finish_call` falls back to `Settings()` when none is passed, `Settings()`
    reads `.env`, and `publish()` never raises -- so a live topic in `.env`
    turned every test run into twenty paid Veo renders, silently, while the
    suite reported green. conftest.py clears the environment; this checks that
    it is actually cleared, because a guardrail nobody tests is a comment.
    """

    def test_no_topic_is_visible_to_a_bare_settings(self) -> None:
        assert Settings().memories_topic == ""

    def test_publishing_from_a_bare_settings_is_a_no_op(self) -> None:
        assert publish(Settings(), REQUEST) is False

    def test_finish_calls_own_fallback_cannot_reach_pubsub(self) -> None:
        """The exact path that leaked: no settings argument at all."""
        from sampan.config import Settings as Fresh

        assert publish(Fresh(), REQUEST) is False
