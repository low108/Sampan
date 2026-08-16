"""Turning a pinned story into something the family can read.

Bilingual because of a real generational gap: she speaks Mandarin, her
granddaughter does not read Chinese, and a Chinese-only archive would be
inherited by people who cannot open it.

The letter is built around `sense_detail`. That constraint is the whole reason
the field is defended so hard upstream — a letter assembled from facts reads
like a database row, and one built around 「煤油灯下一碗白饭配酱油」 reads like
her.
"""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, Field

from sampan.config import Settings
from sampan.family import StoryCard

LETTER_PROMPT = """\
下面是一位老人家亲口讲的一段回忆,已经整理成资料。
请写成一封短短的信,给她的家人看。

规矩:
- **用第一人称,用她的口气**,像她自己在讲给孙女听
- 一百二十字以内。短比长好
- **一定要围绕那个感官细节来写**。那一句是这封信的心
- 只能用资料里有的东西。**不要加她没讲过的情节、感受或场景**
- 不要写「我记得」「那些年」这种套话开头
- 不要总结,不要给道理,不要感叹人生

english: 同样的一封信,翻成英文给看不懂中文的孙辈看。
不要逐字直译,要读起来像一封信,但意思不可以跑掉。

title_en: 英文标题,短。

资料:
标题:{title}
时间:{when}({years})
地点:{where}
人物:{people}
感官细节:{sense}
她讲的内容:{narrative}
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

        years = f"{card.year_from or ''}–{card.year_to or ''}".strip("–") or "年份不详"
        response = self._client.models.generate_content(
            model=self._settings.archivist_model,
            contents=LETTER_PROMPT.format(
                title=card.title,
                when=card.when_said or "没讲清楚",
                years=years,
                where=card.where_said or "没讲清楚",
                people="、".join(card.people) or "没提到",
                sense=card.sense_detail or "(她没讲到具体细节)",
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
