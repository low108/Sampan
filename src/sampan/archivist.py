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

from sampan.anchors import apply_anchors, fold_anchors
from sampan.config import Settings
from sampan.entities import Resolution, Tiebreaker, resolve_mentions
from sampan.models import (
    Anchor,
    AnchorCandidate,
    Closure,
    ClosureReason,
    Entity,
    EntityMention,
    Preference,
    PreferenceObservation,
    ScoredStory,
    SensitiveTopic,
    StoryCandidate,
    Thread,
    ThreadUpdate,
    TopicSignal,
    assess,
)
from sampan.preferences import fold_preferences, fold_sensitivities
from sampan.threads import fold_threads, open_threads

EXTRACTION_PROMPT = """\
你是一位口述历史记录员。下面是一位老人家和陪伴她聊天的助手之间的对话记录。

请从对话中找出她讲的「故事」,并整理成结构化资料。

什么算一个故事:
- 有开头有结尾的一件事,不是笼统的感想
- 「我小时候很穷」不是故事;「我们吃白饭配酱油,妈妈说她已经吃过了」是故事

**讲了一半的也要列出来。** 她提起了一件事,可是没讲完、没讲清楚是什么时候、
在哪里、或者被打断了 —— 这些一样要列进去,把不知道的栏位留空就好。
这些「碎片」很重要:下次聊天的时候,就是靠这些空栏位知道要问她什么。

所以一次对话通常有 2 到 6 个 story:讲完整的,加上讲了一半的。
只有一点要守住:**不要编造**。她没讲的就留空,不要用猜的填满。

每个故事请尽量填齐这几样,但**绝对不要编造**。她没讲的就留空:
- where: 地点,用她自己讲的名字
- when: 时间。她常常讲相对时间(「结婚以前」、「大水那年」)。
  raw_phrase 一定要用她原本的话。能推算年份就填,不能就留空,
  precision 用 relative 或 era
- who: 出现的人,用她称呼的方式(「我姐姐」、「阿水」)
- what: 发生了什么事
- sense_detail: **最重要的一项,也最容易做错**。
  必须是**她自己讲出来的**一个具体感官细节 —— 一种味道、一个声音、
  一样看得到摸得到的东西。要能从对话里指出是哪一句。
  只要一个,不要列一串。

  ✅ 「缝纫机咔嗒咔嗒的声音」—— 她讲过这个声音
  ✅ 「白饭配酱油」—— 她讲过吃什么
  ❌ 「南渡的画面」「艰苦的岁月」—— 这是你替她总结的,不是她讲的
  ❌ 把这个故事的事实换句话说,再加上「的画面」「的情景」

  简单的检查:如果这一句是你归纳出来的,而不是她说的,就**留空**。
  留空完全没关系 —— 下次聊天就会问她。硬凑一个反而毁了这个栏位。
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

threads —— 这次对话里「讲了但还没讲完」的话题:
- topic: 短短一个标题,例如「爸爸的咖啡店」
- action: opened(第一次提起)/ advanced(接着上次讲)/ closed(讲完了)
- left_off_at: 她还没讲到的部分。下次就是从这里接下去,所以要具体

closure —— 这次对话是怎么结束的。**这一项很重要**:
- reason:
  - interrupted: 外面的事打断了(有人按门铃、电话响、有人来找她)
  - fatigue: 她累了、想休息、话变短了
  - natural: 讲完了,自然结束
  - refused: 她不想讲
  - unknown: 看不出来
- evidence: 对话里显示出来的那一句
- active_topic: 结束的时候她正在讲哪个话题

interrupted 和 fatigue 一定要分清楚。被打断表示她话讲到一半、还想讲;
累了表示今天到此为止。下次开场要怎么讲,就看这一项。

anchors —— 可以定年份的人生大事。老人家很少讲年份,可是一旦知道
「结婚 = 1968」,以后她讲「结婚以前」就有时间了。
- anchor_id 用这些固定的名称:anchor_birth(出生)、anchor_marriage(结婚)、
  anchor_shop_open(开店)、anchor_shop_close(关店)、anchor_first_child(第一个孩子出世)、
  anchor_arrival(祖辈南来)、anchor_husband_death(先生过世)、
  anchor_sister_death(姐姐过世)。没有对应的就不要硬套
- 只有她讲了明确年份(或算得出来)才列。猜的不要列
- confidence: 她直接讲年份就高;要推算的就低

story 的 when 栏位:如果她讲的是相对时间(「结婚以前」),
请填 anchor_ref 指向对应的 anchor_id,年份不知道就留空 —— 我们会自己算。

preferences —— 从这次对话看得出她「喜欢怎样被对待」。只列看得出来的:
- session_length: 大概讲多久就累(例:讲到十分钟左右开始短句)
- best_time: 早上还是晚上比较有精神
- listen_talk_ratio: 她喜欢自己一直讲,还是要人问
- question_style: 具体的问题比较有用,还是开放的问题
- hearing: 听力(例:左耳不好)
- pace: 讲快讲慢
- silence_tolerance: 她需要多久的停顿
- topic_favourite: 她讲起来最起劲的题目
value 要短、要具体。evidence 填对话里的那一句。

topic_signals —— 她对每个话题的反应。**这一项是她无声的反馈**:
- kind:
  - refused: 明讲不要(「讲别的」「不要讲这个」)
  - deflected: 没有明讲,可是转开话题、只回一两个字、答非所问
  - engaged: 她自己主动讲、讲得很多
- topic: 短标签(例:姐姐、关店的原因)
- evidence: 那一句

同一个话题她后来自己愿意讲了,就照实记 engaged。

{known_labels}
对话记录:
---
{transcript}
---
"""

