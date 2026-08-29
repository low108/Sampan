# Sampan — Product Requirements Document

> **Sampan** — *ingat*: to remember, and to think of someone.

**Version:** 0.2
**Date:** 2026-08-15
**Deadline:** 1 September 2026 (17 days)
**Team:** solo
**Submission:** All Things Agentic Hackathon — Track: **The Collaborative Partner**

---

## 0. Constraints that shape this document

This PRD is written against a hard 17-day, solo build with a stated goal of **learning ADK
and agent engineering**, not shipping a product. Every requirement is tiered:

| Tier | Meaning |
|---|---|
| **P0** | Must exist by 1 Sept. Cutting this breaks the submission |
| **P1** | Build only if P0 is complete and on schedule |
| **P2** | Documented, deliberately deferred. Real product requirements, not v1 requirements |

Nothing in P2 is deleted. It is the difference between "we didn't think of it" and "we scoped
it out", and judges can tell the difference.

**Honest limitations are recorded in §16 and must appear in the submission write-up.**

---

## 1. Summary

Sampan is a voice AI companion for elderly parents and grandparents that listens to their
life stories, remembers across months of conversations, and turns what it hears into a shared
family memory map their children and grandchildren can explore.

An adult child, mid-workday, feels a pang of missing their mother. They can't call — but they
can tap a question and record ten seconds of their voice. Minutes later her phone buzzes. The
agent plays her son's voice, then listens for as long as she wants to talk. That evening the
son opens the app and finds a new pin on the family map: his mother's story about the coffee
shop his grandfather ran in Ipoh, in her own voice, with a date and a place he never knew.

**The agent is not a replacement for family. It is the ferry between two generations who
cannot reach each other at the same hour.**

---

## 2. Problem

In Malaysia — and across the Chinese diaspora in Southeast Asia — one migration pattern
repeats: grandparents came from southern China to rural Malaya, raised children who moved to
the cities for work, who raised children who barely know where the family came from.

Three failures compound:

1. **Elderly loneliness.** Adult children work long hours. Elderly parents are alone most of
   the day and asleep before their children are free.
2. **A timing mismatch.** The child's window is late at night. The parent's window is the
   afternoon. They rarely overlap.
3. **Silent heritage loss.** Elders hold decades of stories nobody has time to hear. When they
   die, the stories die — including the ones their grandchildren most wanted.

Existing options fail: video calls need both parties free at once; family-history apps require
the elder to operate an interface and self-direct; generic chatbots forget everything between
sessions and produce nothing lasting.

**Grounding.** Reminiscence therapy and structured life review are evidence-based
interventions for elderly wellbeing and mild cognitive decline. Sampan is a delivery mechanism
for reminiscence with a durable artifact as the by-product.

---

## 3. Users

### Primary — the elder ("Ah Khim", 80, Ipoh)

Speaks Malaysian English, mixes in Malay words. Android phone; uses WhatsApp voice notes,
avoids typing. Occasionally tired, hard of hearing on one side. Wants to be heard. Talks most
freely about her childhood, food, and the people who are gone.
**Will not log in, will not navigate menus, will not read small text.**

### Secondary — the adult child ("Wei Lun", 56, Kuala Lumpur)

Works long hours, feels guilty about not calling. Wants to know she's okay and to feel
connected without a 40-minute call he doesn't have. Sets up her phone, completes the family
intake, curates and corrects the archive.

### Tertiary — the grandchild ("Xin Yi", 19)

Never learned the dialect her grandmother grew up in. Loves her, has nothing to talk to her about. Uses the map to
find something to ask at the next family dinner.

**Design consequence.** The elder is who the product is built *for*. The family is both the
*motivation* (a question from a named person is the strongest reason to pick up) and the
*beneficiary* (the archive). The family app is not a second product — it is the elder's output
port and input port.

Full persona detail: `docs/persona-bible.md`.

---

## 4. Product thesis

The obvious objection is that this substitutes an AI for a family. Sampan is designed so the
opposite is structurally true:

| Mechanism | Tier | How it forces connection rather than replacing it |
|---|---|---|
| Every family ask is attributed by name | P0 | She hears *"Wei Lun was asking about you"* — the agent never takes credit |
| The child's actual voice opens the call | P0 | The first thing she hears is her son, not an AI |
| The agent presents as a helper working *for the family* | P0 | Its stated purpose reinforces the bridge every time it introduces itself |
| The map gives the family something to ask about | P0 | Stories become material for real visits |
| She can reply with her own voice note | P1 | The loop closes in both directions |

