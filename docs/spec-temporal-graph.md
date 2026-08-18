# Spec — Temporal Knowledge Graph memory (v2)

**Supersedes the memory sections of `spec-p0.md`.** Everything else in that
document — the voice loop, the map, the letters, the household — stands.

**Reference:** Rasmussen et al., *"Zep: A Temporal Knowledge Graph Architecture
for Agent Memory"* (arXiv 2501.13956), whose engine is Graphiti. Section
numbers below refer to that paper. Where this spec departs from it, the
departure is stated and argued.

---

## Problem Statement

The archive works, and three things about it are wrong.

**1. It cannot hold two accounts of the same event.** She will say the coffee
shop closed in 1969, and in a later session say 1970. Today the second silently
overwrites the first, and nothing records that she ever said 1969. For an
eighty-year-old telling sixty-year-old stories this is not an edge case; it is
the normal condition of the material.

**2. Retrieval during a call is a substring match.** `recall` matches a query
against entity names, aliases and `detail`. It cannot find a fact stated in
different words, it cannot traverse from a person to the place they worked, and
it has no notion of what is currently true versus what used to be.

**3. The agent has no way to lean toward a subject.** The session plan picks
topics before the call and is then void the moment she starts somewhere else —
correctly, since it must never steer back. But there is a difference between
*steering her* and *leaning*, and the system currently cannot do the second at
all. The domains that matter most for a family archive (`ROOT`, `TASTE`) are
the ones least likely to come up unprompted.

Separately, the surface has grown past what one call needs: nine tools, a
family-confirmation queue, and an affect monitor, all P0. Two of those are
worth having and neither is worth blocking the demo on.

---

## Solution

Rebuild memory as a **temporally-aware knowledge graph** in three tiers, after
Zep, with facts carried on edges and both time axes recorded.

- **Episodes** — full transcripts, non-lossy. Already exist.
- **Entities and Facts** — entity nodes (exist) plus **fact edges** (new). Each
  fact carries the sentence she said, when it was true in her life, and when
  the archive came to believe it.
- **Communities** — periodically regenerated clusters of entities. These are
  her *chapters*: "the coffee shop years", "the estate childhood".

Retrieval becomes one tool doing Zep's three searches with reranking, seeded by
the entities mentioned so far in the current call. Contradiction invalidates
rather than overwrites. Steering becomes an explicit, gentle policy carried on
the channel affect already uses.

### Re-tiering

| Capability | Was | Now | Note |
|---|---|---|---|
| Per-turn retrieval | — | **P0** | The thing a memory system is for |
| Fact storage with bi-temporality | — | **P0** | |
| Gentle topic leaning | — | **P0** | |
| Communities / chapters | P1 | **P0** | Falls out of the memory layer |
| Family confirmation of entities | P0 | **P1** | A review screen; nothing depends on it |
| Affect monitor | P0 | **P1** | **Keep running. Stop investing.** See Further Notes |

---

## User Stories

1. As Ah Khim, I want the agent to remember that my father's shop was on Jalan
   Bandar, so that I do not have to explain it again every call.
2. As Ah Khim, I want to be able to say the shop closed in 1970 having once said
   1969, without being corrected or contradicted.
3. As Ah Khim, I want nobody in my family to be able to overwrite what I said
   happened, because it is my life.
4. As Ah Khim, I want the agent to occasionally reach toward where I came from
   without ever pushing me there.
5. As Ah Khim, I want the agent to know what is *currently* true — that the shop
   is long closed, that my husband has died — so it never asks after them as if
   they were still here.
6. As Wei Lun, I want to see my mother's life in chapters rather than a flat
   list, so I can find the part I want.
7. As Wei Lun, I want to fix the map when it puts her village ninety kilometres
   from where it is, because that is the system's mistake and not her memory.
8. As Wei Lun, I want to see both times she told a story differently, so I am
   not shown a tidied version of my mother.
9. As Xin Yi, I want to ask what my great-grandfather did and get an answer
   assembled from things she actually said, each traceable to a sentence.
