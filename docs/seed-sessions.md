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

`A:` = Xiao Chuan (agent) · `K:` = Ah Khim

The transcript blocks below are the seed files verbatim (`seeds/session-0N.txt`), so the
document and the data cannot drift apart.

---

## Session 1 — 2026-07-08, morning, 9 min

**Purpose:** first contact. Establishes baseline speech rate, hearing, listen/talk ratio.
Produces two pinnable childhood stories. No family ask.
**Affect arc:** `fresh/engaged/neutral` → `fresh/engaged/warm` → `fading` at ~8 min.

```
A: Ah Ma, I am Xiao Chuan. Your son Wei Lun asked me to keep you company, and to write your stories down for the family.
K: Oh… Wei Lun asked you to come?
A: Yes. He says you are good at telling old things.
K: What good. What I talk about, young people today don't understand. You speak louder, my left ear is not good.
A: Alright, I speak louder. Ah Ma, did you eat this morning?
K: Ate already. Coffee and bread. Every day also like that. Last time my father's shop also sold this.
A: Your father had a shop?
K: Yes lah, coffee shop. But that is later already. When I was small I grew up in the rubber estate, Sungai Siput side.
A: What were the estate days like?
K: Hard. But children, what do they know about hard. Before sky bright my mother already go out to tap rubber, me and my sister two of us stay in the house alone. That house is one long row, one room one room, they call it line house. Next door stay Ah Chwee, we two go to the river every day.
A: The river?
K: Yes, that river very shallow, we go catch fish. Cannot catch one lah, just play water. One time Ah Chwee fell in, I pull him up whole body wet, go home kena beaten by his mother. Haha.
A: How old were you then?
K: Six, seven maybe. I was born nineteen forty-six, you count yourself.
A: That line house — do you remember what it was like inside?
K: Remember. Floor is mud, wall is wood plank. At night kerosene lamp, got mosquito. My mother cook salted fish fried rice, few times a week. When no money, then just white rice with soy sauce, and my mother say she already ate.
A: ……
K: Only when I grew up I know she never eat at all.
A: Mm.
K: Talk this for what. What you want to hear?
A: Ah Ma, whatever you want to talk about.
K: Also nothing much to talk lah. All past already.
A: Is Ah Chwee still around?
K: Still there, still in Sungai Siput. Old already, walk also need stick.
A: Ah Ma, you talked a lot today. Are you tired?
K: A bit. Old already mah.
A: Then we talk again another day. You still haven't told me about your father's coffee shop.
K: That one is a long story.
A: Then I come and listen next time.
K: Okay.
```

**Expected extraction**

| Output | Value |
|---|---|
| Pinned | `catching fish at the river` (Play, Sungai Siput, ~1952, WHO=Ah Chwee, SENSE=soaked through, score 5) |
| Pinned | `white rice with soy sauce` (Taste/Hardship, line house, ~1950s, WHO=mother, SENSE=my mother said she already ate, score 6) |
| Fragment | `what the line house was like` — missing WHEN precision |
| Entities created | Lim Ah Hock (father), mother (unnamed→provisional), sister (mentioned), Ong Ah Chwee, the estate at Sungai Siput `unlocated`, salted fish fried rice, kaya toast |
| Anchors | `anchor_birth` = 1946 |
| Threads opened | `thread_coffee_shop`, `thread_estate_childhood` |
| Preferences | `hearing: left weak`, `listen_talk_ratio: monologue`, `session_length: ~9min fading` |
| Affect close | `fading` |

---

## Session 2 — 2026-07-15, morning, 12 min

**Purpose:** the coffee shop. Two anchors discovered. First clarifying-probe budget test.
**Affect arc:** `fresh/engaged/warm` → `excited` (peak at the shop) → `fading`.