Success is measured by **family interaction that would not otherwise have happened**, not by
time spent talking to the agent.

---

## 5. The core loop

```
  Child taps a question + records 10s voice note
                 ↓  (instant; queued if within DND window)
  Elder's phone buzzes — notification, tap to open
                 ↓
  Agent plays the child's voice note, then listens and leads
                 ↓  (silent affect monitoring throughout)
  Call ends gracefully when she tires
                 ↓  Pub/Sub
  Archivist extracts stories, resolves entities, updates memory
                 ↓
  Story pinned to the family map, letter generated
                 ↓
  Child reads it, corrects it, asks the next question
                 ↓
  Corrections and the next question feed the next conversation
```

Every arrow is P0.

---

## 6. Scope

### P0 — must ship by 1 Sept

- Companion agent on Gemini Live API, Malaysian English, with tools
- **Full prosodic affect monitor** (audio forked at WebSocket ingress)
- Archivist: post-call extraction → stories + entities, one structured call
- Memory: open threads, preferences, semantic facts, session opener logic
- Family ask + 10-second voice note
- Web frontend, two routes: `/talk` and `/family` (served locally)
- Map with pins; timeline generated on demand per narrator
- Letter per pinned story
- Firestore; backend on Cloud Run
- Four synthetic seed sessions run through the real pipeline

### P1 — only if P0 is done and on schedule

- Frontend hosted on the same Cloud Run service (recovers the "hosted project" submission item)
- Imagen postcard per pinned story
- Elder replies with her own voice note
- Life chapters view

### P2 — deliberately deferred, documented

| Deferred | Why | What it would take |
|---|---|---|
| **Native Android wrapper for real incoming calls** | PWAs cannot produce a full-screen call UI — hard platform limit (§9.4) | TWA + Android Telecom / `CallStyle` notification |
| Dialect support (Hokkien, Cantonese, Teochew) | Poorly supported by all speech systems; largest technical risk, removed entirely | Better ASR, or a fine-tuned model |
| Review gate workflow | Replaced by a single boolean field in P0 | Approval UI + sensitivity classifier tuning |
| Embedding-based entity resolution | Alias matching + one LLM tiebreak is enough at seed scale | Firestore KNN (GA, available) |
| Contradiction detection, anchor re-resolution | Not demonstrable in 17 days | Straightforward once the graph is populated |
| Care view UI | `flag_concern` tool and log line kept; no dashboard | Family-side dashboard |
| Cross-narrator event merge | Requires a second enrolled elder; none available | Event similarity linking |
| Scheduled floor calls | Cannot be demonstrated in the window; **known gap** (§6.1) | Cloud Scheduler + policy |
| Telephony / WhatsApp voice | No clean GCP path | Third-party telephony |
| Veo memory clips | Bonus only | |
| WCAG AAA audit | Large text and big targets only in P0 | Full accessibility pass |

### 6.1 Known gap: neglected elders receive the fewest calls

Because v1 is family-triggered only, the elders who need this most — those whose children are
least attentive — receive the fewest calls. This inverts the mission. The fix is a **scheduled
floor**: if no family ask arrives in N days, the agent calls on its own. It is cut from v1
purely because it cannot be demonstrated inside the submission window, and it is named here so
it reads as a scoping decision rather than an oversight.

---

## 7. Feature specifications

### 7.1 Elder app — P0

Three tabs, no nested navigation, **no login ever**.

**Onboarding.** The child installs the app on the parent's phone and enters a pairing code from
their own account. The device holds a long-lived credential permanently. The elder never sees a
login screen, a password, or an account switcher.

**Tab 1 — Talk (default).** One large button. When a family ask is pending, the screen shows
the sender's name and photo and the button becomes *"Wei Lun sent you something"*. Incoming
asks arrive as a notification; tapping opens an in-app call screen (see §9.4 for why this is
not a true incoming call).

**Tab 2 — Map.** Her own stories, large cards, tappable pins, her own voice on playback. The
agent also surfaces individual cards conversationally at the end of a good call: *"I wrote that down. Want me to read it back to you?"*

**Tab 3 — Family.** Photos and names of family members. Tap a face to record a voice note back
(P1). Same component as the child's ask, reversed.

**Accessibility (P0 subset):** body text ≥22pt, headings ≥32pt, tap targets ≥64×64pt, high
contrast, no horizontal scrolling, no carousels, no hamburger menus. Full WCAG AAA audit is P2.

