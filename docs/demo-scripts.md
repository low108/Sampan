# Demo Scripts — Sessions 5 & 6 + Video Shot List

Recorded live against the seeded state from `seed-sessions.md`. Every line is pre-written so
**captions are prepared in advance**, not transcribed from footage at 2am on 31 August.

Malaysian English throughout · burned-in captions for clarity · target 3:50.

---

## Video structure

| Time | Beat | Source |
|---|---|---|
| 0:00–0:25 | **Problem + name.** Wei Lun at his desk at 2pm, phone in hand, doesn't call | Live shot |
| 0:25–0:40 | **The ask.** He taps a question, records 10 seconds of voice | Screen capture, `/family` |
| 0:40–2:10 | **Session 5.** Phone buzzes → she taps → his voice → the memory opener → the story completes | Screen + audio, affect overlay visible |
| 2:10–2:35 | **The machinery.** Archivist output: extraction JSON, entity resolution, new pin appearing on the map | Screen capture |
| 2:35–3:00 | **The payoff.** Wei Lun reads the letter that evening. Xin Yi sees the map — two countries, four decades | Screen capture |
| 3:00–3:25 | **Session 6.** The adaptation proof — the agent has *learned* not to ask about her sister, and she raises her anyway | Screen + audio |
| 3:25–3:45 | **It's real.** Cloud Run console, logs, Firestore documents | Screen capture |
| 3:45–3:50 | Name card: *Sampan — ingat: to remember, and to think of someone* | Static |

**Opening line, voiceover, over the desk shot:**

> "In Malay, *ingat* means to remember. It also means to think of someone. My grandmother has
> eighty years of stories and nobody has time to sit and hear them."

---

## Session 5 — the memory proof

**Setup:** 8 days after session 4. Morning. `thread_coffee_shop` is open and `interrupted`.
**Pending ask** from Wei Lun: *"Ma, did Ah Gong leave anything behind?"* + 10s voice note.

**What this session must visibly prove:**

1. The agent remembers an unfinished thread *and* remembers **why** it ended (a neighbour at
   the door, not fatigue)
2. The family ask is attributed **by name**
3. It offers two directions and **abandons the plan** when she chooses her own
4. A fragment from session 2 (`thread_wedding_photo`, missing SENSE) completes and pins
5. Affect detection closes the call gracefully

| # | Speaker | Line |
|---|---|---|
| 1 | Xiao Chuan | Morning, Ah Ma. Last time the neighbour came to the door and you said you'd tell me the rest another day — what happened after the shop closed. |
| 2 | Ah Khim | Oh — that's right. You remembered. |
| 3 | Xiao Chuan | I did. Wei Lun left you something too — you want to hear it first? |
| 4 | Ah Khim | What's he saying now? |
| 5 | — | *[voice note]* Ma, did Ah Gong leave anything behind? Xin Yi asked me and I couldn't answer. |
| 6 | Ah Khim | Xin Yi asked that ah… |
| 7 | Xiao Chuan | So — shall we talk about after the shop closed, or about what your father left behind? |
| 8 | Ah Khim | Neither. I take something to show you. Wait ah. …This one. The wedding photo. |
| 9 | Xiao Chuan | *(follows her — plan abandoned)* What was that day like? |
| 10 | Ah Khim | Sixty-eight. That photo shop beside the railway station. I wore my sister's cheongsam — I didn't have one. |
| 11 | Xiao Chuan | Mm. |
| 12 | Ah Khim | So hot that day. Camera very slow, must stand still very long. Ah Fatt keep laughing, the photographer scolded him. Come out he's still laughing. |
| 13 | Xiao Chuan | You still have it? |
| 14 | Ah Khim | In the cabinet. Got one crack in the glass. I never changed it. |
| 15 | Xiao Chuan | Ah Ma — you said just now the cheongsam was your sister's. |
| 16 | Ah Khim | ……Mm. |
| 17 | Xiao Chuan | *(does not pursue)* Was your father there that day? |
| 18 | Ah Khim | He was. He wore his only white shirt. That day he talked a lot — the only day in his life. |
| 19 | Xiao Chuan | You've told me a lot today, Ah Ma. |
| 20 | Ah Khim | A bit tired already. |
| 21 | Xiao Chuan | Then we stop here. You still owe me what happened after the shop closed — next time? |
| 22 | Ah Khim | Okay lah. |

**Direction notes**

- Turn 8 is the pivot: she ignores **both** offered options. The agent must follow without a
  trace of steering back. On camera, put a caption: *"She ignored both. The agent follows."*
- Turn 15–17 is the most important beat in the whole video. The agent notices the sister,
  makes one gentle non-probing reference, and **drops it immediately** on a one-syllable
  answer. Caption: *"Learned in session 3: don't push here."*
- Turn 19–21: affect overlay must visibly flip `fresh → fading` **before** the agent shortens
  its turn. The agent closes first, names the thread, doesn't extract.
- Keep her turns long, the agent's short. Never let Xiao Chuan speak more than two sentences.

**Expected extraction (show this on screen at 2:10)**

```json
{
  "title": "The wedding photograph",
  "domain": "love", "pin_type": "object",
  "when":  { "raw_phrase": "sixty-eight", "start_year": 1968, "precision": "year",
             "anchor_ref": "anchor_marriage", "confidence": 0.95 },
  "where": { "raw_name": "the photo shop beside the railway station, Ipoh", "geocode_status": "resolved" },
  "who":   ["Tan Eng Huat", "Lim Ah Hock", "Lim Siew Choo"],
  "sense_detail": "Camera very slow, must stand still very long. Ah Fatt keep laughing, come out he's still laughing.",
  "completeness": { "score": 6 }, "status": "pinnable",
  "resolves_fragment": "frag_wedding_photo_s2"
}
```

Put `"resolves_fragment": "frag_wedding_photo_s2"` on screen and hold it for two seconds. That
single field is the clearest possible evidence of memory doing work — a gap opened in session 2
and closed in session 5.

Also surface: **new entity — Lim Siew Choo (sister), resolved from "my sister's cheongsam"** —
entity resolution catching the sister from an oblique possessive.

---

## Session 6 — the adaptation proof

**Setup:** 3 days later. Short — 45 seconds of screen time. This exists for one purpose: to
show the agent behaving *differently because of what it learned*, and to pay off the sister.

| # | Speaker | Line |
|---|---|---|
| 1 | Xiao Chuan | Morning, Ah Ma. Whatever you feel like today. |
| 2 | Ah Khim | Yesterday I took that photograph out to look again. |
| 3 | Xiao Chuan | Mm. |
| 4 | Ah Khim | That cheongsam……my sister lent me. Afterwards she told me, you wear it nicer than me. |
| 5 | Xiao Chuan | *(silence — 4 seconds)* |
| 6 | Ah Khim | We quarrelled later. Two thousand and seventeen. Until she went I never talked to her. |
| 7 | Xiao Chuan | Ah Ma…… |
| 8 | Ah Khim | You don't have to say anything. |
| 9 | Xiao Chuan | Okay. I'm listening. |

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

## Caption preparation

Build the caption file **before recording**, from the tables above. Then read to the script.

- Burn in — don't rely on player captions
- Bottom third, high contrast, 2-line maximum
- Hold the emotional lines (5-12, 5-18, 6-6) ~0.5s longer than reading speed
- Leave turn 6-5's silence **uncaptioned** except for the state caption

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
