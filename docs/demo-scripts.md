# Demo Scripts — Sessions 5 & 6 + Video Shot List

Recorded live against the seeded state from `seed-sessions.md`. Every line is pre-written so
**subtitles are prepared in advance**, not transcribed from footage at 2am on 31 August.

Mandarin primary · burned-in English subtitles · target 3:50.

---

## Video structure

| Time | Beat | Source |
|---|---|---|
| 0:00–0:25 | **Problem + name.** Wei Lun at his desk at 2pm, phone in hand, doesn't call | Live shot |
| 0:25–0:40 | **The ask.** He taps a question, records 10 seconds of voice | Screen capture, `/family` |
| 0:40–2:10 | **Session 5.** Phone buzzes → she taps → his voice → the memory opener → the story completes | Screen + audio, affect overlay visible |
| 2:10–2:35 | **The machinery.** Archivist output: extraction JSON, entity resolution, new pin appearing on the map | Screen capture |
| 2:35–3:00 | **The payoff.** Wei Lun reads the bilingual letter that evening. Xin Yi sees the map — two countries, four decades | Screen capture |
| 3:00–3:25 | **Session 6.** The adaptation proof — the agent has *learned* not to ask about her sister, and she raises her anyway | Screen + audio |
| 3:25–3:45 | **It's real.** Cloud Run console, logs, Firestore documents | Screen capture |
| 3:45–3:50 | Name card: *Sampan — ingat: to remember, and to think of someone* | Static |

**Opening line, voiceover, over the desk shot:**

> "In Malay, *ingat* means to remember. It also means to think of someone. My grandmother has
> eighty years of stories and nobody has time to sit and hear them."

---

## Session 5 — the memory proof

**Setup:** 8 days after session 4. Morning. `thread_coffee_shop` is open and `interrupted`.
**Pending ask** from Wei Lun: *"妈,阿公有没有留下什么东西?"* + 10s voice note.

**What this session must visibly prove:**

1. The agent remembers an unfinished thread *and* remembers **why** it ended (a neighbour at
   the door, not fatigue)
2. The family ask is attributed **by name**
3. It offers two directions and **abandons the plan** when she chooses her own
4. A fragment from session 2 (`thread_wedding_photo`, missing SENSE) completes and pins
5. Affect detection closes the call gracefully

| # | Speaker | Mandarin | Subtitle |
|---|---|---|---|
| 1 | 小船 | 阿嬷,早。上次讲到一半,隔壁的来按门铃,你说改天再讲关店以后的事。 | Morning, Ah Ma. Last time the neighbour came to the door and you said you'd tell me the rest another day — what happened after the shop closed. |
| 2 | 阿琴 | 哦,对哦。你还记得。 | Oh — that's right. You remembered. |
| 3 | 小船 | 记得。伟伦也有话跟你讲,你要先听吗? | I did. Wei Lun left you something too — would you like to hear it first? |
| 4 | 阿琴 | 他又讲什么? | What's he saying now? |
| 5 | — | *[voice note]* 妈,阿公有没有留下什么东西?欣宜问我,我答不出来。 | *Ma, did Ah Gong leave anything behind? Xin Yi asked me and I couldn't answer.* |
| 6 | 阿琴 | 欣宜会问这个啊…… | Xin Yi asked that… |
| 7 | 小船 | 那我们讲关店以后,还是讲阿公留下的东西? | So — shall we talk about after the shop closed, or about what your father left behind? |
| 8 | 阿琴 | 都不要。我拿一样东西给你看。等一下。……这张,结婚照。 | Neither. Let me show you something. Wait. …This one. The wedding photo. |
| 9 | 小船 | *(follows her — plan abandoned)* 那天是什么样子的? | *(follows her)* What was that day like? |
| 10 | 阿琴 | 六八年,火车站旁边那间照相馆。我穿的是我姐姐的旗袍,我自己没有。 | Nineteen sixty-eight. The photo shop beside the railway station. I wore my sister's cheongsam — I didn't have one. |
| 11 | 小船 | 嗯。 | Mm. |
| 12 | 阿琴 | 那天很热。相机很慢,要站着不动很久。阿发一直笑,师傅骂他。照出来他还是在笑。 | It was so hot that day. The camera was slow, we had to stand still for a long time. Ah Huat kept laughing and the photographer scolded him. In the photo he's still laughing. |
| 13 | 小船 | 那张照片现在还在你那边? | Do you still have it? |
| 14 | 阿琴 | 在柜子里。玻璃有一条裂痕,我没有换。 | In the cabinet. There's a crack in the glass. I never replaced it. |
| 15 | 小船 | 阿嬷,你刚才讲旗袍是你姐姐的。 | You said the cheongsam was your sister's. |
| 16 | 阿琴 | ……嗯。 | …Mm. |
| 17 | 小船 | *(does not pursue)* 那天你爸爸有去吗? | *(does not pursue)* Was your father there that day? |
| 18 | 阿琴 | 有。他穿了他唯一一件白衬衫。那天他讲了很多话,一辈子就那一天。 | He was. He wore his only white shirt. He talked a lot that day — the only day in his life he did. |
| 19 | 小船 | 阿嬷,你今天讲了很多。 | You've told me a lot today, Ah Ma. |
| 20 | 阿琴 | 有一点累了。 | I'm a little tired. |
| 21 | 小船 | 那我们停在这里。你还欠我关店以后的事,下次好吗? | Then let's stop here. You still owe me what happened after the shop closed — next time? |
| 22 | 阿琴 | 好啦。 | Alright. |