### 7.2 Family app — P0 unless marked

- **Ask** — pick or type a question, attach a 10-second voice note. One pending ask at a time
- **Feed** — new stories with audio, transcript, and English translation
- **Map** — pins filterable by narrator, domain, person, place, decade
- **Timeline** — generated on demand when someone requests a specific narrator's story, not
  maintained as a persistent structure
- **Correct** — edit any extracted fact; writes back to the entity graph
- **Intake** — one-time family setup: names, relationships, birthplace, deceased relatives,
  known no-go topics, photos. Bootstraps entity resolution and prevents painful early mistakes
- **Chapters** (P1) — narrative arc clustering
- **Care view** (P2) — mood trend, repetition and confusion counts

### 7.3 Call flow — P0

1. **Open with the family voice note** if one is pending, attributed by name
2. **Greet with one specific small thing** — the weather, a festival, *"Did you sleep well after we talked last time?"*.
   Never a generic opener
3. **Read affect silently over the first two turns.** Offer nothing yet
4. **Gate on that reading.** Low energy → one light option or just listen. Ended sad last time →
   hold that thread. Normal → proceed
5. **Offer at most two directions, warmly, never as a menu**
6. **Abandon the plan the instant she ignores it.** If she starts an unrelated story, follow her
   and never steer back. The plan is a fallback, not an agenda
7. **Close gracefully** when affect indicates fading, naming the unfinished thread as an
   invitation to return

### 7.4 Topic guide — invisible — P0

Topic domains are a **coverage and categorisation structure, never a script.** The agent never
announces or works through them. They are used for opener selection, post-hoc classification,
and gap identification.

**Domains:** Root · Journey · Taste · People · Events · Tradition · Work · Home · Love ·
Hardship · Objects · Play · Skills · Wisdom

**Depth gating.** Taste, Play, Work, Home are session-one material. Love and Events are mid.
Hardship, Loss and Regret require earned trust (3+ good sessions, or the elder raising it).

**The clarifying-question rule — governs all in-call questioning:**

> **Only ask what a curious grandchild would ask. Never ask what only a database would want.**

*"Where was that?"* and *"How old were you then?"* are things a real listener says. *"Can you specify the
year?"* is not. **Budget: maximum two clarifying probes per call**, never in the first three
minutes, never while engagement is high.

Everything else is filled by post-call extraction. Whatever remains missing becomes a natural
question in a *later* session. Extraction never pressures the conversation.

### 7.5 Affect monitor — P0, full prosodic

**Verified feasible.** ADK never takes the microphone — the application pushes PCM into
`LiveRequestQueue.send_realtime(blob)`. The fork is therefore two lines at the application's
own WebSocket handler:

```python
queue.send_realtime(blob)       # to the model
ring_buffer.append(blob)        # to the affect monitor
```

Every 90s–3min the ring buffer is WAV-wrapped and sent to a separate `gemini-3.7-flash` call
returning structured state. This runs off the critical latency path — never as a tool the
conversational agent calls.

Additionally, enable `RunConfig.enable_affective_dialog` — the Live API's native affect
adaptation. It shapes the model's responses but does not return a readout, so it complements
the monitor rather than replacing it.

**Signals**

| Class | Signals |
|---|---|
| Prosodic | speech rate vs. personal baseline, volume drop, pitch flattening, tremor, sighs |
| Temporal | response latency, intra-turn pauses, **turn-length trend**, silence frequency |
| Lexical | closers ("okay lah", "anyway"), deflection, "I told you already", repetition |
| Interactional | barge-ins, non-answers, questions bounced back, refusal to elaborate |
| Contextual | minutes elapsed, time of day, baseline, how the last 3 calls ended, anniversary proximity |

All prosodic and temporal signals compare against a **per-user baseline** in the preference
layer — "talking slowly" only means something relative to this person.

**State model — three axes plus override flags**

- **Energy:** `fresh` → `fading` → `depleted` (monotonic within a call; only `excited` partially reverses)
- **Engagement:** `engaged` → `drifting` → `withdrawing` → `closing`
- **Affect:** `warm` / `excited` / `neutral` / `sad` / `anxious` / `frustrated` / `agitated`
- **Flags** (non-exclusive, override everything): `confused`, `looping`, `distress`

**Control knobs:** `turn_length`, `speech_rate`, `question_type`, `silence_tolerance`,
`topic_action`, `checkin`, `care_flag`.

**Response policy**

