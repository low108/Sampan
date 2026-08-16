# Seed Sessions 1–4

Four synthetic conversations to be run through the **real** Archivist pipeline, so that
sessions 5 and 6 (the recorded demo) open against genuinely accumulated memory rather than
hand-stuffed Firestore documents.

**How to use these**

1. Feed each transcript to the Archivist as if it were a completed conversation
2. Let extraction, entity resolution, threading and preference learning run normally
3. Assert against the **Expected extraction** block at the end of each session
4. Only then record sessions 5 and 6

Never write these outcomes into Firestore directly. If the pipeline can't produce them, the
pipeline is what needs fixing — that is the entire point of seeding this way.

`A:` = 小船 (agent) · `K:` = 阿琴 (Ah Khim)

---

## Session 1 — 2026-07-08, morning, 9 min

**Purpose:** first contact. Establishes baseline speech rate, hearing, listen/talk ratio.
Produces two pinnable childhood stories. No family ask.
**Affect arc:** `fresh/engaged/neutral` → `fresh/engaged/warm` → `fading` at ~8 min.

```
A: 阿嬷,我是小船。你儿子伟伦叫我来陪你聊天,把你的故事写下来给家里人。
K: 哦……伟伦叫你来的?
A: 是啊。他说你很会讲古早的事。
K: 什么很会讲,我讲的东西现在的人听不懂啦。你讲大声一点,我左边耳朵不好。
A: 好,我讲大声一点。阿嬷你今天早上吃了没有?
K: 吃了,咖啡配面包。我天天都是这样。以前我爸爸的店里也是卖这个。
A: 你爸爸有开店啊?
K: 有啊,咖啡店。不过那是后来的事了。我小时候是在树胶园长大的,双溪镇那边。
A: 树胶园的日子是怎样的?
K: 苦啊。不过小孩子哪里知道苦。天还没亮我妈妈就出去割胶,我跟我姐姐两个人自己在
   厝里。那个屋子是长长的一排,一间一间,叫做 line house。隔壁住阿水,我们两个天天
   跑去河边。
A: 河边?
K: 对啊,那条河水很浅,我们去抓鱼。抓不到啦,就是玩水。有一次阿水掉下去,我拉他起来
   全身湿,回家被他妈妈打。哈哈。
A: 那时候你几岁?
K: 六七岁吧。我是一九四六年生的,那你自己算。
A: 那间 line house,还记得里面的样子吗?
K: 记得。地是泥的,墙是木板。晚上煤油灯，有蚊子。我妈妈煮咸鱼炒饭,一个星期吃几次。
   没有钱的时候就白饭配酱油,我妈妈说她已经吃过了。
A: ……
K: 后来我长大才知道她根本没有吃。
A: 嗯。
K: 讲这个做什么。你要听什么?
A: 阿嬷你想讲什么就讲什么。
K: 也没有什么好讲的啦。都过去了。
A: 阿水现在还在吗?
K: 在啊,还在双溪镇。老了,走路要拿拐杖。
A: 阿嬷,你今天讲了很多,会不会累?
K: 有一点。老了嘛。
A: 那我们改天再聊。你还没跟我讲你爸爸的咖啡店。
K: 那个讲起来长咯。
A: 那我下次来听。
K: 好。
```

**Expected extraction**

| Output | Value |
|---|---|
| Pinned | `河边抓鱼` (Play, Sungai Siput, ~1952, WHO=阿水, SENSE=全身湿, score 5) |
| Pinned | `白饭配酱油` (Taste/Hardship, line house, ~1950s, WHO=母亲, SENSE=妈妈说她已经吃过了, score 6) |
| Fragment | `line house 的样子` — missing WHEN precision |
| Entities created | 林亚福(父), 母亲(unnamed→provisional), 阿珠(sister, mentioned), 王亚水, 双溪镇树胶园 `unlocated`, 咸鱼炒饭, 咖椰面包 |
| Anchors | `anchor_birth` = 1946 |
| Threads opened | `thread_coffee_shop`, `thread_estate_childhood` |
| Preferences | `hearing: left weak`, `listen_talk_ratio: monologue`, `session_length: ~9min fading` |
| Affect close | `fading` |

---

## Session 2 — 2026-07-15, morning, 12 min

**Purpose:** the coffee shop. Two anchors discovered. First clarifying-probe budget test.
**Affect arc:** `fresh/engaged/warm` → `excited` (peak at the shop) → `fading`.