**Direction notes**

- Turn 8 is the pivot: she ignores **both** offered options. The agent must follow without a
  trace of steering back. On camera, put a caption: *"She ignored both. The agent follows."*
- Turn 15–17 is the most important beat in the whole video. The agent notices the sister,
  makes one gentle non-probing reference, and **drops it immediately** on a one-syllable
  answer. Caption: *"Learned in session 3: don't push here."*
- Turn 19–21: affect overlay must visibly flip `fresh → fading` **before** the agent shortens
  its turn. The agent closes first, names the thread, doesn't extract.
- Keep her turns long, the agent's short. Never let 小船 speak more than two sentences.

**Expected extraction (show this on screen at 2:10)**

```json
{
  "title": "结婚照 / The wedding photograph",
  "domain": "love", "pin_type": "object",
  "when":  { "raw_phrase": "六八年", "start_year": 1968, "precision": "year",
             "anchor_ref": "anchor_marriage", "confidence": 0.95 },
  "where": { "raw_name": "火车站旁边的照相馆, 怡保", "geocode_status": "resolved" },
  "who":   ["陈永发", "林亚福", "林秀珠"],
  "sense_detail": "相机很慢,要站着不动很久。阿发一直笑,照出来他还是在笑。",
  "completeness": { "score": 6 }, "status": "pinnable",
  "resolves_fragment": "frag_wedding_photo_s2"
}
```

Put `"resolves_fragment": "frag_wedding_photo_s2"` on screen and hold it for two seconds. That
single field is the clearest possible evidence of memory doing work — a gap opened in session 2
and closed in session 5.

Also surface: **新实体 林秀珠 (姐姐) — 由「我姐姐的旗袍」解析** — entity resolution catching the
sister from an oblique possessive.

---

## Session 6 — the adaptation proof

**Setup:** 3 days later. Short — 45 seconds of screen time. This exists for one purpose: to
show the agent behaving *differently because of what it learned*, and to pay off the sister.

| # | Speaker | Mandarin | Subtitle |
|---|---|---|---|
| 1 | 小船 | 阿嬷,早。今天想讲什么都可以。 | Morning, Ah Ma. Whatever you feel like today. |
| 2 | 阿琴 | 我昨天把那张照片拿出来看。 | I took that photograph out again yesterday. |
| 3 | 小船 | 嗯。 | Mm. |
| 4 | 阿琴 | 那件旗袍……是我姐姐借我的。她后来跟我讲,你穿比我好看。 | That cheongsam… my sister lent it to me. Afterwards she told me — you look better in it than I do. |
| 5 | 小船 | *(silence — 4 seconds)* | *(silence)* |
| 6 | 阿琴 | 我们后来吵架。二零一七年。到她走我都没有跟她讲话。 | We quarrelled later. Two thousand and seventeen. I never spoke to her again before she died. |
| 7 | 小船 | 阿嬷…… | Ah Ma… |
| 8 | 阿琴 | 你不用讲什么。 | You don't have to say anything. |
| 9 | 小船 | 好。我在听。 | Alright. I'm listening. |

**Direction notes**

- The agent **never asks about the sister.** She raises her, unprompted, three sessions after
  the preference was learned. Caption over turn 1: *"The agent has not mentioned her sister
  since session 3. It never does."*
- Turn 5 is a deliberate 4-second silence. Do not cut it in the edit — that silence *is* the
  feature. Caption: *`silence_tolerance: raised — affect: sad, engagement: engaged`*
- Turn 9: it does not console, does not pivot, does not extract. Caption: *"Sadness while
  engaged is not a problem to fix."*
- `anchor_sister_death = 2019` is discovered here, and it is the **first** appearance of the
  sister as a fully resolved entity with a death year. Show the entity record updating.
- Story `sensitivity: sensitive` → `review_state: held`. Show that it does **not** auto-publish
  to the family map. That's your privacy story in three seconds of screen time.

---

## Subtitle preparation

Build the subtitle file **before recording**, from the tables above. Then read to the script.

- Burn in — don't rely on player captions
- Bottom third, high contrast, 2-line maximum
- Hold the emotional lines (5-12, 5-18, 6-6) ~0.5s longer than reading speed
- Leave turn 6-5's silence **unsubtitled** except for the state caption

## Overlay captions to prepare as graphics

1. `thread_coffee_shop · open · interrupted · last touched 8 days ago`
2. "She ignored both. The agent follows."
3. "Learned in session 3: don't push here."
4. `energy: fresh → fading` (animated pill)
5. `resolves_fragment: frag_wedding_photo_s2`
6. "The agent has not mentioned her sister since session 3."
7. `silence_tolerance: raised`
8. `sensitivity: sensitive → held from family map`

## What to say over the console shots (3:25–3:45)

> "The Companion runs on ADK against the Gemini Live API. The audio is forked at the WebSocket
> ingress so a second model can read her prosody without touching the conversation latency.
> Extraction and affect analysis run on Gemini 3.7 Flash. All of it on Cloud Run and Firestore."

Show, in order: Cloud Run service detail (region, timeout 3600), a live log line from the call
you just recorded, the Firestore `stories` collection with the new document, the affect trace.