| State | Response |
|---|---|
| Fresh + engaged | Deepen. Open questions. This is when stories get harvested |
| Excited / nostalgic | Get out of the way. Backchannel only. **Never interrupt.** Highest-yield state |
| Fading | Shorten own turns first. Open → closed questions. No new topics. Close within ~2 turns, naming the thread |
| Depleted | Close warmly in under 30 seconds. Do not extract. Ending early is a success |
| Withdrawing from a topic | Distinguish topic from call. Pivot once to a safe topic; withdraw again → close. Log to sensitivity list |
| Sad / grieving | Do not cheer up, do not pivot away. Slow down, raise silence tolerance, reflect back. Sadness while engaged is not a problem to fix |
| Not in the mood | Offer an out immediately. Drop the queued family ask rather than forcing it |
| Frustrated at the agent | Stop asking. Acknowledge, don't defend. *"You talk. I'll just listen."* Log as explicit negative signal |
| Agitated | Never interrupt, never argue, never correct. Lower stimulation. Validate the feeling, not the claim. **Flag for care** — sudden agitation in elderly people can be pain, infection, or sundowning |
| `confused` | **Validate, never reality-orient.** Don't correct the year, don't say "he passed away". Short concrete turns. Flag for care |
| `looping` | Receive the repeated story as if it were the first time. Never say "you already told me that". Log count for the family only |
| `distress` | Hard escalation. Alert family immediately, stay on the line, keep talking, do not hang up |

**How the state reaches the agent (corrected 2026-08-16)**

A live session's system instruction is sent once at connect, and every route for injecting
direction mid-call was tried and fails — `role="user"` makes the agent read its own stage
directions aloud, `role="system"` makes it acknowledge them aloud, `role="model"` breaks
turn-taking, verified by probing. **Continuous within-call modulation is therefore not achievable.**

Affect reaches the agent three other ways:

1. **The next call's instruction** — deterministic, testable, and what the demo shows
2. **Tool responses**, which are never spoken aloud, so guidance rides back on any tool call
3. **`enable_affective_dialog`** — the Live API's native in-turn adaptation

The monitor still runs live: it drives the on-screen overlay, the care flags, and the
end-of-call affect trace.

**Invariants**

- The agent **never names the detected state out loud**
- The agent's turn always shrinks before the user's does
- Spoken check-ins rate-limited to one per ~10 minutes, only on low confidence, severe state, or closing
- Transitions require **two consecutive assessments**, except `distress` and `agitated` (single strong signal)
- Every transition logged to the call's affect trace with triggering signals

### 7.6 Extraction and pinnability — P0

Extraction is **entirely post-hoc**, run by the Archivist after the call ends.

| Field | Required | Note |
|---|---|---|
| **WHERE** | ✅ | Place name; imprecise is fine, family corrects later |
| **WHEN** | ✅ | Year *or* era — "before I married" is enough |
| WHO | | At least one named person |
| WHAT | | An event with a beginning and end, not a generality |
| **SENSE** | | One concrete sensory detail |
| WHY | | Why it stayed with them |

**Pin at score ≥4, with WHERE and WHEN mandatory.** Below that it is a fragment: kept, linked
to its thread, retried in a later session.

**SENSE must not be dropped.** It is the difference between a fact and a story: *"we were poor"*
versus *"we ate white rice with soy sauce, and my mother said she had already eaten"*. It is the line the letter is built around.

**Pin types:** `place` (map) · `person` (family tree facet) · `object` (heirloom card) ·
`timeline` (wisdom, no location).

**`missing_fields` closes the loop.** A fragment missing `when` generates next session's
*"That coffee shop — was it before you married, or after?"* Extraction feeds the opener.

### 7.7 Privacy — P0 subset

- Every story carries `sensitivity` (`routine` | `sensitive`) and `review_state`
- P0: a single boolean gate; **P2**: the full approval workflow
- The elder can mark any story private by voice at any time (`mark_private` tool) — **P0**
- The agent is transparent when it flags something to family. It says so — **P0**

### 7.8 Map, timeline, letters

- **Map (P0):** pins per story, filterable by narrator, domain, person, place, decade
- **Timeline (P0):** generated on demand for one narrator, not persisted
- **Unlocated tray (P0):** geocoding failures are first-class, not hidden. They surface as
  family correction tasks *and* as next-session clarifying questions. Region-level approximate
  pins are valid states
- **Letters (P0):** short letter per pinned story, built around the SENSE detail,
  quoting her verbatim