10. As the agent, I want one retrieval call that returns what is known about a
    subject, what she said about it, and what is still unfinished — rather than
    three tools returning fragments.
11. As the agent, I want to know which facts are no longer true, so I speak in
    the right tense about the dead.
12. As a developer, I want every fact to carry the sentence that produced it, so
    an assertion the archive cannot attribute is one it does not make.

---

## Implementation Decisions

### 1. The graph

`G = (N, E, φ)` in three tiers, following Zep §2:

| Tier | Nodes | Edges | Status |
|---|---|---|---|
| Episodic `Gₑ` | conversations | episode → entity (mentions) | transcripts exist; edges are new |
| Semantic `Gₛ` | entities | **facts** | nodes exist; **facts are the new thing** |
| Community `G_c` | communities | community → member entity | new |

Scoped per narrator, as today (`entities__<narrator>`, etc.).

`ScoredStory` **is not replaced and is not folded into facts.** A story is the
narrative unit — the thing with a sensory detail that becomes a letter. A fact
is the queryable projection. Forcing a story into triples destroys the thing the
product exists for. They coexist and both reference the same episode.

### 2. `Fact` — the edge

```python
class Predicate(StrEnum):
    """Closed vocabulary. The model chooses from it; it never invents one."""
    LIVED_AT, WORKED_AT, OWNED, MADE, ATE,
    MARRIED_TO, PARENT_OF, SIBLING_OF, NEIGHBOUR_OF, ESTRANGED_FROM,
    BORN_AT, DIED, TRAVELLED_TO


class Fact(BaseModel):
    fact_id: str
    subject_id: str                     # entity_id
    predicate: Predicate
    object_id: str | None               # entity_id when the object is an entity
    object_literal: str = ""            # when it is not
    statement: str                      # the retrieval surface, see §5
    embedding: list[float] | None = None

    # valid time (T) — when it was true in her life
    valid_from: When | None
    valid_to: When | None

    # transaction time (T') — when the archive believed it
    t_created: datetime
    t_expired: datetime | None = None
    superseded_by: str | None = None    # fact_id

    # provenance
    episode_id: str                     # conversation_id
    quote: str                          # her sentence — required
    confidence: float
```

Three deliberate departures from the paper:

**`Predicate` is a closed enum.** Zep lets the LLM name relations freely. Our
own history says not to: one refusal came back as *"the reason the shop closed"*
in session 2 and *"grandfather's shop shutting"* in session 4, no string match
reconciles them, and the subject stayed marked `do_not_raise` through the
session that was supposed to reopen it. The paper makes the same argument about
its own writes — it uses *"predefined Cypher queries… over LLM-generated
database queries to ensure consistent schema formats and reduce the potential
for hallucinations"* (§2.2.1). The model proposes; code owns the key.

**`valid_from` / `valid_to` are `When`, not `datetime`.** This is the
contribution. Zep stores valid-time as timestamps; the literature review's Area
4 verdict is that *"interval representations with explicit uncertainty… are
absent from all current agent-memory systems — Zep stores valid-time edges, not
uncertain intervals."* She says *"before I married"*. A `datetime` forces a
fabrication. `When` keeps `raw_phrase="before I married"`, `end_year=1968`,
`anchor_ref="anchor_marriage"` — an uncertain interval on a bi-temporal edge.

**`quote` is required, non-empty.** Same rule as the place linker, enforced the
same way: the quote must appear in the episode transcript (normalised for case
and whitespace, minimum length). A fact the archive cannot attribute to a
sentence she said is a fact it does not assert. This is the fourth application
of a lesson that has now cost four bugs.

### 3. Extraction — a separate pass

Facts are extracted by a **second model call** over the transcript, after story
extraction, with its own schema containing only fact fields.

Not by extending the story schema. The geocoder taught this: `Place` was used as
the resolver's `response_schema`, `Place` carried the linker's fields, and the
model filled fields the prompt never mentioned — bypassing a verification path
that existed and worked. **The schema is part of the prompt.** A fact-extraction
schema contains fact fields and nothing else.