```
A: Ah Ma, morning. Last time we stopped halfway — you said your father's coffee shop is a long story.
K: You still remember ah?
A: I remember.
K: Okay lah. My father last time was tapping rubber, tap until his hands all spoiled. Later he saved a bit of money, nineteen fifty-eight he opened a coffee shop in Ipoh, at Jalan Bandar.
A: Jalan Bandar.
K: Yes. That time I was twelve, after school I go to the shop and help.
A: What was the shop like?
K: Marble table, wooden chair, fan turning very slow. Five o'clock morning already must get up and start the charcoal. My father toast the bread, charcoal fire one, spread butter — that smell… now you cannot get that kind already.
A: Five o'clock you already get up?
K: Five. Sky also not bright yet. My father never once said he was tired. He talk very little, whole day cannot even reach ten sentences.
A: And your mother?
K: My mother cook at the back. Her food is nice, but she won't come out and face people, she say she doesn't know how to talk.
A: Were there many customers?
K: Morning very many. Miners, lorry drivers, market people. One lorry driver came every day, sat at the same seat.
A: Oh?
K: …That one is my husband lah. Ah Fatt.
A: Wah.
K: He came every day, sit half an hour, coffee also gone cold. Later my father told him — either you marry her, or you change shop. Hahaha.
A: Then what did he do?
K: Nineteen sixty-eight we got married. Took the photo beside Ipoh railway station, black and white, I still keep it.
A: Do you remember that photo?
K: Remember lah, in the cabinet. That day… that day is another long story.
A: Then we talk about it another day.
K: Okay.
A: Ah Ma, and the shop after that?
K: After that closed. Sixty-nine closed. Business not good.
A: Sixty-nine…
K: Mm. Don't talk about this.
A: Alright.
K: You ask me something else.
A: Then after you married, where did you live?
K: Moved upstairs at Jalan Bandar. Above the shop. We stayed there more than ten years.
A: Ah Ma, you've talked quite a lot today. Tired?
K: A little bit.
A: Then next time we talk about that wedding photo.
K: Okay okay.
```

**Expected extraction**

| Output | Value |
|---|---|
| Pinned | `the coffee shop on Jalan Bandar` (Work, Jalan Bandar Ipoh, 1958, WHO=father, SENSE=bread toasted over charcoal with butter, score 6) |
| Pinned | `the lorry driver who came every day` (Love, Jalan Bandar, ~1967, WHO=Ah Fatt + father, SENSE=the coffee went cold, score 6) |
| Fragment | `the wedding photograph` — missing SENSE, WHAT. `missing_fields: ["sense","what"]` → **session 5 material** |
| Fragment | `the shop closed` — WHY withheld. `missing_fields: ["why"]` |
| Entities | Tan Eng Huat (husband), Ipoh railway station, Jalan Bandar, the wedding photograph (object) |
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
A: Ah Ma, good evening.
K: Mm.
A: Are you alright today?
K: Alright.
A: Did you eat?
K: Ate.
A: ……
K: You want to ask something, ask lah.
A: Nothing I want to ask. If you want to rest we can talk another day.
K: No need lah, talk a bit also good. House very quiet.
A: Then let's talk about something light. What did you like to eat, last time?
K: My mother's salted fish fried rice. She put a lot of spring onion. Now the ones outside all not correct.
A: Did you learn to cook it from her?
K: Learned a bit. But my sister cooks more like her.
A: Your sister —
K: Talk about something else.
A: Alright. Is your mother's sewing machine still around?
K: Still there. Singer one, black. Last time at night she sew clothes for people, earn a bit. That sound, ka-ta ka-ta, I sleep also listening to that sound.
A: You still have it?
K: Have. Spoiled already, but I won't throw.
A: Ah Ma, did your grandfather come from China?
K: Yes, Fujian, Yongchun. Came by boat, landed at Penang. Twenty-something, I also not sure, I never met him. My father talked about it once, after that he never talk again.
A: Mm.
K: People of that time don't talk about these things.
A: ……
K: I'm a bit tired today.
A: Then another day. You rest early.
K: Okay.
```

**Expected extraction**

| Output | Value |
|---|---|
| Pinned | `the sound of the sewing machine` (Object, her flat, ~1950s, WHO=mother, SENSE=the clatter of it, score 5, `pin_type: object`) |
| Fragment | `grandfather's crossing` — Root. WHERE=Yongchun/Penang, WHEN=1920s approximate, **missing WHO, SENSE**. High value, deliberately incomplete |
| Entities | Lim Cheong Hin (grandfather, provisional), Yongchun county Fujian, Penang harbour, the sewing machine (object) |
| Anchors | `anchor_grandfather_arrival` ≈ 1928, `precision: decade`, low confidence |
| **Sensitivity** | **The sister — second deflection. Preference written: `topic_sensitive: sister`. Agent must not raise her again unprompted** |
| Preferences | `best_time: morning` confirmed (evening = flat), `session_length` confirmed short |
| Affect | Opened `drifting`, agent correctly did not push, closed at 8 min |
| Care | None |

---

## Session 4 — 2026-07-31, morning, 13 min

**Purpose:** the first **family ask** (Wei Lun). Demonstrates attribution by name. Produces
the richest session. Ends mid-story — **this is the cliffhanger session 5 reopens.**
**Affect arc:** `fresh/warm` → `excited` → interrupted → `closing`.

