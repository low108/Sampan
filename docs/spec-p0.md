# Spec — Sampan P0

**Status:** ready-for-agent
**Scope:** the P0 tier defined in `PRD.md` §6. P1 and P2 are out of scope (§Out of Scope).
**Deadline:** 1 Sept 2026.

---

## Problem Statement

Ah Khim is 80 and lives alone in Ipoh. Her son Wei Lun works long hours in Kuala Lumpur. He
misses her during the workday but can't stop to call; by the time he's free at night she's
asleep. Their windows never overlap, so they speak rarely.

Meanwhile she holds eighty years of stories — a village in Fujian she's only heard about, a
rubber estate childhood, her father's kopitiam and the day it closed — and nobody has time to
sit and hear them. Her granddaughter Xin Yi loves her but has nothing to talk to her about,
and can't read Chinese anyway. When Ah Khim dies, all of it goes with her.

Existing options fail all three of them. Video calls need both parties free at the same hour.
Family-history apps require Ah Khim to operate an interface and direct herself. Chatbots
forget everything between sessions and leave nothing behind.

## Solution

A voice companion that Wei Lun can send to his mother when he thinks of her.

He taps a question and records ten seconds of his own voice. Her phone buzzes; she taps once
and hears her son, then talks to an agent that already knows her — what she said last time,
where she stopped, who she's lost, and what not to ask about. It leads gently, follows her
when she goes elsewhere, and ends the call before she's tired.

Afterwards, the conversation becomes structured memory: stories with a place, a date, the
people in them, and one sensory detail each. They appear as pins on a family map with her
voice attached and a short letter in both Chinese and English. Wei Lun reads it that evening
and corrects anything wrong. Xin Yi finds something to ask her grandmother about at dinner.

The agent's purpose is stated in its own introduction — *"your son Wei Lun asked me to keep
you company and write your stories down for the family"* — because it is a ferry between two
generations, not a substitute for either.

## User Stories

**The elder**

1. As an elder, I want to never see a login screen, so that I can use this without asking my son for help.
2. As an elder, I want one large button to start talking, so that I don't have to learn an interface.
3. As an elder, I want to hear my son's actual voice when he asks me something, so that it feels like him and not a machine.
4. As an elder, I want to be told which family member asked, by name, so that I know someone was thinking of me.
5. As an elder, I want the agent to remember where we stopped last time, so that I don't have to start over.
6. As an elder, I want the agent to know the conversation was cut short by the doorbell rather than by my being tired, so that it invites me back to the same story.
7. As an elder, I want to be offered a choice of what to talk about, so that I'm not interrogated on someone else's agenda.
8. As an elder, I want to be able to ignore both options and talk about something else entirely, so that the conversation is mine.
9. As an elder, I want the agent to stop asking about my sister after I've changed the subject twice, so that I don't have to keep refusing.
10. As an elder, I want the agent to sit in silence when I say something painful, so that I'm not consoled at.
11. As an elder, I want the agent to speak in short turns, so that I can hear it and it doesn't talk over me.
12. As an elder, I want the agent to end the call when I get tired, so that I'm never left to say so myself.
13. As an elder, I want the agent to name what we didn't finish when it says goodbye, so that coming back feels like an invitation.
14. As an elder, I want to be asked no more than a couple of questions a call, so that it feels like company rather than an interview.
15. As an elder, I want the agent to receive a story I've told before as if it were the first time, so that I'm never made to feel forgetful.
16. As an elder, I want to say "keep that one private" out loud, so that I control what my family sees.
17. As an elder, I want the agent to tell me when it's flagging something to my family, so that nothing happens behind my back.
18. As an elder, I want to hear back a story it wrote down, so that I know I was actually listened to.

**The adult child**

19. As an adult child, I want to send a question mid-workday, so that I can act on missing my mother without a call I don't have time for.
20. As an adult child, I want to attach ten seconds of my own voice, so that she hears me and not a robot reading my text.
21. As an adult child, I want my question delivered to her promptly during her waking hours, so that it reaches her when she's free.
22. As an adult child, I want no question delivered between 10pm and 8am, so that she isn't woken.
23. As an adult child, I want to read what she said the same evening, so that I feel connected on the day I thought of her.
24. As an adult child, I want each story to carry a place and a date, so that it becomes part of a family record rather than an anecdote.
25. As an adult child, I want to hear her actual voice, so that the archive is her and not a paraphrase.
26. As an adult child, I want to correct a wrong name or place, so that the archive is trustworthy.
27. As an adult child, I want my correction to improve stories already recorded, so that fixing it once is enough.
28. As an adult child, I want to fill in a family intake once at setup, so that the agent doesn't ask her painful questions about people who have died.
29. As an adult child, I want to see which places couldn't be located, so that I can supply what she couldn't.
30. As an adult child, I want to be alerted if she mentions a fall or chest pain, so that the calls are also a safety net.

**The grandchild**