Cost: one extra model call per completed call. Acceptable — it runs post-call,
off the latency path.

### 4. Entity resolution — Zep's pipeline, our tie-break

Two-stage: cheap candidate generation, then LLM adjudication (Zep §2.2.1).

```
mention
  ├─ normalise() + alias + kin_role          deterministic, runs first
  └─ miss ↓
     ├─ φ_cos  over entity names (embedded)
     └─ φ_text over entity names AND detail   ← the summary field matters
                    ↓
        candidates + episode context → LLM adjudication
                    ↓
        NeverMerges tiebreaker            ← ours, runs last
```

Kept from Zep: candidate generation by two complementary retrievers; matching
against the **summary** as well as the name (a new node named `"Ah Fatt"` with
detail *"the lorry driver who came every day"* must reach the existing
`"Tan Eng Huat"` whose detail says *"Lorry driver"*); and canonicalising to the
**most complete full name** on merge.

Not taken:

- **Binary `is_duplicate`.** `"Ah Chwee"` (the neighbour) and `"Ah Choo"` (her
  dead sister) are one character apart and will land in each other's candidate
  sets. If that merge fires, the agent asks brightly after the neighbour and
  reaches the sister. A wrong merge is unrecoverable and silent; a wrong split
  is one click. `NeverMerges` keeps the last word and splits on a tie.
- **The `n=4` message window.** Zep resolves per message while streaming. We
  resolve post-call over the whole transcript, so we see *"my sister"* in turn 3
  and her name in turn 40. Strictly better for this problem.
- **Cosine as first filter for kin terms.** *"my sister"* and *"my mother"*
  embed close together and are different people. `KIN_ROLES` runs first.

### 5. Contradiction and invalidation

Zep's mechanism (§2.2.3): an LLM compares a new edge against semantically
related existing edges; on a temporally overlapping contradiction it sets the
old edge's `t_invalid` to the new edge's `t_valid`, and *"consistently
prioritises new information."*

**Adopted, with contradictions routed to the correct time axis.** Zep provides
both axes; the mistake would be sending everything to T.

| Kind | Example | Action |
|---|---|---|
| **State change** — the world moved | she moved house in 2016 | `old.valid_to = new.valid_from`. Zep as written |
| **Conflicting testimony** — she recalls differently | *"closed in 1969"* → *"closed in 1970"* | `old.t_expired = now`; `old.superseded_by = new.fact_id`; **valid-time untouched** |

The second is most of the material in an oral history and none of the material
in an enterprise dataset. Applying Zep's rule literally to it yields *"her
father ran a coffee shop, and that stopped being true in 1970"* — a claim she
never made. The shop closed once. The disagreement is about the account, so it
lives on T′.

Rules that hold in both cases:

- **Nothing is ever deleted.** Invalidated facts remain readable.
- **Newest wins for display.** The map, timeline and letters read only
  `t_expired is None` and `valid_to.t_invalid is None`.
- **A contradiction becomes a question, not a decision.** It is a fragment with
  a disputed field, so it enters the opener's queue the same way a missing
  `why` does: *"you mentioned the shop closing — was that sixty-nine, or
  seventy?"* Resolution happens in conversation with her, not in a database.

### 6. Who may change what

**Her account is hers.** The family cannot edit, correct, resolve or delete a
`Fact`. Read-only, no exceptions, no admin path.

`corrections.py` currently mixes two different things and must be split:

| Claim | Whose | Editable by family |
|---|---|---|
| *"the shop closed in 1969"* | **hers** | **No.** Only she may revise it, in a later call |
| *"Sungai Siput is at 3.67°N"* | **ours** — a geocoder guess | **Yes.** It resolved to Sungkai, ninety kilometres off |
| *"Ah Chwee and Ong Ah Chwee are one person"* | **ours** — a resolver guess | **Yes** |

The existing place-correction and entity-merge paths stay. Anything touching a
`Fact` goes away.

### 7. Communities — her chapters

Following Zep §2.3, which uses **label propagation, not Leiden**, chosen for
*"straightforward dynamic extension… delaying the need for complete community
refreshes."*

