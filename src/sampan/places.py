"""Putting her places on a map.

A conventional geocoder is the wrong tool here. The places that matter most in
this archive are the ones it handles worst: a village in Fujian named the way
her father said it, a rubber estate near Sungai Siput that stopped existing
decades ago, 「板底街」 rather than Jalan Bandar. A geocoder returns either
nothing or a confident wrong answer.

So resolution is a model call that must state its own precision, and anything
it cannot place lands in the unlocated tray — a first-class state, shown to the
family to correct and fed back as a question for her next call.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Protocol

from pydantic import BaseModel, Field

from sampan.config import Settings


class Precision(StrEnum):
    """How exactly a place is known. Never guessed past what she said."""

    EXACT = "exact"
    STREET = "street"
    TOWN = "town"
    REGION = "region"
    UNKNOWN = "unknown"


class Place(BaseModel):
    raw_name: str
    lat: float | None = None
    lng: float | None = None
    precision: Precision = Precision.UNKNOWN
    country: str = ""
    display_name: str = Field(default="", description="What to show on the pin")
    note: str = Field(default="", description="Why it is imprecise, if it is")
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)

    @property
    def locatable(self) -> bool:
        return (
            self.lat is not None
            and self.lng is not None
            and self.precision is not Precision.UNKNOWN
        )

    @property
    def needs_confirmation(self) -> bool:
        """Whether the family should check this pin before it is trusted.

        Resolution produces confident wrong answers on exactly the names that
        matter most here: 「双溪镇」 came back as Sungkai, a real Perak town
        ninety kilometres from the one she meant. Anything coarser than a
        street is shown as provisional, because a plausible wrong pin is worse
        than an obviously missing one — nobody corrects what looks right.
        """
        return self.locatable and self.precision in (
            Precision.TOWN,
            Precision.REGION,
        )


RESOLUTION_PROMPT = """\
下面是一位马来西亚华人老人家口述历史里提到的地名。她说的是几十年前的地方,
用的是当年的叫法,有些地方现在已经不在了。

请尽量定位,但**precision 一定要老实**:
- exact: 确定是哪一个具体地点
- street: 知道是哪条街、哪一带
- town: 只能定到镇/市
- region: 只能定到州/县/省
- unknown: 定不到。**定不到就填 unknown,不要给一个像样的猜测**

note: 如果不精确,一句话讲为什么(例如「树胶园已不存在,只能定到双溪镇」)。
display_name: 给家里人看的名字,中英对照,例如「板底街 Jalan Bandar, 怡保」。

地名:{names}
"""


class PlaceResolver(Protocol):
    def resolve(self, names: list[str]) -> list[Place]: ...


class _Batch(BaseModel):
    places: list[Place]


class GeminiPlaceResolver:
    """Resolve place names in one batch call."""

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

    def resolve(self, names: list[str]) -> list[Place]:
        if not names:
            return []
        from google.genai import types

        response = self._client.models.generate_content(
            model=self._settings.archivist_model,
            contents=RESOLUTION_PROMPT.format(names="\n".join(f"- {n}" for n in names)),
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=_Batch,
                temperature=0.0,
            ),
        )
        parsed = response.parsed
        if parsed is None:
            return [Place(raw_name=name) for name in names]
        return list(parsed.places)


def split_tray(places: list[Place]) -> tuple[list[Place], list[Place]]:
    """Pins for the map, and the tray of places the family can help with.

    The tray is deliberately visible rather than hidden: an unplaced story is
    not a failure, it is a question for the next call.
    """
    pinned = [p for p in places if p.locatable]
    unlocated = [p for p in places if not p.locatable]
    return pinned, unlocated
