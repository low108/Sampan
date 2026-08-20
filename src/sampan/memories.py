"""The image at the head of a story card, generated off the critical path.

    finish_call ──publish──> Pub/Sub topic ──push──> POST /internal/memories
                                                          │
                                                          ├── Veo ──> mp4
                                                          └── GCS + Firestore

Pub/Sub here and not for the Archivist (D17, D21). The two look like the same
problem and are not. Extraction is seconds, runs once per call, and its output
is the thing the product exists to keep, so an in-process worker with the
transcript already written is the right trade. Veo is tens of seconds to
minutes, produces something the card is complete without, and would otherwise
have to run somewhere on the request path. A queue is what lets a card open
immediately and acquire its picture later, which is the only acceptable order.

Nothing here is called during a call. The publish is a fire-and-forget at the
end of `finish_call`; if the topic does not exist, the archive is unaffected.
"""

from __future__ import annotations

import json
import re
from typing import Any, Protocol

from pydantic import BaseModel, Field

from sampan.config import Settings

TOPIC = "sampan-memories"

# A card is 390x196 and the source is 16:9; anything longer than a few seconds
# is a film, not a photograph that breathes.
CLIP_SECONDS = 4
MODEL = "veo-3.1-fast-generate-001"


class MemoryRequest(BaseModel):
    """One story that could use an image. The whole Pub/Sub message."""

    narrator_id: str
    story_id: str
    title: str
    # Her own words, which is what the prompt is built from -- not a summary of
    # them, and not anything the model inferred.
    sense_detail: str = ""
    where_said: str = ""
    year: int | None = None


class MemoryAsset(BaseModel):
    """Where the finished clip lives, once there is one."""

    story_id: str
    video_url: str = ""
    still_url: str = ""
    prompt: str = ""
    model: str = MODEL
    created_at: str = ""


class VideoGenerator(Protocol):
    """The Veo call, behind a seam so the pipeline is testable without it."""

    def generate(self, prompt: str) -> bytes: ...


class Blobs(Protocol):
    """Object storage. An mp4 is ~1.2 MB and a Firestore document caps at 1 MB,
    so the bytes cannot live beside the rest of the archive."""

    def put(self, path: str, data: bytes, content_type: str) -> str: ...


# Rooms, never people.
#
# Two inches below this image sits the quote box, which is the one element the
# whole design protects. A generated face beside her verbatim words puts an
# invented person exactly where the product promises a real memory, and a
# viewer cannot tell the two apart. Rooms carry the feeling without the claim.
_NO_PEOPLE = (
    "Absolutely no people, no faces, no figures. Static locked-off camera, "
    "almost no movement -- only dust, smoke or light shifting. Documentary "
    "still-life photograph, warm amber and deep brown, fine natural grain, "
    "shallow depth of field. Full-bleed photographic frame: no border, no film "
    "sprockets, no text or markings anywhere in the image."
)

# "35mm film" produced a literal film frame, sprocket holes and edge markings
# included, on one of two runs. The look wanted is the photograph, not the
# stock it was shot on.
_BANNED = re.compile(r"\b(35\s*mm|film stock|polaroid|negative)\b", re.I)


def build_prompt(request: MemoryRequest) -> str:
    """Turn one story into something Veo can film.

    Built from what she said rather than from the story's title alone, because
    the title is the Archivist's phrasing and the sense detail is hers.
    """
    where = request.where_said.strip()
    era = f"in {request.year}" if request.year else "in mid-century Malaya"
    subject = request.sense_detail.strip() or request.title.strip()

    scene = f"A quiet interior {era}"
    if where:
        scene += f", {where}"
    scene += f". The scene around this, unpeopled: {subject.rstrip('.')}."

    return _BANNED.sub("", f"{scene} {_NO_PEOPLE}").strip()


def render(
    request: MemoryRequest, generator: VideoGenerator, blobs: Blobs
) -> MemoryAsset:
    """Generate one clip and put it where the card can reach it.

    Pure in the ways that matter: the model and the bucket are both injected,
    so the whole path is exercisable with fakes.
    """
    from datetime import UTC, datetime

    prompt = build_prompt(request)
    data = generator.generate(prompt)
    path = f"memories/{request.narrator_id}/{request.story_id}.mp4"
    url = blobs.put(path, data, "video/mp4")
    return MemoryAsset(
        story_id=request.story_id,
        video_url=url,
        prompt=prompt,
        created_at=datetime.now(UTC).isoformat(),
    )


class VeoGenerator:
    """Veo, via Vertex. Long-running by nature: this blocks for tens of seconds
    and is the entire reason the work is queued rather than done in a call."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def generate(self, prompt: str) -> bytes:
        import time

        from google import genai
        from google.genai import types

        client = genai.Client(
            vertexai=True,
            project=self._settings.project_id,
            # Veo is served from the Live region, not the text region.
            location=self._settings.live_location,
        )
        operation = client.models.generate_videos(
            model=MODEL,
            prompt=prompt,
            config=types.GenerateVideosConfig(
                aspect_ratio="16:9", number_of_videos=1, duration_seconds=CLIP_SECONDS
            ),
        )
        while not operation.done:
            time.sleep(10)
            operation = client.operations.get(operation)
        if operation.error:
            raise RuntimeError(str(operation.error))
        videos = getattr(operation.response, "generated_videos", None) or []
        if not videos:
            raise RuntimeError("Veo returned no video")
        return bytes(videos[0].video.video_bytes or b"")


class BucketBlobs:
    """A GCS bucket, public-read so a card can use the URL directly."""

    def __init__(self, bucket: str) -> None:
        self._bucket = bucket

    def put(self, path: str, data: bytes, content_type: str) -> str:
        from google.cloud import storage

        blob = storage.Client().bucket(self._bucket).blob(path)
        blob.upload_from_string(data, content_type=content_type)
        return f"https://storage.googleapis.com/{self._bucket}/{path}"


def publish(settings: Settings, request: MemoryRequest) -> bool:
    """Ask for a memory. Never raises.

    Fire and forget, and deliberately so: this runs at the end of a call, and a
    missing topic or a Pub/Sub outage must not cost her the stories that call
    produced. Returns whether it was queued, for callers that want to know.
    """
    if not settings.configured or not settings.memories_topic:
        return False
    try:
        from google.cloud import pubsub_v1

        publisher = pubsub_v1.PublisherClient()
        topic = publisher.topic_path(settings.project_id, settings.memories_topic)
        publisher.publish(
            topic, json.dumps(request.model_dump(mode="json")).encode("utf-8")
        ).result(timeout=10)
        return True
    except Exception:  # noqa: BLE001 -- an image is never worth a failed call
        return False


def decode_push(body: dict[str, Any]) -> MemoryRequest | None:
    """Read a Pub/Sub push envelope.

    Push delivers `{"message": {"data": "<base64>"}}`. Returns None rather than
    raising for anything unreadable, because a push endpoint that 500s gets the
    same message redelivered forever.
    """
    import base64

    try:
        raw = ((body or {}).get("message") or {}).get("data")
        if not raw:
            return None
        return MemoryRequest.model_validate(json.loads(base64.b64decode(raw)))
    except Exception:  # noqa: BLE001
        return None


class MemoryStore(BaseModel):
    """Assets by story id, kept in Firestore beside everything else."""

    assets: dict[str, MemoryAsset] = Field(default_factory=dict)
