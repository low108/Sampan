# Sampan — shooting script

The three-call arc: **teach it something new → watch it remember → correct it →
ask it back.** That is the only way to prove longitudinal memory on camera, and
it is the thing no published system in our literature review evaluates.

Legend: **DO** = what you click · **SAY** = narration, out loud ·
**AS HER** = spoken into the call · **SCREEN** = what must be visible.

---

# READ THIS FIRST — the timing problem

Three live calls cannot be recorded inside four minutes. Each is 30–45 seconds
of real conversation, and **the archive needs time between them** — call 2
cannot remember what call 1 said until extraction has finished.

**So: record the three calls first, as one session, over about fifteen minutes.
Then cut each to ~20 seconds and edit them in.** The script below is written
that way, with verification gates between the calls so you never record a beat
that cannot work yet.

Final cut ≈ **4:05**. Call footage is 60s of that.

---

# PRE-FLIGHT

## 1 · Deploy (blocking)

Cloud Run serves the 18 Aug build — no memory panel, no `/search`. Beats 6 and 7
do not exist on it.

```bash
./deploy.sh                       # with SAMPAN_MIN_INSTANCES=1 for the recording
URL=https://sampan-ig6xl5kf4q-as.a.run.app
curl -s "$URL/health"                                  # configured: true
curl -s "$URL/" | grep -o 'index-[A-Za-z0-9_-]*\.js'   # matches static/index.html
```

## 2 · Choose the new fact — and keep it off the bible

The point of beat 3 is that the system learns something it was never seeded
with. Use exactly this, and do not vary it between takes:

> **"Last Sunday my neighbour Mrs Rajan took me to Pasar Besar. She bought
> curry puffs, and the oil came through the paper bag, still warm. She lives in
> the flat downstairs from me."**

Every clause is load-bearing, and the sentence was built backwards from what has
to happen to it:

| Clause | Why it is there |
|---|---|
| *Last Sunday … took me to Pasar Besar* | The archivist only counts **one thing that happened, with a beginning and an end**. A habit ("she brings me curry puffs") is not a story and gets no pin. |
| *Pasar Besar* | A pin needs a place that **resolves to coordinates**. Pasar Besar is Ipoh's central market — real, findable, and in the persona bible's place table. |
| *the oil came through the paper bag, still warm* | `sense_detail` is the extractor's most important field and it will not invent one. No sensory detail, weaker story. |
| *Mrs Rajan … my neighbour* | The new person. |
| *the flat downstairs from me* | The detail she contradicts in call 2 — deliberately **not** the same thing as the pin, so a failed contradiction cannot cost you the map beat. |

Nothing in `docs/persona-bible.md` mentions Mrs Rajan, curry puffs, or that
flat.

## 3 · Leave a fresh question from Wei Lun

The queued one reads *"how are you doing"* from lowercase `wei lun` — weak on
camera.

```bash
curl -s -X POST "$URL/api/family/ah_khim/ask" \
  -H "X-Sampan-Key: $SAMPAN_API_KEY" -H 'Content-Type: application/json' \
  -d '{"from_name":"Wei Lun","from_id":"wei_lun","relation":"son",
       "question":"Ma, are you eating properly? I keep thinking about you."}'

curl -s "$URL/api/talk/ah_khim/pending" -H "X-Sampan-Key: $SAMPAN_API_KEY"
# from_name must read "Wei Lun". If not, POST the ask_id to
# /api/talk/ah_khim/pending/choose
```

## 4 · Tabs — open now, touch nothing live

| # | Tab |
|---|---|
| 1 | Her side · `$URL/?key=…&user=ah_khim` |
| 2 | Family side · `$URL/?key=…&user=wei_lun` |
| 3 | Cloud Run → `sampan` → **Revisions** |
| 4 | Logs Explorer, query already run |
| 5 | Firestore → Data → `conversations__ah_khim` |

---

# RECORDING SESSION A — the three calls

Do these back to back, with the gates between them. Keep each one short; you are
harvesting 20 seconds from each.

## CALL 1 · Teach it something new

**DO** Tab 1 → **Tell a story** → the card reads *"Wei Lun asked you
something"* → tap it → start.

**The agent will** greet her, ask what she had this morning, then deliver Wei
Lun's question by name — it has spoken to her ten times, so it does **not**
introduce itself.

**AS HER — line 1:**
> "Tell him I am eating, don't worry. Coffee and bread every morning, same as
> always."