- **Dynamic extension:** a new entity surveys its neighbours' communities and
  joins the **plurality**; the summary is then updated. One recursive step of
  label propagation.
- **Periodic refresh:** the paper is explicit that dynamic updates drift and
  *"periodic community refreshes remain necessary."* Full recomputation runs on
  a schedule (nightly, or after N new entities), not per call.
- **Summaries** by iterative map-reduce over member nodes.
- **Community names** carry key terms and are the search field for `N_c` — the
  same artifact serves the chapters UI and retrieval.

Expected output on the current archive:

```
{ Lim Ah Hock, Jalan Bandar, the coffee shop, kaya toast, Milo,
  Tan Eng Huat, Ipoh railway station }        → "The coffee shop years"

{ Tan Ah Tai, the line house, Sungai Siput, salted fish fried rice,
  the Singer sewing machine, Ah Chwee, the river } → "The estate childhood"
```

This subsumes the P1 "Chapters — narrative arc clustering" line in the PRD.

### 8. Retrieval — one tool

Replaces `recall`, `get_open_threads` and `what_do_you_remember`.

```python
def remember(query: str) -> dict:
    """Look up what is known about a person, place or thing she has mentioned."""
```

**Search field varies by object type**, per Zep §3.1 — for facts the `statement`
field, for entities the name, for communities the community name. Facts are
found by searching fact text, not by searching entities.

```
resolve      query → entity   (§4 pipeline)
seeds        {resolved entity} ∪ {entities mentioned so far this call}
search       φ_bm25 over Fact.statement
             φ_bfs  1–2 hops from seeds
             φ_cos  over fact embeddings
rerank       RRF  →  node distance from seeds  →  episode mentions
filter       t_expired is None
return       ≤5 facts with intervals, her quotes, unfinished threads
```

**Seeding from the current call is what makes agent-initiated retrieval feel
contextual.** Zep notes `φ_bfs` *"can accept nodes as parameters… particularly
valuable when using recent episodes as seeds."* We cannot retrieve per turn
under the Live API, but when the agent does call `remember`, the call's own
mentions steer the traversal.

Rerankers **not** used: **MMR** (diversity matters at 500 results, not 5) and
**cross-encoder** (an extra LLM call inside a live voice turn — latency we
cannot spend mid-conversation).

Response shape:

```
1958–1969 · her father ran a coffee shop at Jalan Bandar
   she said: "nineteen fifty-eight he opened a coffee shop in Ipoh, at Jalan Bandar"
still unfinished: why it closed
```

The last line has no Zep equivalent; the literature review found unfinished
threads unhandled anywhere.

### 9. Steering — leaning, never pushing

Two mechanisms, both existing channels:

1. **`SessionPlan.target_domain`** — one domain the call may lean toward,
   chosen from domains unlocked by `unlocked_depth(session_count)` and not yet
   covered. Rendered into the instruction as a *lean*, explicitly subordinate to
   the existing rule that the plan is void the moment she starts elsewhere.
2. **The guidance channel** — `_with_guidance` already attaches affect policy to
   every tool response. It gains one optional line: *"if a natural opening
   appears, her mother's cooking is somewhere she has not been."* Never an
   instruction to raise it.

Constraints, all existing and all kept: `DOMAIN_DEPTH` gating (`ROOT` and
`JOURNEY` are depth 2, unlocked at session 3 — ancestry is not first-conversation
material); sensitivity gating; at most two offers; **the agent never steers
back** if she goes elsewhere.

### 10. Tools: nine → five

| Tool | Fate |
|---|---|
| `recall`, `get_open_threads`, `what_do_you_remember` | **merged** into `remember` |
| `get_pending_ask` | keep |
| `flag_concern` | keep — safety |
| `forget_this` | keep — she asked |
| `mark_private` | keep — she asked |
| `note_preference`, `save_fragment` | **drop.** Both are inferable post-call by the Archivist, which already does it better than the agent noticing mid-conversation |

---

## Testing Decisions

Good tests here assert **external behaviour at the existing seams**, never
internals. The three seams stay; a fourth is added.

