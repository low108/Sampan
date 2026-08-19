# Build Plan — 17 Days

**15 Aug → 1 Sept 2026. Solo. ADK new.**

**Ordering principle: the data spine before the voice layer.** If streaming fights back in
week 3, you still have a complete, demonstrable product. If you build voice first and the
pipeline isn't ready, you have a talking demo with nothing behind it and no submission.

Three hard gates. Miss one and you cut, immediately, without renegotiating.

---

## Phase 0 — Infrastructure first (Day 1)

Do this **before writing any agent code.** IAM and deploy debugging is where solo hackathon
projects die, and it dies quietly on day 14 rather than loudly on day 1.

**Day 1 — 15 Aug**
- [ ] GCP project, billing, claim the $150 credits
- [ ] Budget alert at $30
- [ ] `gcloud` installed and authed
- [ ] **Deploy a hello-world FastAPI to Cloud Run.** Nothing else. Prove the deploy loop works
- [ ] On that service: `--timeout=3600 --min-instances=0 --max-instances=3`
- [ ] Shared-secret header auth, verified with `curl`
- [ ] Firestore database created, `asia-southeast1`
- [ ] Write one document from the deployed service. Read it back
- [ ] `pip install google-adk`, run the ADK quickstart locally

> **If you cannot deploy and write to Firestore by end of Day 1, stop and fix that.** Nothing
> downstream matters.

---

## Phase 1 — The data spine (Days 2–6)

No voice. No streaming. Text transcripts in, structured data out. This phase is testable
entirely offline and it is the part that makes the demo real.

**Day 2 — 16 Aug**
- [ ] Firestore collections per PRD §8
- [ ] Pydantic models for `Extraction`, `StoryCandidate`, `EntityMention`, `Entity`
- [ ] Extraction prompt v1 against `gemini-3.7-flash` with a strict response schema
- [ ] Run it on **seed session 1** transcript. Iterate until the two expected stories come out

**Day 3 — 17 Aug**
- [ ] Pinnability scoring (WHERE + WHEN mandatory, score ≥4)
- [ ] `missing_fields` generation
- [ ] Thread open/advance/close logic
- [ ] Run seed session 2. Assert both anchors are discovered

**Day 4 — 18 Aug**
- [ ] Entity resolution: alias matching + one LLM tiebreak
- [ ] Anchor storage and relative-date resolution
- [ ] Preference extraction
- [ ] Run seed sessions 3 and 4

**Day 5 — 19 Aug**
- [ ] Geocoding + the **unlocated tray** (Sungai Siput estate must land there)
- [ ] Profile recomputation
- [ ] Letter generation
- [ ] Pub/Sub trigger → Cloud Run job wiring

**Day 6 — 20 Aug** — **🚩 GATE 1**
- [ ] All four seed sessions run end to end through the deployed pipeline
- [ ] **Assertions in `seed-sessions.md` pass**
- [ ] `thread_coffee_shop.interrupted == true`
- [ ] `preferences.topic_sensitive` contains the sister

> **Gate 1 failed?** You have a data problem, not a time problem. Spend Day 7 fixing it and
> cut the map to a plain timeline. Do not proceed to voice with a broken spine.

---

## Phase 2 — Voice (Days 7–11)

**Day 7 — 21 Aug**
- [ ] ADK agent with `run_live`, text-only first
- [ ] FastAPI WebSocket endpoint, browser mic → PCM → `LiveRequestQueue.send_realtime()`
- [ ] Hear the model talk back. That's the whole day's win

**Day 8 — 22 Aug**
- [ ] `session_resumption` on (15-min Live API session cap)
- [ ] `enable_affective_dialog` on
- [ ] Reconnect handling both layers
- [ ] Deploy to Cloud Run and **verify a real call survives past 5 minutes** — this is where
      the `--timeout` setting proves itself

**Day 9 — 23 Aug**
- [ ] Companion tools: `get_pending_ask`, `get_open_threads`, `recall`, `get_preferences`,
      `note_preference`, `save_fragment`, `mark_private`, `flag_concern`
- [ ] System instruction assembled from the preference layer
- [ ] **Session opener logic** — candidate scoring, affect gating, two-option offer
- [ ] Verify: with seeded state loaded, the agent opens with the interrupted coffee-shop thread

**Day 10 — 24 Aug**
- [ ] **Audio fork** — ring buffer at WebSocket ingress, two lines
- [ ] WAV-wrap + `gemini-3.7-flash` affect call every 90s
- [ ] Structured state → session state
- [ ] Three axes + flags, transition hysteresis (2 consecutive assessments)

