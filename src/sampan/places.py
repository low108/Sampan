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
    # Set when this place was placed by linking it to somewhere she named
    # elsewhere — 「爸爸的咖啡店」 sits on 板底街 because she said so.
    linked_from: str = ""
    linked_evidence: str = ""

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


LINK_PROMPT = """\
一位老人家讲自己的故事时,常常不讲地址,只讲关系 ——「爸爸的咖啡店」、「家里」、
「我们住的地方」。可是她在别的时候,可能已经讲过那个地方在哪里。

下面是她提到过、但定不到位置的地名,以及她已经讲清楚位置的地名。
请判断:哪些「关系型」的地名,其实指的就是那些已知的地方?

**一定要有根据。** evidence 栏位必须是她自己讲过的一句话,能证明这个关系。
- ✅ 她讲过「一九五八年在怡保开了一间咖啡店,在板底街」
     → 「爸爸的咖啡店」 = 板底街
- ❌ 「家里」大概就是她住的地方吧 —— 这是猜的,不要连

找不到根据就**不要连**。宁可留白,家里人自己会补。

定不到的地名:
{unknown}

已经知道位置的地名:
{known}

她讲过的话:
---
{transcripts}
---
"""


class PlaceLink(BaseModel):
    raw_name: str = Field(description="The relational name, e.g. 爸爸的咖啡店")
    resolves_to: str = Field(description="A place she named elsewhere")
    evidence: str = Field(description="Her own sentence proving the link")
    confidence: float = Field(ge=0.0, le=1.0)


class _Links(BaseModel):
    links: list[PlaceLink]


class GeminiPlaceLinker:
    """Place a story by what she said elsewhere, never by inference.

    Her best stories name places by relationship — 「爸爸的咖啡店」, 「家里」 —
    and a geocoder can do nothing with those. But she often gave the address in
    another session, so the information is already in the archive and only
    needs joining. Every link must carry the sentence that justifies it.
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

    def link(
        self, unknown: list[str], known: list[Place], transcripts: str
    ) -> list[PlaceLink]:
        if not unknown or not known or not transcripts.strip():
            return []
        from google.genai import types

        response = self._client.models.generate_content(
            model=self._settings.archivist_model,
            contents=LINK_PROMPT.format(
                unknown="\n".join(f"- {n}" for n in unknown),
                known="\n".join(
                    f"- {p.raw_name} ({p.display_name or p.raw_name})" for p in known
                ),
                transcripts=transcripts[:60000],
            ),
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=_Links,
                temperature=0.0,
            ),
        )
        parsed = response.parsed
        if parsed is None:
            return []
        # A link without her words behind it is a guess, and guesses are what
        # this whole mechanism exists to avoid.
        return [
            link
            for link in parsed.links
            if link.evidence.strip() and link.resolves_to in {p.raw_name for p in known}
        ]


def apply_links(places: list[Place], links: list[PlaceLink]) -> list[Place]:
    """Give linked places the coordinates of the place she named."""
    by_name = {p.raw_name: p for p in places}
    out = []
    for place in places:
        link = next((x for x in links if x.raw_name == place.raw_name), None)
        parent = by_name.get(link.resolves_to) if link else None
        if link is None or parent is None or not parent.locatable:
            out.append(place)
            continue
        out.append(
            place.model_copy(
                update={
                    "lat": parent.lat,
                    "lng": parent.lng,
                    # Never more precise than the place it borrowed from.
                    "precision": parent.precision,
                    "country": parent.country,
                    "confidence": min(link.confidence, parent.confidence),
                    "linked_from": parent.raw_name,
                    "linked_evidence": link.evidence,
                    "note": f"她讲过:「{link.evidence}」",
                }
            )
        )
    return out


def split_tray(places: list[Place]) -> tuple[list[Place], list[Place]]:
    """Pins for the map, and the tray of places the family can help with.

    The tray is deliberately visible rather than hidden: an unplaced story is
    not a failure, it is a question for the next call.
    """
    pinned = [p for p in places if p.locatable]
    unlocated = [p for p in places if not p.locatable]
    return pinned, unlocated