31. As a grandchild, I want an English translation beside the Chinese, so that I can read stories I couldn't otherwise.
32. As a grandchild, I want to see her life on a map, so that I can understand where my family came from.
33. As a grandchild, I want to filter to one relative or see the whole family, so that I can explore how I choose.
34. As a grandchild, I want her stories sorted into a timeline when I ask for hers, so that I can follow her life in order.
35. As a grandchild, I want a specific detail to bring up at dinner, so that I have something real to ask her about.

**The operator**

36. As the developer, I want the whole extraction pipeline testable from a text transcript, so that I can build and verify it without touching audio.
37. As the developer, I want seeded memory produced by the real pipeline, so that the demo's memory is genuine rather than fabricated.
38. As the developer, I want an on-screen affect state overlay, so that internal adaptation is visible in the demo.
39. As the developer, I want every service to scale to zero and cap its instances, so that the credits survive the build.

## Implementation Decisions

**Agents.** Three, per PRD §9.1. `Companion` runs real-time on the Gemini Live API via ADK.
`Archivist` runs asynchronously after a call. `Care` is a tool surface plus logging in P0, not
a separate runtime.

**Connection topology is fixed by ADK.** ADK is server-side and has no client-direct path, so
the browser connects to a FastAPI WebSocket on Cloud Run, which relays to the Live API.
Connecting the browser directly to the Live API is rejected: it removes ADK entirely, taking
tools, sessions and the audio fork with it.

**Audio forking happens at the application's own WebSocket ingress**, not inside ADK. ADK never
takes the microphone — the application pushes PCM into `LiveRequestQueue.send_realtime(blob)`.
The fork is therefore a second write to a rolling ring buffer alongside that call. ADK's
`save_live_blob` is rejected: it flushes only on turn boundaries and requires an artifact-service
round trip. There is no ADK plugin hook for live audio and none is needed.

**The affect monitor is a side channel, never a tool.** It must not sit on the conversational
latency path. It reads the ring buffer every 90s–3min, calls `gemini-3.7-flash`, and writes
structured state into ADK session state, which the Companion's instruction reads.
`RunConfig.enable_affective_dialog` is additionally enabled; it shapes model responses but
returns no readout, so it complements rather than replaces the monitor.

**Affect state is three orthogonal axes plus override flags**, not a flat enum, because "sad
and engaged" and "sad and withdrawing" require opposite responses. Energy is monotonic within
a call. Transitions require two consecutive assessments except `distress` and `agitated`,
which fire on one. From the design work:

```
energy:     fresh -> fading -> depleted          (monotonic; only `excited` partially reverses)
engagement: engaged -> drifting -> withdrawing -> closing
affect:     warm | excited | neutral | sad | anxious | frustrated | agitated
flags:      confused | looping | distress        (non-exclusive, override everything)
```

**Extraction is entirely post-hoc.** The Companion never chases schema fields mid-conversation.
In-call questioning is governed by one rule — *only ask what a curious grandchild would ask,
never what only a database would want* — with a hard budget of two clarifying probes per call,
none in the first three minutes, none while engagement is high. Gaps are filled by the
Archivist, and what remains becomes `missing_fields`, which generates a later session's
question. This resolves the standing tension between listening and extracting in favour of
listening.

**Topic domains are a categorisation and coverage structure, never a script.** The agent never
announces or works through them. They drive opener selection and post-hoc classification only.

**Three-tier data model: extraction → merge → profile.** Extractions are immutable, one per
conversation. Profiles are derived and regenerated, never hand-edited. Writing extraction
directly into a profile is rejected: no audit trail, no way to repair a bad extraction,
contradictions overwrite silently, and Firestore's 1MB document limit is reached within a year.

**Entities are first-class documents with stable IDs**, in a single collection discriminated by
`type` (person, place, object, food). Storing them as name-keyed maps on stories is rejected —
unqueryable, ungeocodable, and unable to dedupe *Ipoh* / *Ipoh town* / *town*.

**Entity resolution in P0 is alias matching plus one LLM tiebreak call**, seeded by the
child-completed family intake. Below threshold, create a provisional entity flagged for family
confirmation. Embedding-based resolution is deferred; the capability exists but is unnecessary
at seed scale.

**Time is stored twice.** Elders speak relatively ("before I married"), so every date keeps the
raw phrase alongside a resolved range with a precision enum and an anchor reference. The
profile accumulates anchor events, against which relative phrases resolve. Retroactive
re-resolution is out of scope.

**Pinnability is a score, not a judgement.** WHERE and WHEN are mandatory; score ≥4 of 6 pins.
Below that the story is a fragment, kept and linked to its thread. `sense_detail` is a
first-class required-in-spirit field — it is the difference between a fact and a story, and it
is what the letter is built around.

**Four pin types over one schema:** `place`, `person`, `object`, `timeline`. The map, the family
tree facet, the heirloom cards and the wisdom entries are four projections of the same records.

**The timeline is generated on demand** for one narrator when requested, not maintained as a
persistent structure.

**Geocoding failure is a first-class state.** An `unlocated` tray is visible, feeds the family
correction path, and generates a next-session clarifying question. Region-level approximate
pins are valid.