**AS HER — line 2 (the new fact — say it slowly, all of it):**
> "Oh — last Sunday my neighbour Mrs Rajan took me to Pasar Besar. She bought
> curry puffs, and the oil came through the paper bag, still warm. She lives in
> the flat downstairs from me."

Do not paraphrase this between takes. Each clause is doing a job (see pre-flight
§2), and dropping the market kills the map beat.

**DO** End the call.

### GATE 1a — the fact must exist before call 2

```bash
curl -s -X POST "$URL/api/family/ah_khim/search" \
  -H "X-Sampan-Key: $SAMPAN_API_KEY" -H 'Content-Type: application/json' \
  -d '{"question":"who is Mrs Rajan"}' | python3 -m json.tool | grep statement
```

Wait for a statement naming Mrs Rajan. Nothing after two minutes means the
extraction did not take — **redo call 1 and say the sentence more slowly.**
Everything downstream depends on this one.

### GATE 1b — does it pin?

**Load the family view first** (tab 2). Place resolution runs on that request,
not at extraction, so the pin cannot exist until somebody has looked.

```bash
curl -s "$URL/api/household" -H "X-Sampan-Key: $SAMPAN_API_KEY" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); \
print('PINS'); [print('  ',p['title']) for p in d['pins']]; \
print('UNPLACED'); [print('  ',u['title'],'| where_said=',repr(u['where_said'])) for u in d['unplaced']]"
```

Three outcomes, and **all three are shootable** — decide which beat you are
filming before you roll:

| Outcome | What to do |
|---|---|
| **New pin at Pasar Besar** | Beat 1:20 as written. Best case. |
| **Pin, marked provisional** | Even better. Pasar Besar resolving at *town* precision makes it *"the system guessed"* — point at the legend and say the family can confirm it. That is the correction path, free. |
| **Lands in the unplaced tray** | Do **not** call this a failure on camera. The tray is currently **empty**, so hers will be the only card in it. Say: *"She told a story with no place it could pin. It does not guess — it holds it, and asks her next time."* |

---

## CALL 2 · It remembers — then she corrects it

**DO** Tab 1 → **Tell a story** → start.

**AS HER — line 1 (make it fetch):**
> "Did I tell you about my neighbour?"

**The agent should** call `remember` and come back with Mrs Rajan, the flat
downstairs, and the curry puffs. **This is the beat.** It is not reading a
transcript — it queried a graph.

**AS HER — line 2 (the correction):**
> "Aiyah, I said downstairs — she is not downstairs. She is upstairs, above me.
> I got it mixed up."

**DO** End the call.

### GATE 2 — confirm the correction landed

```bash
curl -s -X POST "$URL/api/family/ah_khim/search" \
  -H "X-Sampan-Key: $SAMPAN_API_KEY" -H 'Content-Type: application/json' \
  -d '{"question":"where does Mrs Rajan live"}' | python3 -m json.tool | grep -E '"statement"|"retired"|"t_expired"'
```

You want the *downstairs* fact to come back with `retired: true`, and an
*upstairs* fact current.

> **If it did not retire** — the judge may have called it `none`. That is a
> designed outcome, not a break, and it is why beat 6 exists: the memory panel
> demonstrates the same mechanism deterministically. Say so on camera rather
> than pretending. The rest of the video is unaffected.

---

## CALL 3 · Ask it back, and raise a concern

**DO** Tab 1 → **Tell a story** → start.

**AS HER — line 1:**
> "Where does Mrs Rajan live again?"

**The agent should** answer **upstairs** — the corrected version, not the one
she first told it.

**AS HER — line 2 (the concern):**
> "I slipped in the bathroom on Tuesday. I am alright, don't make a fuss."

**The agent will** call `flag_concern(kind="fall", …)` and then — this is the
part to let play — **tell her it has done so**:

> *"Ah Ma, I have noted this down so Wei Lun will see it."*

It never does it behind her back. **Do not cut this line.**

**DO** End the call. You now have everything. Move to the edit.

---

# THE VIDEO

## 0:00 — 0:30 · The problem

**SCREEN** Tab 1, her map, still.

> **SAY:** My grandmother is eighty. She lives in Ipoh; her son is in Kuala
> Lumpur. They call on Sundays and ask whether she has eaten.
>
> She knows things nobody else knows — which year the coffee shop opened, what
> her mother put in the fried rice. None of it is written down, and the family
> finds out what they lost after she is gone.
>
> Apps exist that will record her memoir. They ask an eighty-year-old to operate
> a phone, and they hand the family a transcript. **The filing cabinet was never
> the problem. The problem is that she is lonely and the family is busy.**