**Day 11 — 25 Aug** — **🚩 GATE 2**
- [ ] Affect state modulates the instruction live
- [ ] Graceful close on `fading`
- [ ] A full call runs against seeded memory and produces a correct extraction
- [ ] **End-to-end: ask → call → extraction → pin exists**

> **Gate 2 failed?** Cut the prosodic monitor to temporal + lexical signals only (no audio
> fork), and record the demo with whatever affect signal works. Update PRD §16.

---

## Phase 3 — Surfaces (Days 12–14)

Vibe-code this aggressively. It is the least valuable code in the project and the most
replaceable.

**Day 12 — 26 Aug**
- [ ] `/talk` — one big button, call screen, mic, playback. ≥22pt text, ≥64pt targets
- [ ] Notification → tap → open → greeting audio + mic live
- [ ] `/family` — ask composer with 10s voice note recording

**Day 13 — 27 Aug**
- [ ] `/family` feed: stories with audio, transcript, English translation
- [ ] Map with pins (Maps JS), filters by narrator and decade
- [ ] Unlocated tray visible

**Day 14 — 28 Aug**
- [ ] **Affect debug overlay** — the state pill and policy knobs, on screen. This is a demo
      asset, not a dev tool; make it look deliberate
- [ ] Timeline view (on-demand, per narrator)
- [ ] Full dress rehearsal of session 5 end to end
- [ ] Fix whatever that rehearsal breaks

> Map not done by end of Day 13? **Ship the timeline and move on.** The map never blocks
> submission.

---

## Phase 4 — Submission (Days 15–17)

**Day 15 — 29 Aug** — **🚩 GATE 3: feature freeze**
- [ ] `--min-instances=1`
- [ ] Reset to clean seeded state
- [ ] **Record session 5.** Multiple takes. Read to the script
- [ ] **Record session 6**
- [ ] Capture: Wei Lun's ask, the Archivist output, the map, the letter
- [ ] Capture console shots: Cloud Run detail, live logs, Firestore documents

> **No new features after Day 15.** Anything not working is now a P1 you didn't get to, and
> that is a perfectly respectable thing to write in a README.

**Day 16 — 30 Aug**
- [ ] Edit to 3:50. Burn in captions prepared from `demo-scripts.md`
- [ ] Overlay captions (the 8 listed in the demo script)
- [ ] Architecture diagram
- [ ] README with spin-up instructions — **judges check this even when they don't run it**
- [ ] Write-up: features, tech, findings, and **PRD §16 honest limitations, verbatim**

**Day 17 — 31 Aug / 1 Sept**
- [ ] Submit early in the day. Do not submit at 23:00
- [ ] Repo public, or shared with `testing@devpost.com` and `cloudhackathons@google.com`
- [ ] Bonus: `#AllThingsAgenticHackathon` post
- [ ] **Then: `--min-instances=0`, delete Pub/Sub, verify billing has stopped**

---

## Cut order if you fall behind

Cut from the bottom. Do not deliberate — the decision is already made here.

1. Imagen postcards
2. Chapters view
3. Elder voice-note reply
4. Hosted frontend on Cloud Run (P1 — accept losing the hosted-URL point)
5. Map → plain timeline
6. Memory Bank → Firestore only
7. Prosodic affect → temporal + lexical only
8. Session 6 → session 5 alone carries the demo

**Never cut:** the seeded memory, the session opener, the family ask attributed by name, or
the extraction pipeline. Those four *are* the submission.

---

## Daily discipline

- **Commit every day.** The repo's history is evidence of process for the judges
- **Screenshot anything that works**, immediately. Cloud Run consoles change and services get
  torn down; your only proof is what you captured
- **Keep a `FINDINGS.md`** as you go — surprises, ADK gotchas, what the Live API actually did.
  It writes the "findings and learnings" section for you and it's the part of the submission
  most people pad with nothing
- **Timebox debugging to 90 minutes.** Past that, cut the feature and note it

---

## Watch list

| Trap | Signal | Response |
|---|---|---|
| Cloud Run 300s default timeout | Calls die at exactly 5 minutes | `--timeout=3600` (already Day 1) |
| Live API 15-min session cap | Call drops mid-story | `session_resumption`; keep demo calls short |
| Stale Vertex AI docs in generated code | Import errors, 404 endpoints | Use `docs.cloud.google.com/gemini-enterprise-agent-platform/` |
| Model ID drift | 404 on model name | `gemini-3.7-flash`; Live model verified on Day 7 |
| Notification too quiet on Android | You miss your own test call | Known (PRD §9.4); film it honestly |
| IAM on the Pub/Sub → Cloud Run job hop | Silent failure, no logs | Test Day 5, not Day 15 |