**Session opening is candidate scoring, then affect gating, then an offer of at most two.**
Candidates come from open threads, the pending family ask, a depth-appropriate new domain, and
date triggers. Affect read over the first two turns gates what is offered. The plan is
abandoned the moment the elder goes elsewhere.

**A family ask is always attributed by name**, at most one per call, delivered instantly during
waking hours and queued through a 22:00–08:00 DND window.

**Model selection.** Voice runs on a Live dialog model; the Archivist and affect monitor run on
`gemini-3.7-flash`. The hackathon requires Gemini 3.5 or newer and no Live dialog model meets
that bar, so compliance is satisfied via 3.7 and stated explicitly in the write-up rather than
left implicit.

**Cloud Run configuration is part of the contract, not deployment detail.** `--timeout=3600`
(the 300s default kills calls mid-story), `--max-instances=3`, shared-secret header auth,
`--min-instances` 0 while building and 1 only for recording. `RunConfig.session_resumption` is
enabled because Live API audio sessions cap at roughly 15 minutes.

**A PWA cannot produce an incoming-call UI.** Verified hard platform limit. P0 ships push →
high-priority notification with vibration → tap → app opens → greeting audio and live mic. The
gap is documented, not worked around.

## Testing Decisions

**What makes a good test here.** Test external behaviour at the highest available seam. Assert
on the *outcome* a user would notice — a story pinned, a thread left open, a topic never raised
again — never on prompt text, model call counts, or intermediate structures. Model output
varies between runs, so assert on structure, presence, and relationships rather than exact
wording; where wording matters, assert containment, not equality.

**Three seams, argued down from more.** No prior art exists — this is greenfield — so these
establish the pattern.

**Seam 1 — `ingest_conversation(transcript, context) -> ConversationOutcome`.** The entire
Archivist behind one function: extraction, entity resolution, threading, anchors, preferences,
pinnability. Takes text, returns everything derived. This is the highest seam in the system and
carries the most value, because it needs no audio, no streaming and no browser. The four
transcripts in `seed-sessions.md` are the fixtures and their per-session expectation tables are
the assertions. This is Gate 1 in the build plan.

Two assertions matter more than the rest, because the demo depends on them:
`thread_coffee_shop.interrupted == true` after session 4, and the sister recorded as
`do_not_raise` after session 3.

**Seam 2 — `build_session_plan(narrator_id, now) -> SessionPlan`.** The opener: candidate
scoring, affect gating, the two-option offer. Deterministic given a Firestore state, so it is
tested against the seeded state produced by seam 1 — which also proves the two seams compose.
Assertions: with the seeded state, the interrupted coffee-shop thread ranks first; a pending
ask is attributed by name; a topic marked `do_not_raise` never appears as a candidate; a low
opening affect reduces the offer to one light option.

**Seam 3 — `AffectStateMachine.apply(current, assessment) -> AffectState`.** Pure transition
logic with no model call: hysteresis (two consecutive assessments to transition), the
single-assessment exceptions for `distress` and `agitated`, and monotonic energy. Fast, exact,
and it isolates the rules most likely to break subtly.

**Deliberately not automatically tested.** The Live API streaming loop, browser audio capture,
the map UI, and prosodic classification accuracy. The first three are verified by the Day 14
dress rehearsal; the last cannot be validated at all with the available test data — the only
voice available is the developer's, not an elderly one. That limitation is recorded rather
than papered over.

## Out of Scope

Everything in PRD §6 P1 and P2, specifically: hosted frontend on Cloud Run, Imagen postcards,
elder voice-note replies, chapters clustering, Memory Bank integration, the native Android
wrapper, dialect support, the review-gate approval workflow, embedding-based entity resolution,
contradiction detection, retroactive anchor re-resolution, the care dashboard, cross-narrator
event merge, scheduled floor calls, telephony, Veo, and a full WCAG AAA audit.

Also out of scope: multi-family tenancy, authentication beyond the shared-secret header and the
device pairing code, and any production concern that does not affect the 1 Sept submission.

## Further Notes

**The seed sessions are load-bearing.** Session 5's opening line depends on the pipeline having
recorded *why* session 4 ended — a doorbell, not fatigue — and session 6's payoff depends on the
agent having learned in session 3 not to raise the sister, so that her raising it herself lands.
If seam 1 cannot produce those two states from the transcripts, the demo's central claim
collapses. Fix the pipeline; do not write the states into Firestore by hand.

**Build the data spine before the voice layer.** If streaming fights back in week 3 there is
still a complete demonstrable product. Built the other way round there is a talking demo with
nothing behind it.

**Infrastructure on day one, before any agent code.** IAM, service accounts and the Pub/Sub →
Cloud Run job hop fail silently and they should fail on 15 August, not 28 August.

**The riskiest assumption is not technical.** No real elderly person has tested this. Whether a
lonely elder will open up to an AI voice — the premise the whole product rests on — is
unvalidated, and all testing is the developer voicing a scripted persona. PRD §16 records this
and the submission write-up must carry it verbatim.
