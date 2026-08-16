"""The Archivist — post-call extraction.

Runs after the conversation has ended, never during it. The Companion agent
never chases schema fields mid-call; whatever is missing here becomes a gentle
question in a later session instead.

`ingest_conversation` is the seam the pipeline is tested at (docs/spec-p0.md).
Ticket 2 fills in the story half; entities, threads, anchors and preferences
land on top in tickets 3-6.
"""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel

from sampan.config import Settings
from sampan.entities import Resolution, Tiebreaker, resolve_mentions
from sampan.models import Entity, EntityMention, ScoredStory, StoryCandidate, assess

EXTRACTION_PROMPT = """\
你是一位口述历史记录员。下面是一位老人家和陪伴她聊天的助手之间的对话记录。

请从对话中找出她讲的「故事」,并整理成结构化资料。

什么算一个故事:
- 有开头有结尾的一件事,不是笼统的感想
- 「我小时候很穷」不是故事;「我们吃白饭配酱油,妈妈说她已经吃过了」是故事
- 一次对话通常有 1 到 4 个故事。宁可少,不要硬凑

每个故事请尽量填齐这几样,但**绝对不要编造**。她没讲的就留空:
- where: 地点,用她自己讲的名字
- when: 时间。她常常讲相对时间(「结婚以前」、「大水那年」)。
  raw_phrase 一定要用她原本的话。能推算年份就填,不能就留空,
  precision 用 relative 或 era
- who: 出现的人,用她称呼的方式(「我姐姐」、「阿水」)
- what: 发生了什么事
- sense_detail: **最重要的一项**。**一个**具体的感官细节 —— 一种味道、
  一个声音、一个画面。只要一个,不要列一串。
  这是「事实」和「故事」的分别。找不到就留空,不要用形容词凑
- why_it_matters: 为什么这件事留在她心里
- narrative: 80-150 字,用第一人称,尽量用她原本的用词
- verbatim_quotes: 她的原话,一两句

pin_type 决定这个故事在哪里呈现,请照这个顺序判断:
- place: 有具体地点的事(在河边、在店里、在厝里)。**大部分故事都是 place**
- object: 故事是围绕一件东西的(缝纫机、结婚照、一件旗袍)
- person: 故事主要是在讲一个人是怎样的,没有特定地点
- timeline: 人生道理、感想、劝告,没有地点也没有单一事件
只要 where 有真实地点,就不要选 timeline。

sensitivity 标 sensitive 的情况:钱、跟在世亲人的冲突、健康、
她明显回避或转开话题的事。其他标 routine。

另外请列出 entity_mentions —— 对话里出现过的人、地方、东西、食物。
- surface_form 一定要用她原本的叫法(「我姐姐」就是「我姐姐」,不要改成名字)
- 同一个人在同一次对话里讲了几次,只列一次
- type: person / place / object / food
- role: 只有人才填 —— father, mother, elder_sister, husband, son, neighbour 等
- detail: 她讲过关于这个人/地方/东西的事,一句话就好

对话记录:
---
{transcript}
---
"""


class ExtractionResponse(BaseModel):
    stories: list[StoryCandidate]
    entity_mentions: list[EntityMention] = []


class ConversationOutcome(BaseModel):
    """Everything derived from one conversation.

    Grows as tickets land: threads, anchors and preferences join `stories` and
    `entities` here, and this stays the single return value of the seam.
    """

    stories: list[ScoredStory]
    entities: list[Entity] = []
    resolutions: list[Resolution] = []

    @property
    def pinned(self) -> list[ScoredStory]:
        return [s for s in self.stories if s.status == "pinnable"]

    @property
    def fragments(self) -> list[ScoredStory]:
        return [s for s in self.stories if s.status == "fragment"]

    @property
    def new_entities(self) -> list[Entity]:
        new_ids = {r.entity_id for r in self.resolutions if r.created}
        return [e for e in self.entities if e.entity_id in new_ids]


class StoryExtractor(Protocol):
    """Seam for the model call, so the pipeline can be exercised offline."""

    def extract(self, transcript: str) -> ExtractionResponse: ...


class GeminiStoryExtractor:
    """Structured extraction against Gemini.

    The client is built lazily so importing this module costs nothing and needs
    no credentials.
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

    def extract(self, transcript: str) -> ExtractionResponse:
        from google.genai import types

        response = self._client.models.generate_content(
            model=self._settings.archivist_model,
            contents=EXTRACTION_PROMPT.format(transcript=transcript),
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ExtractionResponse,
                temperature=0.2,
            ),
        )
        parsed = response.parsed
        if parsed is None:
            raise RuntimeError(
                f"Extraction returned no parseable JSON: {response.text}"
            )
        return parsed


def ingest_conversation(
    transcript: str,
    extractor: StoryExtractor,
    *,
    known_entities: list[Entity] | None = None,
    conversation_id: str | None = None,
    tiebreaker: Tiebreaker | None = None,
) -> ConversationOutcome:
    """Turn a finished conversation into structured memory.

    This is seam 1. Text in, everything derived out — no audio, no streaming,
    no browser, so the whole spine is testable offline.

    `known_entities` is the family's graph so far, seeded at setup by the
    child-completed intake. Passing it is what turns 「我姐姐」 into a reference
    rather than a fourth duplicate sister.
    """
    extracted = extractor.extract(transcript)
    resolution = resolve_mentions(
        extracted.entity_mentions,
        known_entities or [],
        conversation_id=conversation_id,
        tiebreaker=tiebreaker,
    )
    return ConversationOutcome(
        stories=[assess(c) for c in extracted.stories],
        entities=resolution.entities,
        resolutions=resolution.resolutions,
    )