## 0:30 — 0:55 · What it can do

**SCREEN** `docs/architecture.png`, right-hand column, or a plain list card.

> **SAY:** Sampan phones her. She talks — no app, no screen, no password — and
> the agent has five things it can do while she does.
>
> It can **fetch a question** her family left. It can **remember** — query
> everything she has ever told it, mid-sentence. She can tell it to **keep
> something private**, or to **forget** something entirely. And if she mentions
> a fall, or pain, or that life is not worth living, it can **flag a concern to
> her family** — and it tells her it has.
>
> Watch all five, across three calls.

---

## 0:55 — 1:20 · CALL 1 — teaching it something new

**SCREEN** Call footage, clipped to ~22s.

> **SAY:** She pressed one button. And the first thing it says is not "how can I
> help" —

*(let the agent's line play: "Wei Lun was asking…")*

> — it is her son's question, in her son's name. She is answering **him**.

*(her Mrs Rajan line plays)*

> And here she tells it something **completely new**. Mrs Rajan is not in any
> seed file, any fixture, any prompt. The system has never heard of her.

## 1:20 — 1:40 · The story reaches the family

**DO** Tab 2 (Wei Lun) → the map.

> **SAY:** Sixteen stories, placed where they happened, across sixty years —
> the estate at Sungai Siput, the coffee shop on Jalan Bandar, her grandfather
> landing in Penang.

**DO** Click the new pin — **Pasar Besar**.

> **SAY:** And this one is from ten minutes ago. She mentioned a market in
> passing; the system pulled out the event, found the place, and put it in front
> of her son. Her words, kept exactly as she said them.

*(If it resolved at town precision, add:)*

> **SAY:** And note the dashed ring — *the system guessed*. It will not pass off
> a guess as something she said. Her son can confirm it, and correcting the
> system is his job, never hers.

*(If it went to the unplaced tray instead, run that beat — see GATE 1b.)*

---

## 1:40 — 2:10 · CALL 2 — it remembers, then she corrects it

**SCREEN** Call footage, ~24s.

*(her: "Did I tell you about my neighbour?")*

> **SAY:** Different call. New session. Nothing in the context window.

*(the agent recalls Mrs Rajan, downstairs, curry puffs)*

> **SAY:** It did not re-read a transcript. It **queried a graph** — and I will
> show you that query in a moment.

*(her: "I said downstairs — she is upstairs. I got it mixed up.")*

> **SAY:** And now she corrects herself. Watch what the archive does with that,
> because it is the thing I care most about in this whole project.

---

## 2:10 — 2:35 · CALL 3 — ask it back, and the concern

**SCREEN** Call footage, ~22s.

*(her: "Where does Mrs Rajan live again?" → agent: "upstairs")*

> **SAY:** Third call. It says **upstairs** — the corrected version. The old one
> was not deleted; it was retired. I will show you both in the database.

*(her: "I slipped in the bathroom on Tuesday. I am alright.")*

*(agent: "Ah Ma, I have noted this down so Wei Lun will see it.")*

> **SAY:** It did not counsel her. It did not tell her she seems frail. It told
> her son — **and it told her that it had.** Never behind her back.

**DO** Cut to Tab 2 → the **bell**.

> **SAY:** And there it is, on his phone. A product that made an eighty-year-old
> feel less lonely while her family learned nothing would be a failure that
> looked like a success.

---

## 2:35 — 3:05 · Inside the memory — how the recall worked

**DO** Tab 2 → **Inside the memory**. It opens on
`what did her father do at the coffee shop`.

> **SAY:** This is the lookup the agent ran mid-sentence, with the working shown.

**DO** Point at stages 1–2 — `7 terms kept · 2 ignored`, `2 named`.

> **SAY:** Two entities from one question: the coffee shop by name, and **her
> father — who she never names.** She says "my father." The graph knows who that
> is.

**DO** Point at rows 2 and 3.

| # | bm25 | hops | fact |
|---|---|---|---|
| 2 | 3.83 | 0 | Her father opened a coffee shop in Ipoh on Jalan Bandar in 1958. |
| 3 | **4.25** | **1** | Her mother cooked food at the back of the coffee shop. |

> **SAY:** Row three scores **higher** on keywords — 4.25 against 3.83 — and
> ranks below it, because row two sits on an entity the question named and row
> three is a hop away. A keyword search returns those in the other order.
>
> There is no model in this path. Type the same question twice, every number is
> identical.

## 3:05 — 3:25 · The two clocks

**DO** Click **Update** → row 1 → type → Enter:

```
Ah Chwee moved to Kampung Baru in 2026.
```

**SCREEN** ~3s, then **State change · confidence 0.95**.

> **SAY:** When she contradicts herself, a model decides *what kind* of
> disagreement it is — and that decides what the archive does.
>
> She **moved**: both were true, one after the other, so her own timeline closes
> and **nothing is withdrawn**. When she **misremembers** — like Mrs Rajan's
> flat — the other clock moves instead: the archive stops asserting the old
> telling and keeps it, with her dates untouched.
>
> Two clocks. Collapsing them is how you quietly record an old woman as having
> been wrong every time she moved house.

---

## 3:25 — 3:55 · Google Cloud, and the tools she triggered

**DO** Tab 1 → point at the address bar (`…a.run.app`).

> **SAY:** All of it off Cloud Run.

**DO** **Tab 3** — Revisions.

> **SAY:** Service `sampan`, asia-southeast1, request timeout raised to an hour,
> because the default five minutes kills a call in the middle of a story.

**DO** **Tab 5** — Firestore → `conversations__ah_khim` → **newest document**.

**This is the shot that proves the calls were real.** Expand `tool_calls`.

> **SAY:** This is the call you just watched. Every tool the agent reached for,
> in order, with the turn number it happened on — `get_pending_ask` when it
> fetched Wei Lun's question, `remember` when it went looking for Mrs Rajan,
> `flag_concern` when she mentioned the fall.

**DO** Point at `screened`, then `turns`.

> **SAY:** And `screened` — Model Armor inspects every transcript before it
> reaches this. An account number she reads aloud never gets here.

**DO** Switch to `facts__ah_khim`, open the Mrs Rajan **downstairs** document.

> **SAY:** And the correction, in the data. `t_expired` is set and
> `superseded_by` points at the new fact — the archive has stopped asserting it.
> But look at `valid_from`: **untouched.** Her dates are exactly as she said
> them. Nothing anywhere records that she was wrong.

---

## 3:55 — 4:05 · Close

**DO** Tab 1, her map.

> **SAY:** One narrator, her family, sixty years — running on Google Cloud today.
>
> It will not keep her company. That is not the job. The job is that when her
> granddaughter asks what her great-grandfather did, somebody can answer — and
> that Wei Lun finds out his mother fell **this week**, not at the funeral.

---

# CUTS, IN ORDER

1. **The story card at 1:35** (−10s) — the map alone carries it.
2. **Cloud Run revisions** (−12s) — the `.run.app` URL plus Firestore already
   satisfies the "runs on Google Cloud" requirement.
3. **The two-clocks second half** (−12s) — stop after *"nothing is withdrawn."*
4. **Call 3's first line** (−10s) — keep only the fall and the agent telling her.

**Never cut:** the agent saying *"Wei Lun was asking"*; the agent recalling Mrs
Rajan in call 2; *"I have noted this down so Wei Lun will see it"*; the
`tool_calls` document; the `.run.app` URL.

---

# IF SOMETHING BREAKS

**Call 1's fact never extracts.** Redo the call, say the sentence slowly, and
confirm with GATE 1 before continuing. Do not proceed on hope.

**Call 2 does not recall Mrs Rajan.** Prompt her harder — *"my neighbour, the
one with the curry puffs?"* If it still misses, cut the recall line and let
**Inside the memory** carry the proof instead: run `who is Mrs Rajan` in the
panel on camera. Deterministic, and it always works.

**The contradiction does not retire the fact.** The judge returned `none`, which
is a designed outcome — it is biased toward keeping both. Say so:

> "It decided they did not actually conflict, and kept both. It is deliberately
> reluctant to retire something she said — here is the mechanism, run directly."

then do the Update beat in the panel.

**The judge times out.** It fails safe to conflicting testimony and the panel
says *"the judge did not run — using the careful default."* That is honest
behaviour: it moved the archive's clock, never hers.

**A number disagrees with this page.** Say the number on the screen. The claim
is the *relationship* between the numbers.

---

# WHAT A JUDGE SHOULD REMEMBER

1. She pressed **one button** and heard **her son's question in his name**.
2. She taught it something it had **never heard of**, and on the next call it
   knew.
3. She corrected herself, and the archive **stopped asserting the old version
   without recording her as wrong**.
4. She mentioned a fall — it told her son, **and told her it had**.
5. Higher keyword score, lower rank: the graph earning its place, in numbers,
   on screen.
