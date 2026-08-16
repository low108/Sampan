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
你在帮一个家庭了解他们的长辈。下面是这位长辈亲口讲过的事,整理出来的。

回答家人的问题,规矩如下:

1. **只讲她讲过的。** 她没讲过的,就说她没讲过。不要用你对那个年代、
   那个地方的常识去补。宁可答不出来。

2. 尽量**用她自己的话**。她的原话比任何转述都好。

3. 答完之后,如果这件事她其实**没讲清楚**,就在 follow_up 提一个问题 ——
   下次小船打给她的时候可以替家人问。这是这个功能最有用的地方:
   把「不知道」变成「下次问她」。

4. 用问的人的语言回答。他用中文问就中文答,用英文问就英文答。
   answer_en 一律填英文版,给看不懂中文的孙辈。

5. 简短。两三句就好,不要写作文。

---
她是谁:{who}

她讲过的事:
{stories}

她提到过的人和地方:
{entities}
---

家人问:{question}
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
        when = card.when_said or "(没讲时间)"
        years = (
            f"{card.year_from or ''}–{card.year_to or ''}".strip("–")
            if (card.year_from or card.year_to)
            else "年份不详"
        )
        lines.append(
            f"[{card.story_id}] {card.title} · {when} ({years}) · "
            f"{card.where_said or '没讲地点'}\n"
            f"  人:{'、'.join(card.people) or '没提到'}\n"
            f"  她的话:{card.sense_detail or '(没有)'}\n"
            f"  经过:{card.narrative}\n"
            f"  还没讲到:{'、'.join(card.missing_fields) or '(都讲了)'}"
        )
    return "\n\n".join(lines)


def _render_entities(entities: list[Entity]) -> str:
    return "\n".join(
        f"- {e.canonical_name} ({e.type.value}"
        + (f", {e.role}" if e.role else "")
        + f"): {e.detail or '没有更多'}"
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
                answer="她还没讲过什么。打个电话给她吧。",
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
