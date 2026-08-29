# Sampan — project submission

*A voice companion that phones an elderly parent, remembers what she says across
months, and hands it to her family as something they can walk through.*

**Live:** `https://sampan-ig6xl5kf4q-as.a.run.app` ·
**Track:** Collaborative Partner ·

## 1. Description

Sampan phones her. She talks to Xiao Chuan — no app, no screen, no password. It
listens, remembers across months, and turns what she says into a map her family
can walk through. It carries their questions to her *in their name*, and carries
her stories back.

The design thesis, and the thing every decision below is measured against:
**the agent is a bridge to her family, not a substitute for them.** The failure
mode for a product like this is becoming the company she has instead of her son.

### Why the thesis is not a slogan

It came out of the literature, not out of a pitch deck. Jo et al.'s CareCall
deployment (CHI 2023, ~330 citations) is the closest published system to this
one — an LLM phone companion for socially isolated elderly people, at national
scale. What it reports is: reduced loneliness, real offload on care workers,
**and users who over-attach, who expect a memory the system does not have, and
who disclose more than they intended.** Lazar et al.'s systematic review of
reminiscence technology (2014, ~315 citations) reaches the same shape from a
different direction: the technology works best as a *conversation catalyst*, and
worst as a replacement for the person.

So Sampan is built to be visibly a bridge. Three concrete consequences:

- Xiao Chuan opens a call with a family member's actual question, attributed by
  name — never its own curiosity dressed up as theirs.
- When she says something that worries it, it does not counsel her. It tells her
  son.
- Every story is addressed outward: the map, the chapters and the letters exist
  for the family to read, not for her to re-read alone.

### The whole product in one picture

![The round trip: son to mother and back](round-trip.png)

**Reading it left to right:** Wei Lun leaves a question from Kuala Lumpur. It is
queued instantly. That afternoon his mother presses one button in Ipoh; the
service opens a live voice session with Gemini, and the **orange arrow** is the
moment the whole product exists for — the agent saying *"Wei Lun asked…"* and
then his question, in his name. She tells a story. Her tone triggers a concern
flag, which goes to her son and never to her. When she hangs up, the transcript
is screened and written, and both the story and the concern arrive in his bell.

Nine messages. She never opened an app, and she never spoke to a stranger — she
answered her son.

---

## 2. Features and functionality

### Her side 

She presses **Tell a story**. A live, bidirectional voice conversation opens.
There is no login, no account, no menu. The session carries:

| | |
|---|---|
| **A question from her family** | If Wei Lun left one, the agent opens with it, by name. This is the bridge working inbound. |
| **Five tools the agent can call** | `get_pending_ask`, `remember`, `mark_private`, `forget_this`, `flag_concern` |
| **An affect monitor** | Runs on the audio in parallel; never intervenes in the conversation |
| **Quiet hours** | A question sent at 11pm is queued instantly and *delivered* in the morning |
| **Open-thread reopening** | "Last time the neighbour came to the door and you said you'd tell me the rest another day" |

### Her side — the things that protect her

- **`mark_private`** — a topic she does not want in the archive. Captured
  silently; never announced back at her.
- **`forget_this`** — a subject she wants removed. Recorded, and honoured on
  retrieval.
- **Preference capture** — that she is hard of hearing, that her sister is a
  sore subject. Learned from behaviour, never recited to her. An agent that
  announces what it has learned about you is unsettling rather than attentive.
- **Cloud DLP** screens every transcript *before* anything is written.

### The family side

| Feature | What it does |
|---|---|
| **The map** | Her stories placed where they happened, 1946 → now. Pins distinguish *named in the telling* from *the system guessed*. |
| **Story cards** | Her words, kept as she said them, with a Veo-generated card image |
| **Chapters** | Entity communities, labelled — "the coffee shop years" |
| **Letters** | A short written piece per story, generated once and kept |
| **Ask her something** | Leave a question, optionally ten seconds of your own voice. It reaches her in your name. |
| **The bell** | New stories, answered questions, and **concern flags** |
| **Corrections** | The family may fix a name, a place, or merge two people |
| **Inside the memory** | The retrieval panel: retrieve, create, update — with the working shown |