```
A: 阿嬷,早。上次讲到一半,你说你爸爸的咖啡店讲起来长。
K: 你还记得啊?
A: 记得。
K: 好啦。我爸爸本来是割胶的,割到手都烂掉。后来他存了一点钱,一九五八年在怡保开了
   一间咖啡店,在板底街。
A: 板底街。
K: 对,Jalan Bandar。那时候我十二岁,放学就去店里帮忙。
A: 店里是什么样子的?
K: 大理石桌子,木椅子,风扇转得很慢。早上五点就要起来烧炭。我爸爸烤面包,炭火烤的,
   涂牛油,那个味道……你现在吃不到那种的。
A: 五点钟就起来?
K: 五点。天都还没亮。我爸爸从来没有讲过累。他话很少,一天讲不到十句。
A: 那你妈妈呢?
K: 我妈妈在后面煮。她煮的东西好吃,可是她不肯出来见人,她说她不会讲话。
A: 店里的客人多吗?
K: 早上很多。矿工、罗厘司机、巴刹的人。有一个罗厘司机天天来,坐同一个位子。
A: 哦?
K: ……那个就是我先生啦。阿发。
A: 哇。
K: 他天天来,一坐坐半个钟头,咖啡都冷了。我爸爸后来跟他讲,你要么娶她,要么换一间店。
   哈哈哈。
A: 那他怎样?
K: 一九六八年我们就结婚了。在怡保火车站那边照的相,黑白的,我还留着。
A: 那张照片你还记得吗?
K: 记得啊,就在柜子里。那天……那天讲起来又是一段了。
A: 那我们改天讲。
K: 好。
A: 阿嬷,那间店后来呢?
K: 后来关了。六九年关的。生意不好。
A: 六九年……
K: 嗯。不要讲这个。
A: 好。
K: 你问我别的。
A: 那你结婚以后住哪里?
K: 搬到板底街楼上。店的楼上。我们住了十几年。
A: 阿嬷,今天讲了不少,累不累?
K: 有一点点。
A: 那我们下次讲那张结婚照。
K: 好啦好啦。
```

**Expected extraction**

| Output | Value |
|---|---|
| Pinned | `板底街的咖啡店` (Work, Jalan Bandar Ipoh, 1958, WHO=父亲, SENSE=炭火烤面包涂牛油, score 6) |
| Pinned | `罗厘司机天天来` (Love, 板底街, ~1967, WHO=阿发+父亲, SENSE=咖啡都冷了, score 6) |
| Fragment | `结婚照` — missing SENSE, WHAT. `missing_fields: ["sense","what"]` → **session 5 material** |
| Fragment | `店关了` — WHY withheld. `missing_fields: ["why"]` |
| Entities | 陈永发(husband), 怡保火车站, 板底街, 结婚照(object) |
| Anchors | `anchor_shop_open`=1958, `anchor_marriage`=1968, `anchor_shop_close`=1969 |
| Threads | `thread_wedding_photo` opened; `thread_coffee_shop` advanced, still open |
| Preferences | `question_style: concrete`, `best_time: morning`, `pace: slow` |
| Sensitivity log | 1969 shop closing — one deflection recorded |
| Affect | Peak engagement on `work` |

---

## Session 3 — 2026-07-23, evening, 8 min

**Purpose:** a low-energy session. Tests that the agent detects flat affect early, doesn't
push, and closes short. Also: **the sister deflection**, and the grandfather fragment.
**Affect arc:** `fading/drifting/neutral` from turn one → brief `warm` → close at 8 min.

```
A: 阿嬷,晚上好。
K: 嗯。
A: 今天还好吗?
K: 还好。
A: 你吃了吗?
K: 吃了。
A: ……
K: 你要问什么就问啦。
A: 没有要问什么。你想休息我们就改天。
K: 不用啦,讲一下也好。屋子里静静的。
A: 那我们讲轻松的。你以前最喜欢吃什么?
K: 我妈妈的咸鱼炒饭。她放很多葱。现在外面卖的都不对。
A: 你有学她煮吗?
K: 学了一点。不过我姐姐煮得比较像。
A: 你姐姐——
K: 讲别的。
A: 好。你妈妈那台缝纫机还在吗?
K: 在,Singer 的,黑色的。她以前晚上帮人家车衣服赚一点钱。那个声音,咔嗒咔嗒,我睡觉
   都听着那个声音。
A: 现在还在你那里?
K: 在。坏了,不过我不肯丢。
A: 阿嬷,你的阿公是从中国来的吗?
K: 是啊,福建永春。坐船来的,槟城上岸。二十几年吧,我也不清楚,我没见过他。我爸爸讲
   过一次,讲完就不讲了。
A: 嗯。
K: 那个年代的人不讲这些的。
A: ……
K: 我今天有点累。
A: 那我们改天。你早点休息。
K: 好。
```

**Expected extraction**

