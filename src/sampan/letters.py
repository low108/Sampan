"""Turning a pinned story into something the family can read.

Bilingual because of a real generational gap: she speaks Mandarin, her
granddaughter does not read Chinese, and a Chinese-only archive would be
inherited by people who cannot open it.

The letter is built around `sense_detail`. That constraint is the whole reason
the field is defended so hard upstream — a letter assembled from facts reads
like a database row, and one built around "a bowl of white rice with soy
sauce under a kerosene lamp" reads like
her.
"""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, Field

from sampan.config import Settings
from sampan.family import StoryCard

LETTER_PROMPT = """\
Below is a memory an elderly woman told in her own words, organised into a
record. Write it as a short letter for her family to read.

Rules:
- **First person, in her voice**, as though she were telling her granddaughter.
- Under 120 words. Short is better than long.
- **Build it around the sensory detail.** That line is the heart of the letter.
- Use only what is in the record. **Do not add events, feelings or scenes she
  did not describe.**
- Do not open with "I remember" or "in those days".
- Do not summarise, do not draw a lesson, do not reflect on life.

english: the same letter in English, for grandchildren who cannot read Chinese.
Not a word-for-word translation — it should read as a letter — but nothing may
change meaning.

title_en: a short English title.

The record:
title: {title}
when: {when} ({years})
where: {where}
people: {people}
sensory detail: {sense}
what she said: {narrative}
"""


class Letter(BaseModel):
    story_id: str = ""
    chinese: str = Field(description="In her voice, first person")
    english: str = Field(description="For the grandchild who cannot read Chinese")
    title_en: str = ""


class LetterWriter(Protocol):
    def write(self, card: StoryCard) -> Letter: ...


class GeminiLetterWriter:
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

    def write(self, card: StoryCard) -> Letter:
        from google.genai import types

        years = (
            f"{card.year_from or ''}–{card.year_to or ''}".strip("–") or "year unknown"
        )
        response = self._client.models.generate_content(
            model=self._settings.archivist_model,
            contents=LETTER_PROMPT.format(
                title=card.title,
                when=card.when_said or "not clearly said",
                years=years,
                where=card.where_said or "not clearly said",
                people=", ".join(card.people) or "none mentioned",
                sense=card.sense_detail or "(she gave no concrete detail)",
                narrative=card.narrative,
            ),
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=Letter,
                temperature=0.6,
            ),
        )
        parsed = response.parsed
        if parsed is None:
            raise RuntimeError(f"Letter returned no JSON: {response.text}")
        parsed.story_id = card.story_id
        return parsed


def worth_writing(card: StoryCard) -> bool:
    """Only pinned stories with a sensory detail get a letter.

    A letter without one would be a paraphrase of facts she already told
    better, and sending the family a worse version of her own words is worse
    than sending nothing.
    """
    return card.status == "pinnable" and bool(card.sense_detail.strip())