KNOWN_LABELS_BLOCK = """\
以前几次聊天已经用过的标签。讲的是同一件事,就**用回原本的标签**,
不要另外取新的名字 —— 换了名字,系统就会当成两件事。
{labels}

"""


def _known_labels_block(topics: list[str]) -> str:
    """Give the model the vocabulary it has already used.

    Without this it invents a fresh label every call — 咖啡店关店原因 one
    session, 阿公的店关门 the next — and no amount of string matching
    afterwards can tell that they are the same subject.
    """
    unique = sorted({t.strip() for t in topics if t.strip()})
    if not unique:
        return ""
    return KNOWN_LABELS_BLOCK.format(labels="\n".join(f"- {t}" for t in unique))


class ExtractionResponse(BaseModel):
    stories: list[StoryCandidate]
    entity_mentions: list[EntityMention] = []
    threads: list[ThreadUpdate] = []
    closure: Closure = Closure(reason=ClosureReason.UNKNOWN)
    anchors: list[AnchorCandidate] = []
    preferences: list[PreferenceObservation] = []
    topic_signals: list[TopicSignal] = []


class ConversationOutcome(BaseModel):
    """Everything derived from one conversation.

    Grows as tickets land: threads, anchors and preferences join `stories` and
    `entities` here, and this stays the single return value of the seam.
    """

    stories: list[ScoredStory]
    entities: list[Entity] = []
    resolutions: list[Resolution] = []
    threads: list[Thread] = []
    closure: Closure = Closure(reason=ClosureReason.UNKNOWN)
    anchors: list[Anchor] = []
    preferences: list[Preference] = []
    sensitivities: list[SensitiveTopic] = []

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

    @property
    def open_threads(self) -> list[Thread]:
        return open_threads(self.threads)

    @property
    def do_not_raise(self) -> list[SensitiveTopic]:
        """Subjects the agent must not open on its own next time."""
        return [t for t in self.sensitivities if t.do_not_raise]

    @property
    def interrupted_thread(self) -> Thread | None:
        """What she was cut off mid-way through. The next call's opener."""
        return next((t for t in self.threads if t.interrupted), None)


class StoryExtractor(Protocol):
    """Seam for the model call, so the pipeline can be exercised offline."""

    def extract(
        self, transcript: str, known_labels: list[str] | None = None
    ) -> ExtractionResponse: ...


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

    def extract(
        self, transcript: str, known_labels: list[str] | None = None
    ) -> ExtractionResponse:
        from google.genai import types

        response = self._client.models.generate_content(
            model=self._settings.archivist_model,
            contents=EXTRACTION_PROMPT.format(
                transcript=transcript,
                known_labels=_known_labels_block(known_labels or []),
            ),
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
    known_threads: list[Thread] | None = None,
    known_anchors: list[Anchor] | None = None,
    known_preferences: list[Preference] | None = None,
    known_sensitivities: list[SensitiveTopic] | None = None,
    conversation_id: str = "conv_unknown",
    tiebreaker: Tiebreaker | None = None,
) -> ConversationOutcome:
    """Turn a finished conversation into structured memory.

    This is seam 1. Text in, everything derived out — no audio, no streaming,
    no browser, so the whole spine is testable offline.

    `known_entities` is the family's graph so far, seeded at setup by the
    child-completed intake. Passing it is what turns 「我姐姐」 into a reference
    rather than a fourth duplicate sister.
    """
    known_labels = [t.topic for t in (known_threads or [])] + [
        t.topic for t in (known_sensitivities or [])
    ]
    extracted = extractor.extract(transcript, known_labels)
    resolution = resolve_mentions(
        extracted.entity_mentions,
        known_entities or [],
        conversation_id=conversation_id,
        tiebreaker=tiebreaker,
    )
    anchors = fold_anchors(
        known_anchors or [], extracted.anchors, conversation_id=conversation_id
    )
    for candidate in extracted.stories:
        candidate.when = apply_anchors(candidate.when, anchors)

    return ConversationOutcome(
        stories=[assess(c) for c in extracted.stories],
        entities=resolution.entities,
        resolutions=resolution.resolutions,
        threads=fold_threads(
            known_threads or [],
            extracted.threads,
            extracted.closure,
            conversation_id=conversation_id,
        ),
        closure=extracted.closure,
        anchors=anchors,
        preferences=fold_preferences(
            known_preferences or [],
            extracted.preferences,
            conversation_id=conversation_id,
        ),
        sensitivities=fold_sensitivities(
            known_sensitivities or [],
            extracted.topic_signals,
            conversation_id=conversation_id,
        ),
    )