- **Chapters (P1):** narrative arc clustering — *The village in Yongchun (–1949) · The crossing · Rubber estate years
  (1949–58) · The coffee shop (1958–69) · Moving to the city*
- **Stats (P0, free):** stories collected, years spanned, places, **hours of her actual voice preserved**
- **Postcards (P1):** Imagen illustration per pinned story

### 7.9 Care and safety — P0

- **Distress escalation** (falls, chest pain, breathlessness, hopelessness) → immediate family
  alert, agent stays on the line and keeps talking
- **Never reality-orient a confused elder.** Validation, not correction — the standard of care
- The agent never presents itself as a person, a friend, or a family member
- The agent never gives medical, legal, or financial advice

---

## 8. Data model

Three tiers. **Extraction → Merge → Profile.** Never extract directly into the profile: no
audit trail, no way to fix a bad extraction, contradictions silently overwrite, and the
document exceeds Firestore's 1MB limit within a year.

```
families/{family_id}
users/{user_id}                    # elder or family member
conversations/{conversation_id}    # transcript, audio refs, affect trace
extractions/{conversation_id}      # immutable model output for that call
stories/{story_id}                 # the pinnable unit
entities/{entity_id}               # type: person | place | object | food
threads/{thread_id}                # open loops
asks/{ask_id}                      # family questions + voice notes
profiles/{user_id}                 # derived, regenerated, never hand-edited
```

### 8.1 Extraction (per conversation, immutable)

```json
{
  "conversation_id": "...", "narrator_id": "...",
  "occurred_at": "...", "duration_sec": 840,
  "summary_short": "Talked about her father's coffee shop in Ipoh, and closing it in 1969.",
  "topics_covered": ["work", "home"],
  "affect_trace": { "opened": "warm", "closed": "fading", "peak_engagement_topic": "work" },
  "stories": [ /* StoryCandidate[] */ ],
  "entity_mentions": [ /* EntityMention[] */ ],
  "threads_opened": [], "threads_advanced": [], "threads_closed": [],
  "preferences_learned": [
    { "type": "session_length", "value": "fades ~11min", "confidence": 0.6 }
  ],
  "care_signals": [],
  "family_ask_addressed": { "ask_id": "...", "answered": true }
}
```

### 8.2 StoryCandidate

```json
{
  "title": "The coffee shop on Jalan Bandar",
  "domain": "work",
  "narrative": "...",
  "verbatim_quotes": [{ "text": "...", "turn_id": 14 }],
  "when": {
    "raw_phrase": "before I married",
    "start_year": 1958, "end_year": 1968,
    "precision": "relative",
    "anchor_ref": "anchor_marriage",
    "confidence": 0.7
  },
  "where": {
    "raw_name": "Jalan Bandar, Ipoh", "aliases": ["Jalan Bandar", "the shop"],
    "geocode_status": "pending", "confidence": 0.8
  },
  "who": [{ "surface_form": "my father", "entity_ref": null, "role": "father", "confidence": 0.9 }],
  "what": "...",
  "sense_detail": "The smell of bread toasted over charcoal at five in the morning, with butter.",
  "why_it_matters": "...",
  "emotion": { "valence": -0.2, "labels": ["pride", "loss"] },
  "pin_type": "place",
  "completeness": { "where": true, "when": true, "who": true, "what": true, "sense": true, "why": false, "score": 5 },
  "status": "pinnable",
  "missing_fields": ["why"],
  "sensitivity": "routine",
  "review_state": "draft"
}
```

### 8.3 Entity

```json
{
  "entity_id": "...", "family_id": "...",
  "type": "person",
  "canonical_name": "Lim Siew Choo",
  "names": { "en": "Lim Siew Choo" },
  "aliases": ["my sister", "Ah Choo"],
  "person": { "relation_to_narrator": "sister", "birth_year": 1941, "death_year": 2019, "living": false },
  "place":  { "geo": { "lat": 4.597, "lng": 101.09, "confidence": 0.6 },
              "admin": { "country": "MY", "state": "Perak", "town": "Ipoh" }, "kind": "shophouse" },
  "food":   { "dish": "kaya toast", "who_made_it": "entity_father", "occasion": "every morning" },
  "story_refs": [], "mention_count": 7,
  "first_mentioned_in": "conv_003",
  "confirmed_by_family": false
}
```

### 8.4 Temporal model

Elders speak in relative time. Store the raw phrase *and* a resolved range with precision and
provenance. The profile accumulates **anchor events** (see persona bible); once an anchor is
known, relative dates resolve against it. Retroactive re-resolution is **P2**.