### The rule that shapes the whole product

### The two clocks aka bi-temporal graph

![Two clocks: valid time versus transaction time](two-clocks.png)

**In plain language.** Every fact the system stores carries *two* separate
timelines, and it is worth being slow about this because everything else follows
from it:

1. **Her life** — when a thing was actually true. She lived in Sungai Siput from
That is a fact about the world.
2. **What the archive believes** — when the system started asserting it, and if
   ever, when it stopped. That is a fact about the *system*, not about her.

Now she says something that does not match. There are exactly two reasons that
can happen, and they need opposite responses:

- **She moved.** Both statements were true, one after the other. The *first*
  timeline closes . Sungai Siput until 2026, Kampung Baru after. Nothing is
  withdrawn, because nothing was ever wrong.
- **She misremembered.** One event, two accounts. The *second* timeline closes, 
  the archive stops asserting the older telling and keeps it. **Her own dates are
  not touched**, because the disagreement is about the account, not about her
  life.

Collapse those two into a single "update" and you get a system that records an
eighty-year-old as having been wrong every time she moved house. That is the
error the design exists to prevent.

### Inside the memory — the explainability panel

Three operations on the knowledge graph, each showing its working:

- **Retrieve** — type a question and watch the four stages: grounding (which
  terms survived, which entities the question named), exploration (what those
  reached within two hops), focus (BM25, hops, RRF for every candidate,
  including the rejected ones), and what the archive has stopped asserting.
- **Create** — write a sentence; it becomes an edge on whichever node it names
  and then competes for rank like any other. No special treatment for being new.
- **Update** — pick the telling she is correcting, say what she says now. Gemini
  decides which kind of disagreement it is, and *that decides which clock moves*.

Nothing in the panel is written to her archive — the sandbox rides on the
request and dies with it. That is not squeamishness about demo data. It is the
correction rule above, enforced in code.

---

## 3. Technologies used

![Sampan system architecture](architecture.png)

**Reading it left to right:** the browser is only a microphone and a map. Every
decision happens in the middle column, on Cloud Run. The right column is the
three Google AI models, each placed opposite the thing that calls it. The bottom
row is storage. The orange path is a live call; the blue path is the family
reading; the dashed paths happen after she has hung up and nobody is waiting.

The dashed orange box is the one security boundary that matters: **nothing
reaches the database without passing through DLP first.**

### Google AI models 

| Model | Where | Job |
|---|---|---|
| `gemini-live-2.5-flash-native-audio` | us-central1 | The conversation. Duplex native audio over a WebSocket. |
| `gemini-3.7-flash` | global, temperature 0.0 | Story extraction, fact extraction, contradiction judge, affect monitor, place resolver, letter writer, community labelling |
| `veo-3.1-fast-generate-001` | Vertex AI | Story-card video, off the call path via Pub/Sub |


### Google Cloud

- **Cloud Run** (`sampan`, asia-southeast1) — one FastAPI service. Request
  timeout raised to 3600s because the 300s default kills a call mid-story.
- **Firestore** (asia-southeast1) — the archive. Collections per narrator:
  `facts__`, `entities__`, `stories__`, `conversations__`, `asks__`,
  `concerns__`, `communities__`, `memories__`, `private__`, `forgotten__`.
- **Vertex AI** — all model calls, via `google-genai`.
- **Sensitive Data Protection (DLP)** — screening before every write. Two
  templates: `CREDIT_CARD_NUMBER` plus a custom `BANK_ACCOUNT_NUMBER` regex,
  and a de-identify template that replaces both.
- **Model Armor** — provisioned and wired, but **not the running backend.** It
  detects nothing itself: with only its SDP filter enabled it forwards to the
  same two DLP templates, so it costs a hop and a failure mode for no added
  detection (R18). Opt-in via `SAMPAN_SCREEN_BACKEND=armor`, which also brings
  its prompt-injection filter.
- **Pub/Sub** — the Veo generation queue, push-subscribed to
  `/internal/memories`.
