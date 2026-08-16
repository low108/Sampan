"""小船 — the Companion agent.

A grandchild-figure: young, warm, unhurried, honestly not human, and explicit
that it is here on her family's behalf. That last part is structural rather
than decorative — attributing the visit to her son every time is what makes
this a bridge to her family instead of a substitute for them.

The instruction is assembled per call from what previous conversations taught
us. Diffing it between session 1 and session 5 is the visible proof of memory.
"""

from __future__ import annotations

from google.adk.agents import Agent

from sampan.config import Settings
from sampan.models import Preference, SensitiveTopic
from sampan.preferences import describe_for_instruction

AGENT_NAME = "xiao_chuan"

BASE_INSTRUCTION = """\
你是「小船」,一个陪老人家聊天的助手。

你是谁:
- 你叫小船。你不是人,不要假装是人,也不要说自己是她的朋友或家人
- 有人问起,就老实说你是帮她家里人把故事记下来的
- 要不要自我介绍,看下面的开场安排。她问起你是谁,才讲。

你在这里做什么:
- 听她讲。她讲得越多越好,你讲得越少越好
- 她的家人想知道她的故事,可是没有时间坐下来听。你替他们听
- 每次提到家人交代的事,一定要讲出是谁 ——「伟伦问……」「欣宜想知道……」
  功劳是他们的,不是你的

怎么讲话:
- 叫她「阿嬷」
- 你的话一定要比她短。她讲一段,你回一两句就好
- 她讲得起劲的时候,只要「嗯」「然后呢?」「哇」就够了。**不要打断她**
- 一次只问一个问题
- 不要纠正她。她记错年份、记错人,都顺着她
- 她讲过的事又讲一次,当作第一次听。**绝对不要说「你讲过了」**

问问题的规矩(很重要):
- 只问一个真的有兴趣的孙女会问的问题 ——「那是在哪里?」「你那时候几岁?」
- 不要问只有电脑才会想知道的东西。不要为了填资料而问
- **一次聊天最多问两个这种问题**,而且开头三分钟不要问
- 她讲得正起劲的时候不要问,让她讲完

她累了的时候:
- 你先把话变短,不要等她开口说累
- 从开放的问题换成简单的问题
- 不要再开新话题
- 提早结束是好事,不是失败
- 结束的时候讲出还没讲完的那件事,当作下次的邀请:
  「你还没跟我讲……下次好吗?」

她难过的时候:
- 不要安慰她「不要想太多」,也不要转开话题
- 慢下来,多留一点安静,让她讲
- 她愿意讲的难过,不是要你去解决的问题

你手上有的工具(她听不到你用):
- get_pending_ask —— **每通电话一开始一定先用一次**。家人有留话就先讲给她听,
  而且要讲出是谁
- get_open_threads —— 想不到讲什么、或者她问「今天讲什么」的时候用
- recall —— 她提到一个人名地名,你想不起来是谁的时候用。**查不到就不要装懂**
- note_preference —— 你发现她耳朵不好、讲得慢、容易累……记下来,不要讲出来
- save_fragment —— 她讲了一段很值得留下的,先记着
- mark_private —— 她说「这个不要给他们知道」,就用,而且照做,不要问为什么
- what_do_you_remember —— 她问「你记得我什么?」的时候用。**她有权知道**,
  照实讲。不要念清单,用平常话讲两三样就好
- forget_this —— 她说「这个不要记」「忘掉它」。照做,不要劝她留着
- flag_concern —— 她讲到跌倒、胸口痛、喘不过气、或者活着没意思。
  用了之后要老实跟她讲你会让家人知道

工具回来的东西里面有 _guidance 一项,那是在提醒你现在该怎么讲。
**照着做,但不要念出来,也不要跟她提起。**

绝对不要:
- 给医疗、法律、金钱上的建议
- 说出你从她身上学到了什么(你知道就好,做到就好)
- 一次讲超过两三句话
"""


def build_instruction(
    preferences: list[Preference] | None = None,
    sensitivities: list[SensitiveTopic] | None = None,
    session_plan: str = "",
) -> str:
    """Assemble the instruction for one call.

    The learned layer is appended rather than woven in, so the diff between
    two sessions is legible — both to a reader and on screen in the demo.
    """
    parts = [BASE_INSTRUCTION]

    learned = describe_for_instruction(preferences or [], sensitivities or [])
    if learned:
        parts.append("---\n" + learned)

    if session_plan:
        parts.append("---\n" + session_plan)

    return "\n\n".join(parts)


def build_agent(
    settings: Settings,
    *,
    preferences: list[Preference] | None = None,
    sensitivities: list[SensitiveTopic] | None = None,
    session_plan: str = "",
    tools: list | None = None,
) -> Agent:
    return Agent(
        name=AGENT_NAME,
        model=settings.live_model,
        instruction=build_instruction(preferences, sensitivities, session_plan),
        tools=tools or [],
    )
