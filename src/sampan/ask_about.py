"""An agent that knows one person, for the family who want to ask about her.

Xin Yi is nineteen, cannot read Chinese, and loves her grandmother. She will
not scroll eleven stories to find out what her great-grandfather did. She will
type "what did her father do?" and expect an answer.

Two rules make this worth having rather than a summarizer:

- **It answers only from what she said.** Not from what a model knows about
  1950s Malaya. If the archive does not contain it, it says so.
- **A gap becomes a question.** "She never said which house" is not a dead end;
  it is the next thing to ask her, and this agent can queue it.

Whole-archive context, not retrieval: eleven stories fit in a prompt, and at
this scale retrieval machinery buys nothing (ConvoMem, 2025).
"""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, Field

from sampan.config import Settings
from sampan.family import StoryCard
from sampan.models import Entity

ANSWER_PROMPT = """\
You are helping a family understand an elder of theirs. Below is what she has
told, in her own words, organised into records.

Answer the family's question by these rules:

1. **Only from what she said.** If she never said it, say so. Do not fill the
   gap with what you know about the period or the place. Better to have no
   answer.

2. Use **her own words** wherever you can. They beat any paraphrase.

3. After answering, if she never actually made this clear, put a question in
   `follow_up` — something Xiao Chuan can ask her on the next call. This is the
   most useful thing here: turning "we don't know" into "we'll ask her".

4. Answer in the language they asked in. `answer_en` is always the English
   version, for grandchildren who need it.

5. Keep it short. Two or three sentences, not an essay.

---
Who she is: {who}

What she has told:
{stories}

People and places she has mentioned:
{entities}
---

The family asks: {question}
"""


class Answer(BaseModel):
    answer: str = Field(description="In the language they asked in")
    answer_en: str = Field(default="", description="For grandchildren who need it")
    # Which stories this came from, so they can go and read her actual words.
    from_stories: list[str] = Field(default_factory=list)
    she_never_said: bool = Field(
        default=False, description="True when the archive simply does not have it"
    )
    follow_up: str = Field(
        default="",
        description="A question worth asking her next call, if something is missing",
    )


class AboutHer(Protocol):
    def answer(self, question: str) -> Answer: ...


def _render_stories(cards: list[StoryCard]) -> str:
    lines = []
    for card in cards:
        when = card.when_said or "(no time given)"
        years = (
            f"{card.year_from or ''}–{card.year_to or ''}".strip("–")
            if (card.year_from or card.year_to)
            else "year unknown"
        )
        lines.append(
            f"[{card.story_id}] {card.title} · {when} ({years}) · "
            f"{card.where_said or 'no place given'}\n"
            f"  people: {', '.join(card.people) or 'none mentioned'}\n"
            f"  her words: {card.sense_detail or '(none)'}\n"
            f"  what happened: {card.narrative}\n"
            f"  not yet told: {', '.join(card.missing_fields) or '(all told)'}"
        )
    return "\n\n".join(lines)


def _render_entities(entities: list[Entity]) -> str:
    return "\n".join(
        f"- {e.canonical_name} ({e.type.value}"
        + (f", {e.role}" if e.role else "")
        + f"): {e.detail or 'nothing more'}"
        for e in entities
        if not e.merged_into
    )


class GeminiAboutHer:
    def __init__(
        self,
        settings: Settings,
        *,
        who: str,
        cards: list[StoryCard],
        entities: list[Entity],
    ) -> None:
        self._settings = settings
        self._who = who
        self._cards = cards
        self._entities = entities
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

    def answer(self, question: str) -> Answer:
        from google.genai import types

        if not self._cards:
            return Answer(
                answer="She hasn't told us anything yet. Give her a call.",
                answer_en="She hasn't told us anything yet. Give her a call.",
                she_never_said=True,
            )

        response = self._client.models.generate_content(
            model=self._settings.archivist_model,
            contents=ANSWER_PROMPT.format(
                who=self._who,
                stories=_render_stories(self._cards),
                entities=_render_entities(self._entities),
                question=question,
            ),
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=Answer,
                temperature=0.3,
            ),
        )
        parsed = response.parsed
        if parsed is None:
            raise RuntimeError(f"No parseable answer: {response.text}")
        # Only cite stories that exist. A citation to a story that is not there
        # is worse than none, because the point is that they can go and read it.
        known = {c.story_id for c in self._cards}
        parsed.from_stories = [s for s in parsed.from_stories if s in known]
        return parsed
