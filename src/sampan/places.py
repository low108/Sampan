"""Putting her places on a map.

A conventional geocoder is the wrong tool here. The places that matter most in
this archive are the ones it handles worst: a village in Fujian named the way
her father said it, a rubber estate near Sungai Siput that stopped existing
decades ago, "the shop street" rather than Jalan Bandar. A geocoder returns either
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
    # elsewhere — "my father's coffee shop" sits on Jalan Bandar because she
    # said so.
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
        matter most here: "Sungai Siput" came back as Sungkai, a real Perak town
        ninety kilometres from the one she meant. Anything coarser than a
        street is shown as provisional, because a plausible wrong pin is worse
        than an obviously missing one — nobody corrects what looks right.
        """
        return self.locatable and self.precision in (
            Precision.TOWN,
            Precision.REGION,
        )


RESOLUTION_PROMPT = """\
Below are place names from the oral history of an elderly Malaysian Chinese
woman. She is describing places as they were decades ago, using the names used
then, and some of them no longer exist.

Locate them as well as you can, but **be honest about precision**:
- exact: you are sure which specific spot this is
- street: you know the street or the immediate area
- town: only down to the town or city
- region: only down to the state, district or province
- unknown: you cannot place it. **If you cannot, say unknown — do not offer a
  plausible-looking guess.**

note: if imprecise, one line on why (e.g. "the estate no longer exists, only
locatable to Sungai Siput").
display_name: the name to show the family, e.g. "Jalan Bandar, Ipoh".

Place names:{names}
"""


class PlaceResolver(Protocol):
    def resolve(self, names: list[str]) -> list[Place]: ...


class _Geocoded(BaseModel):
    """What the resolver is allowed to answer with.

    Deliberately not `Place`. `Place` also carries `linked_from` and
    `linked_evidence`, which belong to the linker and are only trustworthy
    because the linker checks the evidence against the transcript. Handed a
    schema containing those fields, the resolver filled them in unprompted --
    "Identified as being in the vicinity of Sungai Siput" -- and because they
    arrived from geocoding rather than linking, nothing ever checked them. The
    pin looked justified and the sentence behind it was never said.

    A field the prompt does not govern does not belong in the schema.
    """

    raw_name: str
    lat: float | None = None
    lng: float | None = None
    precision: Precision = Precision.UNKNOWN
    country: str = ""
    display_name: str = ""
    note: str = ""
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)


class _Batch(BaseModel):
    places: list[_Geocoded]


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
        return [Place(**geocoded.model_dump()) for geocoded in parsed.places]


LINK_PROMPT = """\
When an elderly person tells her own story she often gives no address, only a
relationship — "my father's coffee shop", "home", "the place we lived". But
somewhere else, she may already have said where that place is.

Below are place names that could not be located, and place names whose location
is known. Which of the relational names actually refer to the known places?

**Every link needs evidence.** The evidence field must be a sentence she
actually said that proves the relationship.
- GOOD  she said "in 1958 he opened a coffee shop in Ipoh, at Jalan Bandar"
        -> "my father's coffee shop" = Jalan Bandar
- BAD   "home" is probably where she lived -- that is a guess, do not link it

If there is no evidence, **do not link it.** Leaving it blank is fine; the
family will fill it in.

Could not be located:
{unknown}

Location known:
{known}

What she said:
---
{transcripts}
---
"""


class PlaceLink(BaseModel):
    raw_name: str = Field(
        description='The relational name, e.g. "my father\'s coffee shop"'
    )
    resolves_to: str = Field(description="A place she named elsewhere")
    evidence: str = Field(description="Her own sentence proving the link")
    confidence: float = Field(ge=0.0, le=1.0)


class _Links(BaseModel):
    links: list[PlaceLink]


class GeminiPlaceLinker:
    """Place a story by what she said elsewhere, never by inference.

    Her best stories name places by relationship — "my father's coffee shop",
    "home" —
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
        known_names = {p.raw_name for p in known}
        return [
            link
            for link in parsed.links
            if link.resolves_to in known_names
            and _is_quoted(link.evidence, transcripts)
        ]


def _is_quoted(evidence: str, transcripts: str) -> bool:
    """Whether the evidence is something she actually said.

    Asking for a quote is not enough. Given a required evidence field, the
    model will fill it with its own reasoning — "Identified as being in the
    vicinity of Sungai Siput", "Specific street in Ipoh" — which reads like
    justification and proves nothing. The same failure as a sensory detail
    filled with a paraphrase, in a different field.

    So the claim is checked against the source: the evidence must appear in
    what she said. Comparison ignores case and whitespace, because the model
    re-punctuates freely, and a short fragment is rejected outright since
    almost any few words can be found somewhere in a long transcript.
    """
    claim = " ".join(evidence.strip().lower().split())
    if len(claim) < 20:
        return False
    haystack = " ".join(transcripts.lower().split())
    if claim in haystack:
        return True
    # Allow a trimmed quote: the model often drops a trailing clause.
    head = claim[: max(20, len(claim) // 2)]
    return head in haystack


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
                    "note": f'She said: "{link.evidence}"',
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