### 8.5 Entity resolution — P0 simplified

Alias-list matching plus one LLM tiebreak call. Below threshold → provisional entity flagged
for family confirmation. The child-completed intake pre-seeds the graph and prevents most
early errors. Embedding-based resolution via Firestore KNN is **P2** (the capability is GA and
available; it is simply not needed at seed scale).

### 8.6 Memory layers

| Layer | Contents | Store | Tier |
|---|---|---|---|
| Session state | Within-call context, live affect state | ADK session | P0 |
| Open threads | Unfinished stories, status, last-touched | Firestore | P0 |
| Semantic memory | People, places, dates, relationships, who is deceased | Entity graph | P0 |
| Preferences | Pace, listen/talk ratio, question style, sensitive topics, session length, best time | Firestore, injected into instruction | P0 |
| Mood trajectory | Per-call affect, trending; repetition and confusion counts | Firestore | P0 (stored), P2 (UI) |
| Memory Bank | Managed cross-session consolidation | Agent Engine Memory Bank (GA) | P1 |

---

## 9. Architecture

### 9.1 Services

| Layer | Service | Notes |
|---|---|---|
| Conversational model | **Gemini Live API** (native audio) | Bidirectional streaming, barge-in, native audio out |
| Extraction | **`gemini-3.7-flash`** | One structured call per conversation |
| Affect monitor | **`gemini-3.7-flash`** (or `-lite`) | Side-channel over forked audio, every 90s–3min |
| Agent framework | **Google ADK (Python)** | `run_live` bidi streaming; satisfies the framework requirement |
| State & graph | **Firestore** | Stories, entities, threads, asks, profiles |
| Async orchestration | **In-process worker thread** | Runs on hang-up. Pub/Sub is correct at volume and is a documented gap (§16) |
| Hosting | **Cloud Run** | Backend only in P0; frontend served locally |
| Geocoding / map | **Geocoding API** + Maps JavaScript API | |
| Memory Bank | **Agent Engine Memory Bank** (GA) | P1 |

**Agents:** `Companion` (voice, real-time) → `Archivist` (extraction, merge, async) →
`Care` (wellbeing signals, escalation).

### 9.2 Model selection and hackathon compliance

The hackathon requires **Gemini 3.5 or newer**. The available Live dialog models are
`gemini-3.1-flash-live-preview` (Gemini API) and `gemini-live-2.5-flash-native-audio`
(GA on Google Cloud) — **neither is ≥3.5**.

**Resolution:** voice runs on a Live model; the Archivist and affect monitor run on
**`gemini-3.7-flash`**. The requirement is satisfied via 3.7, and this is **stated explicitly
in the submission write-up** rather than left for a judge to work out.

**Confirmed by probing (2026-08-16):** `gemini-3.1-flash-live-preview` does not exist on
Vertex; `gemini-live-2.5-flash-native-audio` is served from `us-central1` but not `global`.
The Live API therefore runs in its own region, separate from both the text models (`global`)
and the story data (`asia-southeast1`).

Note: `gemini-3.5-flash` exists but is documented as legacy. There is no GA Gemini 3.x Pro text
model. The Gemini 2.5 family retires 2026-10-16 — irrelevant to this build, relevant to anyone
continuing it.

**Documentation warning.** Vertex AI docs are frozen; the platform is now **Gemini Enterprise
Agent Platform**. Anything referencing `vertex-ai/generative-ai` paths is ≥3 months stale.
Expect AI-generated GCP config to hit this.

### 9.3 Connection architecture

ADK is server-side and has no client-direct path, so the topology is fixed:

```
Browser ──WebSocket──> Cloud Run (FastAPI + ADK) ──> Gemini Live API
                            │
                            ├── audio fork ──> affect monitor (gemini-3.7-flash)
                            └── Pub/Sub ──> Archivist job
```

Connecting the browser directly to the Live API would remove ADK entirely — no tools, no
sessions, no audio fork. Not an option.

**Cloud Run settings — non-negotiable:**

| Setting | Value | Why |
|---|---|---|
| `--timeout` | `3600` | **Default is 300s and will guillotine calls mid-story** |
| `--min-instances` | `0` building / `1` recording & submission / `0` after | Cold start on first ring is a UX tax at the worst moment |
| `--max-instances` | `3` | Caps runaway spend |
| Auth | Shared-secret header | Protects the endpoint from traffic draining credits |
| Session resumption | `RunConfig.session_resumption` on | **Live API audio sessions cap at ~15 min** |