- **Cloud Scheduler** — the weekly community refresh, posting to
  `/internal/communities`. The only scheduled work in the product: everything
  else is written by the call that caused it (§5.4).
- **Cloud Storage** — mp4 and poster for story cards.
- **Google ADK 2.7.0** — agent runtime, tool dispatch, session management.

### Application

Python 3.12 · FastAPI · Pydantic · uv · pytest · ruff · pyright ·
React 19 · TypeScript · Vite · Leaflet

**Scale:** 34 modules, ~8,900 lines of source, ~7,400 lines of tests,
**559 tests** (496 unit, 63 integration), 25 recorded architectural decisions.

### Where there is deliberately no model

Retrieval is **BM25 + two-hop breadth-first search + reciprocal rank fusion**,
with node-distance and episode-mention rerankers. No LLM anywhere in the read
path. The same question returns the same numbers every time — which is the only
reason it is honest to show the numbers at all.

---

## 4. Other data sources used

**Academic literature — the primary non-code input.** A Google Scholar–style
index was searched across **19 targeted queries**, returning **482 rows** now
kept in `research/scholar_csv/`, synthesised into a 213-line review at
`research/conversational-memory-literature-review.md` across nine areas.
Citation counts are as returned by that index on 2026-08-16 and are flagged
where they looked anomalous. Section 5 is the map from that review into this
codebase.

**OpenStreetMap** via CARTO tiles — the basemap the story pins sit on.