| Seam | Function | Kind |
|---|---|---|
| 1 | `ingest_conversation` | existing — extended with facts |
| 2 | `build_session_plan` | existing — extended with `target_domain` |
| 3 | `apply_assessment` | existing, unchanged |
| **4** | **`search_facts(query, seeds, graph)`** | **new — pure, no model call** |

Seam 4 is deliberately a pure function over a fixture graph, so ranking is
testable without a network. Model calls stay behind the existing protocols.

**Unit (no network), the cases that matter:**

- A conflicting-testimony contradiction sets `t_expired` and leaves
  `valid_from`/`valid_to` untouched. *This is the one most likely to regress.*
- A state-change contradiction sets `valid_to` from the new fact's `valid_from`.
- An invalidated fact is excluded from default retrieval and still readable.
- A fact whose `quote` is absent from the transcript is dropped — mirroring
  `test_privacy.py::TestPlaceLinkEvidence`.
- A `Predicate` outside the enum is rejected, not coerced.
- `"Ah Chwee"` and `"Ah Choo"` are **split**, not merged, and surfaced as a
  duplicate candidate.
- `remember` returns only currently-valid facts by default.
- Node-distance reranking prefers a fact one hop from a seed over an equally
  textually-relevant fact three hops away.
- A `target_domain` never appears as an instruction to raise a subject.

**Integration (`-m integration`, real model), extending Gate 1:** facts
extracted from the four seed sessions carry quotes that appear in those
transcripts; the shop-closing fact spans 1958–1969; communities over the seeded
archive produce at least two clusters, one containing the father and Jalan
Bandar. Assert **properties, never counts** — extraction is nondeterministic
about boundaries, as the notebook demonstrates (7 vs 10 stories from identical
input).

Prior art to follow: `test_privacy.py` for evidence verification,
`test_entity_resolution.py` for the split-not-merge cases,
`test_seed_run_integration.py` for chained-session properties.

---

## Out of Scope

- **Rewriting `ScoredStory`.** Facts sit alongside stories.
- **Replacing the Live API.** True per-turn retrieval needs a cascade
  (STT → text LLM → TTS); we keep native audio and accept agent-initiated
  retrieval.
- **Cross-encoder reranking.** Latency inside a voice turn.
- **A graph database.** Firestore documents plus in-process traversal. At this
  size, Neo4j buys nothing but an operational dependency.
- **Entity↔entity relations the model infers freely.** Only the closed
  `Predicate` set.
- **Family editing of facts.** Permanently out of scope, not deferred.
- **Hyper-edges** (Zep's multi-entity facts, §2.2.2).
- **Affect and family-confirmation work.** Both keep running untouched.

---

## Further Notes

**Sequencing, against 1 September.** This is a fortnight of work in a fortnight
that also contains recording and a rehearsal. Ordered so that stopping after any
step leaves a working demo:

1. `Fact` model, extraction pass, persistence — additive, nothing else changes
2. `remember` tool replacing three — the P0 the whole revamp is for
3. Contradiction and invalidation — needs (1)
4. `target_domain` steering — small, independent
5. Communities — the most droppable; chapters are a nice-to-have on camera

**If time runs short, stop after 3.** Steps 1–3 are the argument; 4 and 5 are
finish.

**Affect is demoted, not removed.** It is built, tested, and free to keep
running. It is also the thing that makes the agent stop pushing when she tires —
an elder-care property on a track called Collaborative Partner. Demotion means
*no further investment*, not deletion.

**Not letting the family correct is not the same as not letting them see.**
Repeated contradiction about the same event is exactly the signal `flag_concern`
exists for. Deliberately left as a P1 question and not designed here.

**A known mismatch, worth recording in FINDINGS.** Zep's *"prioritise new
information"* is a database instinct. With a narrator of eighty, recency is not
reliability — the later telling may be the less accurate one. We follow Zep
because the alternatives (trust the earlier account, trust the more confident
phrasing) need evidence we do not have. `superseded_by` and the ban on deletion
mean the decision stays reversible.