An instance with an open WebSocket cannot scale to zero and is billed as active for the call's
duration. Session affinity is best-effort; reconnect handling is required at both layers.

### 9.4 Platform limitation: PWAs cannot ring

**A PWA on Android Chrome cannot produce a full-screen incoming-call UI.** This is a hard
platform limit, verified:

- Android reserves `USE_FULL_SCREEN_INTENT` for apps providing calling/alarm functionality; the
  Play Store revokes it otherwise. No web API reaches it
- `Notification.CallStyle` is native-only
- The web `scenario: "incoming-call"` proposal is **Windows-only, behind a flag, with no Android
  milestone** and no signal from Firefox or Safari
- Custom notification sounds are **absent from the spec and from every browser** — proposed
  2014, removed 2018. One default chirp, no loop
- A service worker cannot play audio; nothing sounds until the user taps

**What ships in P0:** push wakes the closed PWA → high-priority notification with vibration and
the OS chirp → she taps → app opens → greeting audio plays and the mic goes live immediately
(an *installed* PWA is exempt from autoplay restrictions).

That is a notification, not a call. For elderly users who may not notice a single chirp, this
is a **material product risk**, and it is the single strongest argument for the P2 native
Android wrapper. It is stated in the write-up rather than glossed.

### 9.5 Companion tools

| Tool | Purpose | Tier |
|---|---|---|
| `get_pending_ask()` | Family question + voice note for this call | P0 |
| `get_open_threads()` | Unfinished stories, ranked | P0 |
| `recall(query)` | Retrieval over past stories and entities | P0 |
| `get_preferences()` | Pace, style, sensitive topics, baseline | P0 |
| `note_preference(type, value)` | Silent feedback capture | P0 |
| `save_fragment(...)` | Mid-call capture | P0 |
| `mark_private(story_ref)` | Elder-initiated privacy, by voice | P0 |
| `flag_concern(type, severity)` | Care escalation | P0 |
| `get_local_context()` | Weather, festivals (Chinese New Year, Qingming, Mid-Autumn, Hungry Ghost) | P1 |

---

## 10. Non-functional requirements

- **Latency:** first audio response under 800ms; affect monitoring never blocks a turn
- **Language:** Mandarin-primary with natural English/Malay code-switching, in conversation,
  storage, and generated letters. Family-facing playback carries transcript and English
  translation — the grandchild who can't understand Mandarin still gets the story
- **Availability:** DND 22:00–08:00 local; asks arriving in that window queue for the morning
  and the agent leads with them
- **Data residency:** `asia-southeast1`. Voice recordings of vulnerable adults; PDPA applies
- **Retention:** raw audio retained for the family archive; the elder can delete any recording by voice
- **Cost:** Flash for conversation and monitor; billing alerts set; all services torn down
  immediately after judging

---

## 11. Success metrics

| Metric | Why |
|---|---|
| **Pinnable stories per call** | Whether the agent listens well |
| **Family replies per pinned story** | Whether the bridge works |
| Fragment → pinned conversion across sessions | Whether memory improves extraction |
| Call answer rate | Whether she wants to pick up |

**Explicitly not a metric: session length.** Longer is not better for a tired 80-year-old; a
graceful early close is a success.

---

## 12. Build plan

Ordering principle: **the data spine
before the voice layer**, so a complete demo exists even if streaming fights back.

---

## 13. Demo plan

**Do not show two apps.** Follow **one story end to end**, which merges both halves in 90
seconds.

1. Wei Lun, at his desk, taps a question and records ten seconds of voice
2. Ah Khim's phone buzzes. She taps. She hears her son
3. She talks. **On-screen debug overlay** shows the affect state pill updating live and the
   policy knobs changing — she tires, the agent shortens its turns and closes gracefully,
   naming the unfinished thread
4. Cut to the Archivist output: structured extraction, entity resolution, a new pin
5. Wei Lun opens the map that evening and reads the letter, in her voice, with a place and a
   date he never knew
6. **Memory proof:** a later session opens with the unfinished thread from session 2 *and* the
   family ask attributed by name
7. Google Cloud console: Cloud Run service, logs, Firestore documents

Mandarin-primary with burned-in English subtitles, prepared in advance from the scripts rather
than transcribed from footage.

---

## 14. Submission checklist