**Seed conversations — invented, and labelled as such.** Six transcripts
(four hers, two her son's) plus an intake fixture, all traceable to
`docs/persona-bible.md`. That document opens by stating the family is invented:
structurally true to the Chinese-Malaysian migration pattern — Fujian → rural
Perak → the city — but **no real person is depicted**. This matters twice: it is
the honest answer to "whose data is this", and it is the only defensible way to
build a system about an elderly person's private memories before that person has
consented to anything.

---

## 5. Research → implementation

This is the section the rest of the project hangs from. Every design below has
a citation behind it and a module in front of it.

### Six words you need for the rest of this section

| Word | What it means, plainly |
|---|---|
| **Knowledge graph** | Facts stored as *dots and lines* rather than paragraphs. "Ah Chwee" is a dot, "Sungai Siput" is a dot, and "lived at" is the line between them. It lets you ask *who* and *where*, not just search for words. |
| **Entity** | One of those dots — a person, a place, an object. The hard part is knowing that "my father", "Ah Hock" and "the man who ran the shop" are all the *same* dot. |
| **Valid time** | When something was true **in her life**. |
| **Transaction time** | When the **system believed** it. The two are different, and keeping them apart is the core of the design. |
| **BM25** | A decades-old, non-AI way of scoring how well a document matches a search term. Predictable, cheap, and it does the same thing every time. |
| **Bi-temporal** | Simply: carrying both of those clocks at once. |

### 5.1 Bi-temporal memory — Zep / Graphiti

> *The picture for this section is `two-clocks.png`, above.*

**Research.** Rasmussen et al., *"Zep: A Temporal Knowledge Graph Architecture
for Agent Memory"* (arXiv 2501.13956, ~360 cit). Entities and edges carry
**two independent time axes**: valid time (when a fact was true in the world)
and transaction time (when the system believed it). New facts *invalidate* old
edges rather than overwriting them, so history survives.

The review's verdict was blunt: this is *"the best-fit published model for
self-contradicting dialogue over months"* — which is precisely what an
eighty-year-old telling her life story over many calls produces.

**Implementation.** `facts.py` carries all four fields (`valid_from`,
`valid_to`, `t_created`, `t_expired`) and cites §2.2.3 in its module docstring.
`contradiction.py` implements Zep's candidate rule as written — same subject,
same predicate — in `candidates()`, and its two amendment operations in
`apply_state_change()` and `apply_conflicting_testimony()`.

**Where we depart.** Zep stores valid time as a timestamp. Elders do not speak in
timestamps. Ours is a `When`: her phrase (`"before I married"`), a resolved
year range when one can be derived, a precision (`exact / year / decade / era /
relative`), an optional anchor reference, and a confidence. Storing only her
phrase makes a timeline unsortable; storing only a guessed year loses how she
actually said it. We keep both.

### 5.2 Update semantics — Mem0, and where we go further

**Research.** Chhikara et al., *Mem0* (arXiv 2025, ~830 cit) — the deployed
reference: an LLM extracts candidate facts and applies **ADD / UPDATE / DELETE /
NOOP** against retrieved memories. The review's criticism is exact: *"conflict
resolution is 'LLM decides', not principled."* Unsolved-problem #4 says the same
thing at more length — *"I hated gardening" (2024) vs "I love my garden" (2026)*
— changed preference or different context? — *"delegated to LLM judgment
everywhere; no principled representation is evaluated."*

**Implementation, and our contribution.** We keep the LLM in the loop but give
it a *narrower and more consequential* question. It is not asked "update or
not". It is asked **which kind of disagreement this is**, and the answer selects
which clock moves:

| Verdict | What it means | What moves | Result |
|---|---|---|---|
| `state_change` | She moved house. Both were true, in sequence. | `valid_to` closes | Nothing is withdrawn; both facts stay current |
| `conflicting_testimony` | One event, two accounts. | `t_expired` + `superseded_by` | Old telling retired, **her valid time untouched** |
| `none` | They do not actually disagree | nothing | Both kept |

The prompt is biased toward `none`: *"an archive that quietly retires something
she said is worse than one holding two compatible statements."*

This is the difference between an overwrite and a representation. Collapsing the
two clocks is the exact error the bi-temporal design exists to prevent — and I
shipped that error and had to fix it, which is in §6.

### 5.2a The managed alternative — Vertex AI Agent Engine Memory Bank

Google ships the thing we built. **Agent Engine Memory Bank** is GA, it is the
first-party memory service for ADK — which we are already on — and wiring it
would be three lines:

```python
memory_service = VertexAiMemoryBankService(
    project=..., location=..., agent_engine_id=...
)
```

It would replace roughly 1,600 lines of ours: extraction, contradiction,
retrieval, entity resolution, communities. We evaluated it and did not use it.
Not because it is weak — it is grounded in a Google Research method published at
ACL 2025 (arXiv 2503.08026) and it solves its problem well. Because it solves a
**different** problem, in three ways that are load-bearing here.

**1. Its consolidation target is one current fact. Ours is two surviving
tellings.**

Memory Bank extracts facts with Gemini, then consolidates: for memories in the
same scope it decides whether existing ones should be *deleted or updated*,
checking whether new information is duplicative, complementary or contradictory.
The stated design goal is that memories are *"continuously up to date"*.

That is correct for a personal assistant and inverted for an archive. Ah Khim
said Mrs. Rajan lived downstairs, then said upstairs. Memory Bank's job is to
end up holding *upstairs*. Ours is to hold both, mark the first `t_expired` with
`superseded_by` pointing forward, and **show the retired one in the family
view**. The downstairs telling is not stale data superseded by better data. It
is something an eighty-year-old said, and the product's central promise is that
she is never corrected — only the system is.

**2. Its revisions are an audit trail of a record. Our clocks are a model of the
world.**

Memory Bank does have versioning, and we should be precise about it: revisions
are on by default, each `Memory` carries child `MemoryRevision` resources, and
consolidation appends one. So the change history exists and is inspectable.

But a revision answers *how did this record change*. Our `Judgement` answers a
different question, and it is the one the product turns on:

| | Memory Bank consolidation | This system |
|---|---|---|
| question asked of the model | is this duplicative, complementary, or contradictory? | **did the world change, or did her account of it change?** |
| resolution | delete or update the memory; append a revision | `state_change` closes `valid_to`; `conflicting_testimony` sets `t_expired` and leaves valid time **untouched** |
| what survives | one current memory + its revision history | two facts, both queryable, one visibly retired |

A revision records that the record moved. It does not record *why*, in the only
sense that matters here — whether Mrs. Rajan moved house, or whether Ah Khim
misremembered. Those are different facts about the world and they must not be
stored the same way. That distinction is §5.1 and §5.2, and it is the whole
reason two clocks exist rather than one timestamp.

**3. It stores model-written sentences. We store hers.**

Memory Bank's own examples are the tell: *"My preferred temperature is 71
degrees"*, *"I prefer aisle seats on flights."* Short, normalised, written by a
model *about* what the user said. Every fact in our graph instead carries
`quote` — the sentence she actually spoke — and the family view can open any
claim down to it (§5.5, §5.6).

For an assistant, the paraphrase is better: shorter, cleaner, cheaper in
context. For something her grandchildren inherit, an archive made of sentences a
model wrote about her is a different artifact from one made of sentences she
said. That is not a performance argument and no benchmark would show it.

**And a fourth, smaller: retrieval stops being showable.** Memory Bank retrieves
by embedding similarity. Ours is BM25 + two-hop BFS + RRF with a stored
`SearchTrace` (§5.3, §5.5) — the same query returns the same numbers, and the
demo puts `bm25=4.9223` on screen. "Semantically close" cannot be audited by a
family, or by a judge.

**What we would gain, honestly.** Consolidation and deduplication is precisely
where our bugs live — §6 documents a false entity merge that survived four
resets and answered a question about her neighbour with the wrong person. That
class of failure is Memory Bank's core competence, and adopting it would remove
it along with the maintenance burden. We are choosing to own a harder problem
because the representation is the product; that is a real cost, not a free win.

**The defensible architecture, stated plainly.** These are two different jobs
and conflating them is the error:

> Memory Bank for **agent continuity** — what the companion needs in order to
> feel like it knows her.
> The bi-temporal graph for the **archive** — what the family inherits.

We built the second. A production system might well run both, and nothing in
our design prevents it: `CallMemory` is constructed at the start of every call
from an injected repository, so a second memory source is an additive change,
not a rewrite.

*Caveat: Agent Engine's regional availability was not confirmed for
`asia-southeast1` at time of writing. Our data-residency choice (§3) is
deliberate, and would need verifying before any adoption.*

### 5.3 Retrieval — Zep §3, BM25, RRF

**Research.** Zep's retrieval is several searches for recall, then a reranker
for precision. Reciprocal Rank Fusion (Cormack et al.) supplies the damping
constant `k=60` used verbatim.

**Implementation.** `retrieval.py` runs BM25 (`k1=1.5`, `b=0.75`) over fact
text, breadth-first search to two hops from entities the question names, and RRF
to fuse them. *Plainly:* one method finds facts whose **words** match the
question, a second finds facts **near** the people the question named, and the
third merges the two rankings without either one being able to dominate. Two of Zep's rerankers are deliberately *not* implemented, and the
docstring says why: MMR, because *"diversity matters at five hundred results and
not at five"*; and the cross-encoder, because it puts a model back into a path
whose entire value is that it has none. Zep's third search — cosine over embeddings —
is left as a slot rather than an omission.

**One departure with a reason.** Terms under three characters are dropped. In an
archive full of *Ah Chwee*, *Ah Fatt* and *Ah Gong*, keeping `ah` means a
question about Ah Seng returns Ah Chwee, confidently and wrongly.

### 5.4 Communities — Zep §2.3

**Research.** Zep uses **label propagation rather than Leiden**, for
"straightforward dynamic extension".

**Implementation.** `communities.py` implements both: `detect()` for full
propagation to convergence, and a single recursive step for incremental
updates — the paper is explicit that the dynamic case is one step, not a rerun.
These become the family-facing "chapters".

**The half of it that is easy to skip.** Zep does not merely permit a periodic
refresh, it says one is *"necessary"* — the cheap dynamic extension is what
makes communities drift. Every other derived record in this system is written
by `finish_call` while the transcript is still in hand: stories, facts,
retirements, entities. Communities are the only one that cannot be, because a
refresh is full label propagation over the whole graph plus a model call per
chapter. That is seconds of work, and it must not happen while an
eighty-year-old is holding a phone.

So it is the one piece of scheduled work in the product:

```
Cloud Scheduler  ──weekly──▶  POST /internal/communities  ──▶  refresh_narrator()
```

Concretely: a Cloud Scheduler job (`scripts/setup_scheduler.sh`) posts weekly to
`/internal/communities`, which clusters and re-names every narrator's chapters.
Four decisions worth stating, because each is the kind that is usually made by
accident:

- **Weekly, not nightly.** One narrator produces a handful of new entities a
  week. Re-clustering every night would spend a model call per chapter to
  rediscover the same chapters. The job is idempotent, so the frequency is a
  cost decision and can be raised as the archive grows.
- **Header auth, not a key in the URL** — unlike `/internal/memories`, which is
  a Pub/Sub push target and *cannot* set a header. Cloud Scheduler can, and a
  key in a URL is a key in access logs and in screen recordings.
- **200 with per-narrator errors in the body**, never a 5xx. Scheduler retries
  on a non-2xx, and retrying a clustering pass that will fail identically only
  bills for it again — the same reasoning as the Veo push endpoint (§5.x, D21).
- **One narrator's failure does not stop the others.** The job runs unattended;
  a single corrupt graph must not mean nobody's chapters are refreshed for a
  week.

`scripts/refresh_communities.py` remains for running it by hand, and both paths
call the same `refresh_narrator()`. Two copies of a clustering pass would drift,
and the unattended one is the copy nobody notices has drifted.

### 5.5 Retrieval explainability — TrustGraph

**Research.** TrustGraph exposes what a query retrieved from the graph, modelled
on W3C PROV-O provenance: question → grounding → exploration → focus →
synthesis.

**Implementation.** `Inside the memory` reproduces that shape against our own
retrieval, with one advantage we can claim and they cannot: **our read path has
no model in it**, so the numbers are reproducible. TrustGraph spends an LLM call
on entity grounding; we do a substring sweep over a few dozen entities, which is
cheaper *and* deterministic.

The panel shows the rejected candidates as well as the returned ones. Those are
the more useful half — they show what the ranking weighed, not just what it
picked.

### 5.6 Extraction faithfulness — the critical literature

**Research.** This is the literature I took most seriously, because it is about
how the system fails rather than how it works.

- Huang et al., *npj Digital Medicine* 2024 (~334 cit) and Shah, *JAMA Network
  Open* 2024 (~100 cit): fabricated and run-inconsistent field values when
  schema-filling from unstructured text.
- Niimi, *"Distortion Instead of Hallucination"* (2026): under strict output
  constraints, models **distort content to satisfy the schema** rather than
  omitting what they do not know.
- Jiang et al., NAACL 2024 (~90 cit): hallucination tracks **entity
  frequency** — rare, ambiguous entities are worst-case. An elderly person's
  acquaintances are exactly that.

**Implementation.** Extraction is allowed to **refuse**. `fact_extraction.py`
has a `Refusal` type with the rule that declined each proposed edge; a fact
without a supporting quote is rejected rather than filled in. `build_facts`
refuses subjects it cannot resolve to a known entity. The extractor runs at
`temperature=0.0` — which was not the original setting, and §6 explains what
that cost.

### 5.7 Entity resolution — false merges cost more than false splits

**Research.** Welch et al. (CIKM 2012): in *incremental* settings, **false
merges propagate and contaminate everything attached to the merged node**.
Menestrina et al. (VLDB 2010, ~120 cit): pairwise precision/recall
mischaracterises merge/split error structure. The review flags honestly that the
asymmetry has never been *quantified* for personal conversational graphs.

**Implementation.** Resolution is conservative and records how it decided —
`matched_by` is one of alias, kin role, containment, tiebreaker, or new. When
two entities look like the same person, the system does **not** merge them. It
surfaces them to the *family* as a correction candidate. False splits are
visible and cheap to fix; false merges are invisible and poison the graph.

### 5.8 Event-anchored personal time

**Research.** Unsolved-problem #2: *"no working system normalizes such
expressions against a personal event timeline, and no agent-memory system stores
intervals-with-uncertainty."* TimeML/THYME support event anchoring on paper;
EventTempEx (AACL-IJCNLP 2025) is the one new tool and has zero citations.

**Implementation.** `anchors.py`. Once her marriage is known to be 1968, every
*"before I married"* acquires an upper bound. Both representations are kept —
her phrase and the derived range — with a precision and a confidence. Retroactive
re-resolution of facts recorded *before* an anchor was known is deferred and
labelled as deferred.

### 5.9 Unfinished threads — no literature at all

**Research.** Unsolved-problem #6: *"No system or benchmark represents open loops
('she never said how the dispute ended') — an obvious companion feature with no
literature."* The Area-1 verdict says the same: *"Nothing published handles
'unfinished conversational threads' as a first-class memory type — that is an
open design space."*

**Implementation.** `threads.py`, and its docstring states the design directly:
*"The single most valuable memory feature and among the cheapest."* The
distinction the module exists to preserve is **why** a thread was left open — a
doorbell means she was mid-story and wants to return; tiredness means the story
is done for today, and reopening it reads as nagging. Same open loop, opposite
correct behaviour.

### 5.10 Forgetting, consent, and the HCI evidence

**Research.**

- Jo et al., CHI 2024 (~123 cit): visible long-term memory **increases
  self-disclosure** — and some users are disturbed by "memory surprises",
  because they have forgotten what they told the agent.
- Unsolved-problem #8: *"No evaluated design lets a user inspect, correct, or
  delete what a companion remembers."*
- Hollanek & Nowaczyk-Basińska (2024, ~230 cit): the griefbot harms framework —
  consent, dignity, grief interference.
- Xiong et al., ACL 2026 (~94 cit): agents **over-trust stale memories**.

**Implementation.** `mark_private` and `forget_this` are tools the agent can
call *during the conversation*, so she never has to find a settings screen. The
family view exposes what the system holds, and the correction path is
first-class rather than an admin screen. Retired facts are kept and visibly
marked rather than deleted — which is also the answer to over-trusting stale
memory: the archive knows what it has stopped asserting, and says so.

**Where we depart from MemoryBank (Zhong et al., AAAI 2024** — the *paper*,
not Google's Agent Engine Memory Bank, which is §5.2a**).** Zhong et al. (~1,250 cit)
imports the Ebbinghaus forgetting curve as a decay policy. We do not implement
decay, and the review is why: disagreement #2 records that *"decay policies that
help benchmarks may harm the relationship"*, because elderly users **expect and
reward indefinite memory**. Forgetting here is something she asks for, not
something a curve does to her.

### 5.11 Affect, and the line we will not cross

**Research.** CareCall's reported harms: over-attachment, expectation gaps,
unintended disclosure. de Wynter (ACL 2025): *engagement does not equal
welfare*.

**Implementation.** `affect.py` monitors the audio alongside the conversation.
It does not counsel her, does not tell her she seems sad, and does not decide
anything. It raises a **concern flag to her son**. A product that made an
eighty-year-old feel less lonely while her family learned nothing would be a
failure that looked like a success.

### 5.12 How a call opens — scoring, trust gates, and the rule that voids it all

**Research.** Lazar et al. (2014, ~315 cit) find reminiscence technology works
as a *conversation catalyst* and fails as a replacement for one. CareCall (Jo et
al., CHI 2023) reports users who over-attach and who disclose more than they
meant to. Both point the same way: the system may **open a door**, and must never
push anyone through it.

**Implementation.** `opener.py` is deterministic given stored state — no model
decides how a call begins. Candidates are scored, and the scores encode a
product opinion:

| | score | why |
|---|---|---|
| `SCORE_INTERRUPTED` | 100 | She was cut off mid-sentence last time. Saying so proves the agent was listening, and nothing available beats it. |
| `SCORE_ASK` | 90 | A family question. One per call, always attributed by name. |
| `SCORE_DATE` | 45 | A festival is near — Qingming routes to `ROOT`, the ancestor domain. |
| `SCORE_THREAD` | 40 | Raised before, unfinished. |
| `SCORE_DOMAIN` | 20 | Never covered, and deep enough for this session. |

`MAX_OFFERS = 2`, because three options is a menu and a menu is an interview.

**Trust is a gate, not a preference.** `DOMAIN_DEPTH` assigns each subject an
intimacy level and `unlocked_depth()` opens them on a deliberately slow curve:

```
level 0  taste, play, work, home        available immediately
level 1  people, events, tradition      from session 1
level 2  love, roots, the journey       from session 3
level 3  hardship, wisdom               from session 6
```

Ancestry is unreachable until the third call and the hard years until the sixth.
That is a decision about earning intimacy, and steering **must not route around
it** — `choose_target` only ever selects from unlocked, uncovered domains, and a
subject she has refused is not merely deprioritised but permanently ineligible
(`may_raise`).

**And then the whole thing is disarmed.** `render_plan` ends every instruction
with:

> **"If she starts talking about something else, follow her. Everything above is
> void, and you never steer back."**

The target domain is introduced as *"somewhere she has not been, not somewhere
she must go"*, and the never-steer-back rule is placed **after** it so it is the
last thing the model reads. A plan that cannot be abandoned is an agenda, and an
agenda run against an eighty-year-old is the failure mode this project exists to
avoid. The system prepares carefully and then defers completely — which is the
bridge thesis at the level of a single turn.

### 5.13 Pinnability — a rubric in code, not a judgement in a prompt

**Research.** The extraction-faithfulness literature (§5.6) is consistent that
models asked to grade their own output drift, and Xiong et al. (ACL 2026) find
agents over-trust what they have already stored. Anything that decides what
reaches the family needs to be inspectable.

**Implementation.** `models.assess()` scores six fields — `where`, `when`, `who`,
`what`, `sense`, `why` — and applies one rule:

```python
pinnable = completeness.where and completeness.when
           and completeness.score >= PIN_THRESHOLD   # 4 of 6
```

`where` and `when` are **mandatory**; four of six pins. The threshold is a
product decision about what belongs on a family map, so it is computed in Python
and never asked of a model. The stored `ScoredStory` carries `completeness`,
`status` and `missing_fields`, which means a story that did not pin can always
say which fields it lacked — and the next call knows what to ask her.

A worked example from the real archive: *"Slipping in the bathroom"* scored
exactly **4 of 6**, missing `who` and `sense`, and pinned anyway because she gave
where and when. *"Market Curry Puffs with Mrs. Rajan"* scored 6 of 6. The rubric
is visible in the data, not asserted in prose.

This is the same commitment as retrieval (§2, *Where there is deliberately no
model*): the two places where the system decides what the family sees are both
deterministic, and both show their working.

---

---

## 6. Findings and learnings

### Where the literature disagreed 

The review's own "where the literature disagrees with itself" section forced
three choices:

1. **Structured memory vs. raw transcripts.** ConvoMem shows that under ~150
   conversations, full-history retrieval matches complex memory systems. We
   built structured memory anyway — because the disagreement decomposes by
   question type, and *temporal reasoning, knowledge updates and abstention* are
   exactly where structured wins. Those three are the whole product.
2. **Is forgetting good?** Benchmarks reward decay; elderly users reward
   permanence. We sided with the users (§5.10).
3. **Episodic richness vs. semantic compression.** Pink et al. argue compression
   destroys what episodic memory keeps. We store both — her exact words as the
   quote behind every fact, so the graph is an *index into* the transcript
   rather than a replacement for it.



---

## 7. What is genuinely new here

Of the eight problems the literature review lists as unsolved, this project puts
a working implementation against four:

| # | Open problem | What Sampan does |
|---|---|---|
| 2 | Event-anchored personal time | `anchors.py` — her phrase *and* a derived range, with precision and confidence |
| 4 | Contradiction semantics | The verdict selects the clock; two clocks, never collapsed |
| 6 | Unfinished threads as memory | `threads.py` — open loops, with *why* they were left open |
| 8 | Forgetting / consent mechanics | In-conversation `mark_private` and `forget_this`; corrections as a first-class family path |

None of these is evaluated at research standard, and I am not claiming they are.
What I am claiming is that they are **built, running, and honest about their
limits** — which is more than the review found anywhere for problems 6 and 8.