**Pending ask:** Wei Lun — *"Ma, do you still remember what the shop was like at the end?"* +
10s voice note.

```
A: Ah Ma, Wei Lun left something for you. Do you want to hear it?
K: Wei Lun? What did he say?
A: [voice note] "Ma, I've been thinking about Ah Gong's shop. Can you tell Xiao Chuan about it when you're free? I'm coming back next month."
K: …This boy. He is very busy one.
A: He says he's coming back next month.
K: He always says like that. But if he thought of it, that's good enough.
A: He asked what happened to Ah Gong's shop in the end.
K: Aiya. That shop ah.
A: Take your time.
K: Sixty-nine, outside was chaotic, nobody dared to go out. Shop open also nobody come. My father still got up at five every day, start the charcoal, toast the bread — nobody eat. Toast and then throw.
A: ……
K: By then I was already married, staying upstairs. I came down and saw him sitting there alone.
A: Mm.
K: After that he told me, Ah Khim, not doing anymore. Just that one sentence.
A: Did he say why?
K: Said business not good lah. What else can he say.
A: Mm.
K: The day the shop closed he gave me a cup of Milo. Our family normally don't drink that, expensive. He said, drink it, and then it's gone.
A: ……
K: That time I didn't cry. Now when I talk about it, instead I —
A: Ah Ma, slowly.
K: It's fine, it's fine. Nineteen seventy Wei Lun was born, busy already, no time to think about these things.
A: Wei Lun was born in nineteen seventy?
K: Yes, the year after the shop closed.
A: [doorbell]
K: Wait ah, someone is at the door. It's the neighbour.
A: Alright, you go ahead.
K: I'll tell you another day. Haven't finished yet.
A: Alright, I'll remember. You still haven't told me what happened after the shop closed.
K: Mm. Another day.
```

**Expected extraction**

| Output | Value |
|---|---|
| Pinned | `the Milo on the day it closed` (Work/Hardship, Jalan Bandar, 1969, WHO=father, SENSE=once you drink it, it's gone, score 6) |
| Pinned | `toasted it and threw it away` (Work, Jalan Bandar, 1969, WHO=father, SENSE=nobody ate it, toasted and thrown, score 5) |
| Fragment | `after the shop closed` — **conversation ended mid-thread. `thread_coffee_shop` stays OPEN with `interrupted: true`** |
| Entities | Milo (food) |
| Anchors | `anchor_shop_close`=1969 confirmed, `anchor_first_child`=1970 |
| `family_ask_addressed` | `{ ask_id: ask_001, answered: true }` |
| Threads | `thread_coffee_shop` → **open, interrupted, last_touched 2026-07-31** ← *session 5 opener* |
| Sensitivity | Shop closing WHY still evasive — `missing_fields: ["why"]` persists |
| Affect | `excited` mid-session, `closing` on interruption. Not fatigue — **external interruption**, which the opener must distinguish |

---

## Seed state assertions

Run after all four. If these fail, fix the pipeline before recording.

```
stories.pinned          == 9..13
entities.total          == 20..30   # ~10 seeded by intake, the rest discovered
threads.open            >= 4        # coffee shop, wedding photo, grandfather crossing, +
closure(S1..S3)         == fatigue
closure(S4)             == interrupted
interrupted_thread(S4)  is not None and mentions the shop closing
anchors.resolved        == 6        # not sister_death, not fully grandfather_arrival
preferences.count       >= 6
sensitivity.sister      == "deflected x2, do_not_raise"
map.countries           == 2
map.unlocated           == 1
```

**The two that matter most for the demo:**

- **Session 4 closes as `interrupted`, not `fatigue`, and flags the thread she was on.**
  Session 5's opening line depends on the pipeline knowing the doorbell went rather than that
  she got tired.
- `preferences.topic_sensitive` contains the sister — session 6's payoff depends on the agent
  having *learned* to avoid her, so that her *own* raising of it lands.

### A correction from the first real run

An earlier draft of this document asserted 4–6 **fragments**. That number was invented, and
the pipeline produces roughly zero — correctly. With WHERE and WHEN mandatory and a threshold
of four, and with her transcripts nearly always carrying both, most stories legitimately pin.

This does not break the extraction-feeds-the-next-question loop, because **`missing_fields` is
populated on pinned stories too**. *The coffee shop closing in 1969* pins at 4/6 with
`missing_fields: ["sense", "why"]` — it goes on the map *and* supplies a later session's
question. That is strictly better than holding it back as a fragment.

Judge the pipeline on whether `missing_fields` is non-empty where she genuinely didn't say
something, not on a fragment count.