| Requirement | Plan |
|---|---|
| Gemini 3.5 or newer | `gemini-3.7-flash` for Archivist + affect monitor; stated explicitly (§9.2) |
| Google agent framework | ADK (Python) |
| Google Cloud infrastructure | Cloud Run, Firestore, Pub/Sub |
| Hosted URL | P1 — seeded read-only view on the same service; torn down post-judging |
| Public repo | GitHub with README spin-up instructions |
| Architecture diagram | Companion / Archivist / Care + GCP services |
| ~4-min demo video | Per §13; must show the Cloud console |
| Track — clarifying questions | §7.3 step 5, §7.4 clarifying rule |
| Track — guides step by step | Opener logic, thread continuation, `missing_fields` |
| Track — captures feedback | Affect monitor (implicit), spoken check-ins (explicit), family corrections (two-sided) |
| Track — adapts to the user | Preference layer visibly changes the instruction between sessions |
| Bonus — Google AI models | P1: Imagen postcards |
| Bonus — public content | Build write-up, `#AllThingsAgenticHackathon` |

---

## 15. Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Cloud Run 300s default timeout kills calls | **High** | `--timeout=3600` on day one |
| Live API 15-min session cap | Medium | `session_resumption` on; demo calls kept short |
| Vibe-coded GCP config references frozen Vertex AI docs | Medium | Check against Agent Platform paths |
| IAM / service-account debugging consumes days | Medium | Deploy a hello-world Cloud Run service on day 1, before any agent code |
| Geocoding fails on ancestral villages and defunct estates | Medium | Unlocated tray as a first-class state; region-level pins |
| Map overruns the schedule | Medium | Timeline ships first; map is additive and never blocks submission |
| Notification too subtle for an elderly user | **Documented** | §9.4; native wrapper is P2 |
| Solo build, 17 days, ADK new | **High** | P0/P1/P2 tiering; data spine before voice layer |

---

## 16. Honest limitations

**These must appear in the submission write-up.** The design is stronger for stating them.

1. **No real elderly person has tested this.** All testing is the developer voicing a scripted
   persona. Whether a lonely elder will actually open up to an AI voice is **unvalidated** —
   and it is the assumption the entire product rests on.
2. **Affect thresholds are tuned on a young voice.** Prosodic signals for tremor, fatigue curve
   and rate decay in elderly speech cannot be validated with the available test data. The
   mechanism works; the thresholds are unproven.
3. **The extraction pipeline is tuned on scripted speech**, which is more fluent and better
   structured than the digressive, repetitive way elders actually tell stories.
4. **A PWA cannot ring.** The core interaction — the family reaching an elder who isn't already
   looking at their phone — is degraded to a notification chirp (§9.4).
5. **Family-triggered only.** Elders with inattentive families get the fewest calls (§6.1).
6. **Single narrator.** Cross-narrator features are untested; no second elder was available.
7. **Affect adapts between calls, not continuously within one.** The Live API cannot be
   steered mid-session (§7.5), so the agent's behaviour changes at the start of each call
   rather than turn by turn as she tires. Native affective dialog covers some of the gap; how
   much is unmeasured.
8. **Four P0 items are not built.** Web Push (so her phone cannot alert her when the app is
   closed — she sees the call screen on opening it), Pub/Sub (the Archivist runs in-process on
   hang-up), the 22:00–08:00 DND queue, and a geographic map (the journey view renders her
   stops as a route instead).
9. **There is no device identity.** Who "you" are is a `?user=` URL parameter, so anyone
   holding the shared key can act as any family member. This is deliberate for the demo — it
   lets one browser flip between her phone and her son's — but the elder-never-logs-in design
   assumed a paired device holding a durable credential, and that is not built. Real pairing
   is roughly a day's work and appears nowhere in the video.
10. **Affect discrimination is verified on synthesised speech, not elderly speech.** Controlled
   TTS deliveries were correctly separated, including the sad-engaged versus sad-withdrawing
   pair. Thresholds for real elderly prosody — tremor, genuine fatigue curve, age-related
   pitch change — remain unvalidated.

---

## 17. Future work

- Native Android wrapper — real incoming calls via Telecom / `CallStyle`
- Dialect support as speech models improve
- Telephony / WhatsApp voice, removing the app requirement entirely
- Scheduled floor calls for elders whose families are silent
- Cross-narrator event merge — two accounts of one wedding on a single pin
- Multimodal object capture: the family photographs an heirloom, the agent asks about it
- Printed book export of the chapters — the artifact families actually want to hold

---

*Sampan — one small boat, carrying a lifetime of stories.*