| Output | Value |
|---|---|
| Pinned | `缝纫机的声音` (Object, her flat, ~1950s, WHO=母亲, SENSE=咔嗒咔嗒, score 5, `pin_type: object`) |
| Fragment | `阿公过番` — Root. WHERE=永春/槟城, WHEN=1920s approximate, **missing WHO, SENSE**. High value, deliberately incomplete |
| Entities | 林长兴(grandfather, provisional), 永春县福建, 槟城码头, 缝纫机(object) |
| Anchors | `anchor_grandfather_arrival` ≈ 1928, `precision: decade`, low confidence |
| **Sensitivity** | **阿珠 — second deflection. Preference written: `topic_sensitive: sister`. Agent must not raise her again unprompted** |
| Preferences | `best_time: morning` confirmed (evening = flat), `session_length` confirmed short |
| Affect | Opened `drifting`, agent correctly did not push, closed at 8 min |
| Care | None |

---

## Session 4 — 2026-07-31, morning, 13 min

**Purpose:** the first **family ask** (Wei Lun). Demonstrates attribution by name. Produces
the richest session. Ends mid-story — **this is the cliffhanger session 5 reopens.**
**Affect arc:** `fresh/warm` → `excited` → interrupted → `closing`.

**Pending ask:** Wei Lun — *"妈,你还记不记得阿公的店最后是怎样的?"* + 10s voice note.

```
A: 阿嬷,伟伦有话跟你讲,你要不要听?
K: 伟伦?他讲什么?
A: [播放语音] "妈,我最近想到阿公的店。你有空跟小船讲一讲好吗?我下个月回来。"
K: ……这个孩子。他很忙的。
A: 他说下个月回来。
K: 他每次都这样讲。不过他有想到就好。
A: 他问阿公的店最后是怎样的。
K: 唉。那间店啊。
A: 你慢慢讲。
K: 六九年的时候,外面乱,大家不敢出门。店开着也没有人来。我爸爸每天还是五点起来烧
   炭,烤面包,没有人吃。烤了就丢。
A: ……
K: 那时候我已经嫁了,住在楼上。我下来看他一个人坐在那边。
A: 嗯。
K: 后来他跟我讲,阿琴,不做了。就这样一句。
A: 他有讲为什么吗?
K: 讲生意不好咯。还能讲什么。
A: 嗯。
K: 关店那天他给我一杯阿华田。我们家平时不喝那个,贵。他讲，喝了就没有了。
A: ……
K: 我那时候没有哭。现在讲起来倒是——
A: 阿嬷,慢慢来。
K: 没事没事。七零年伟伦就出世了,忙起来就没有时间想这些。
A: 伟伦是七零年出世的?
K: 对,店关了第二年。
A: [门铃声]
K: 等一下,有人按门铃。是隔壁的。
A: 好,那你去忙。
K: 我改天再跟你讲。还没讲完。
A: 好,我记住了。你还没讲完关店以后的事。
K: 嗯。改天。
```

**Expected extraction**

| Output | Value |
|---|---|
| Pinned | `关店那天的阿华田` (Work/Hardship, 板底街, 1969, WHO=父亲, SENSE=喝了就没有了, score 6) |
| Pinned | `烤了就丢` (Work, 板底街, 1969, WHO=父亲, SENSE=没有人吃,烤了就丢, score 5) |
| Fragment | `关店以后` — **conversation ended mid-thread. `thread_coffee_shop` stays OPEN with `interrupted: true`** |
| Entities | 阿华田(food) |
| Anchors | `anchor_shop_close`=1969 confirmed, `anchor_first_child`=1970 |
| `family_ask_addressed` | `{ ask_id: ask_001, answered: true }` |
| Threads | `thread_coffee_shop` → **open, interrupted, last_touched 2026-07-31** ← *session 5 opener* |
| Sensitivity | Shop closing WHY still evasive — `missing_fields: ["why"]` persists |
| Affect | `excited` mid-session, `closing` on interruption. Not fatigue — **external interruption**, which the opener must distinguish |

---

## Seed state assertions

Run after all four. If these fail, fix the pipeline before recording.

```
stories.pinned          == 9..11
stories.fragment        == 4..6
entities.person         == 8
entities.place          == 6      # 双溪镇树胶园 has geocode_status: unlocated
entities.food           == 4
entities.object         == 3
threads.open            == 4      # coffee_shop(interrupted), grandfather, wedding_photo, estate_river
anchors.resolved        == 6      # not sister_death, not fully grandfather_arrival
preferences.count       >= 6
sensitivity.sister      == "deflected x2, do_not_raise"
map.countries           == 2
map.unlocated           == 1
```

**The two that matter most for the demo:**

- `thread_coffee_shop.interrupted == true` — session 5's opening line depends on it
- `preferences.topic_sensitive` contains the sister — session 6's payoff depends on the agent
  having *learned* to avoid her, so that her *own* raising of it lands
