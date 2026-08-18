"""Emit notebooks/knowledge_base_flow.ipynb."""

from __future__ import annotations

import json
import pathlib

cells: list[dict] = []


def lines(text: str) -> list[str]:
    """Split into source lines, newlines kept.

    nbformat concatenates this list with nothing between the entries, so a line
    that has lost its "\\n" is a line that has lost its line break. Markdown
    dropped that way renders as one fused paragraph — no headings, no tables,
    and words welded together at the old wrap points.
    """
    split = text.strip("\n").split("\n")
    return [line + "\n" for line in split[:-1]] + [split[-1]]


def md(text: str) -> None:
    cells.append({"cell_type": "markdown", "metadata": {}, "source": lines(text)})


def code(text: str) -> None:
    cells.append(
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": lines(text),
        }
    )


# ── 0 ────────────────────────────────────────────────────────────────────────
md("""
# Sampan — how the knowledge base actually works

Sampan is a voice companion that calls an elderly person, listens to her life
stories, and turns them into a family memory map. This notebook walks the
**memory** side of it end to end:

| Stage | What happens |
|---|---|
| 1 | A **pre-set knowledge base** — the child-completed family intake |
| 2 | **Recording starts** — what is committed into the model's context |
| 3 | **During the call** — the only two channels that reach the model mid-turn |
| 4 | **Recording stops** — the Archivist folds the call back into memory |
| 5 | The **diff** — exactly what changed |

Every cell calls the real functions in `src/sampan/`. Nothing here is a
simplified re-implementation for illustration; where the notebook cannot run
something (the audio stream itself) it says so and drives the same function the
WebSocket handler drives.

> **A note on the GraphRAG comparison.** This is deliberately *not* a GraphRAG
> pipeline. There is no embedding index, no community detection, and — as
> section 1 explains — no entity graph. Understanding why is most of the point.
""")

# ── setup ────────────────────────────────────────────────────────────────────
md("""
## 0. Setup

Nothing to install beyond the project's own dependencies (`uv sync`). The
knowledge base is swapped for an in-memory store so the notebook is safe to
re-run and never touches the real Firestore archive.
""")

code("""
import json
import os
import sys
from pathlib import Path


def load_env(root: Path) -> None:
    # Read .env the way the app does, so extraction can run in section 6.
    env = root / ".env"
    if not env.is_file():
        return
    for line in env.read_text().splitlines():
        if line.strip() and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip('"'))


ROOT = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
sys.path.insert(0, str(ROOT / "src"))
load_env(ROOT)

from sampan.config import Settings, apply_genai_env  # noqa: E402

settings = Settings()
apply_genai_env(settings)
print("Vertex project configured:", settings.configured)
""")

# ── 1 ────────────────────────────────────────────────────────────────────────
md("""
## 1. What this knowledge base is — and what it is not

The queries this product has to answer are **structural, not semantic**:

- *Which thread was left unfinished, and was it cut short by a doorbell or by tiredness?*
- *Which stories have a place but no year?*
- *What has she never said?*

Cosine similarity cannot answer any of those. "Interrupted by a neighbour"
versus "faded at eleven minutes" is a distinction that has to be **modelled**,
because it changes what the agent says next — one gets *"you still owe me the
rest"*, the other gets *"did you sleep well?"*.

So the store is a **typed domain model**, not a vector index.

### It is an entity *index*, not an entity *graph*

Worth being exact, because the word "graph" flatters it. Run this:
""")

code("""
from sampan.models import Entity, PersonMention

print("Entity fields:       ", list(Entity.model_fields))
print("PersonMention fields:", list(PersonMention.model_fields))
""")

md("""
`PersonMention` — how a story records who was in it — has **no entity id**. A
story names people as raw strings (`"my sister"`). There is no foreign key from
a story to an entity anywhere in storage.

The edges *are* computed at ingest, by `resolve_mentions()`, which returns
`Resolution(mention, entity_id, created, matched_by)` — and then **discarded**.
Nothing outside `ingest_conversation` ever reads them: `finish_call` persists
entities and stories, never resolutions, and the family-confirmation screen
works off entities still marked `provisional`, not off the edges. Section 6
shows them existing and then being thrown away.

The one genuinely persisted edge in the whole system is on **places**:
`Place.linked_from` + `linked_evidence`, e.g. *"my father's shop" → Jalan
Bandar, because she said so six weeks earlier.* That is why the map works and
there is no equivalent view for people.
""")

# ── 2 ────────────────────────────────────────────────────────────────────────
md("""
## 2. The schema

The GraphRAG equivalent of an ontology. Here it is a set of Pydantic models,
and the load-bearing idea is visible in `When`:
""")

code("""
from sampan.models import When, Where

for model in (When, Where):
    doc = (model.__doc__ or "").strip().splitlines()
    print(model.__name__, "--", doc[0] if doc else "(no docstring)")
    for name, field in model.model_fields.items():
        print(f"  {name:12} {str(field.annotation):24} {field.description or ''}")
    print()
""")

md("""
**Store what she said and what you concluded, side by side.** She says *"six,
seven maybe"* and, eleven turns later, *"I was born nineteen forty-six."* The
model resolves one against the other into `start_year`, while `raw_phrase`
keeps her words verbatim.

The same shape repeats:

| She says | The interpretation | Held in |
|---|---|---|
| `raw_phrase` "before I married" | `start_year` + `anchor_ref` | `When` |
| `raw_name` "my father's shop" | geocoded `Place` | `Where` → `Place` |
| `surface_form` "my sister" | `canonical_name` "Lim Siew Choo" | `PersonMention` → `Entity` |

Three payoffs from one decision: she keeps her voice in the letters, the map
and timeline can sort, and every inference stays auditable and correctable.

### Completeness is scored in code, not by the model
""")

code("""
from sampan.models import assess

print(assess.__doc__)
""")

md("""
Six fields — where, when, who, what, sense, why — threshold of four, with
`where` and `when` mandatory regardless of score.

The important part is that `missing_fields` is populated on **pinned** stories
too. A story that reached the map missing `why` becomes next session's *"that
coffee shop — was it before you married, or after?"* Gaps are not errors to
log; they are the question queue.
""")

# ── 3 ────────────────────────────────────────────────────────────────────────
md("""
## 3. Stage 1 — the pre-set knowledge base

Before the agent ever calls, one thing is filled in by the **child**, not the
elder: the family intake. This is what stops the agent asking brightly after
someone who died in 2019.
""")

code("""
from sampan.repository import Repository
from sampan.store import InMemoryDocumentStore

NARRATOR = "ah_khim"

raw = json.loads((ROOT / "seeds" / "intake.json").read_text(encoding="utf-8"))
intake = [Entity.model_validate(e) for e in raw["entities"]]

store = InMemoryDocumentStore()
repo = Repository(store)
repo.save_entities(NARRATOR, intake)

print(f"{'name':22} {'type':8} {'role':12} detail")
print("-" * 100)
for e in intake:
    print(f"{e.canonical_name:22} {e.type.value:8} {str(e.role or ''):12}"
          f" {e.detail[:40]}")
""")

md("""
Note `provisional=False, confirmed_by_family=True` on every one of these: the
family asserted them, so the agent treats them as settled. Anything the agent
discovers later arrives `provisional=True` and waits for confirmation.

Now queue the thing the whole product is built around — a question from her son:
""")

code("""
from sampan.models import Ask

repo.queue_ask(
    NARRATOR,
    Ask(
        ask_id="ask_001",
        from_name="Wei Lun",
        relation="son",
        question=(
            "Did Ah Gong leave anything behind?"
            " Xin Yi asked me and I couldn't answer."
        ),
    ),
)

memory_before = repo.load_memory(NARRATOR)
print("sessions so far:", memory_before.session_count)
print("threads:", len(memory_before.threads), " anchors:", len(memory_before.anchors))
print("pending ask:", repo.pending_ask(NARRATOR).question[:60])
""")

# ── 4 ────────────────────────────────────────────────────────────────────────
md("""
## 4. Stage 2 — recording starts

This is where the design departs most sharply from a normal agent loop.

With chat completions you rebuild the message list every turn, and that is your
retrieval hook. **The Live API has no such hook.** It is one persistent
bidirectional stream: the system instruction is sent *once, at connect*, and
the model keeps conversation state server-side for the session.

So the question is not *"what do I retrieve each turn"* but *"what do I commit
to before she speaks, and how does anything reach the model afterwards?"*

`prepare_call()` does the committing:
""")

code("""
from sampan.callflow import prepare_call

prepared = prepare_call(repo, settings, narrator_id=NARRATOR)

print("conversation_id:", prepared.conversation_id)
print("tools exposed:  ", [t.__name__ for t in prepared.agent.tools])
""")

md("""
The `conversation_id` carries a uuid suffix, not just a timestamp. Live
sessions cap at roughly fifteen minutes, so a dropped call and its redial can
land in the same second and the second call's stories would silently overwrite
the first's.

Now the instruction actually sent to the model — assembled in three layers,
concatenated rather than woven together so the diff between session 1 and
session 20 stays legible. This is the first call, so the middle layer (what
previous calls taught) is still empty and only the persona and the session plan
print:
""")

code("""
print(prepared.agent.instruction)
""")

md("""
Read what is in there, and then what is *not*.

**In:** the persona and hard rules; the learned layer (preferences,
sensitivities); and this call's session plan.

**Not in:** the stories. The entity index. The transcripts. **None of the
archive is preloaded.**

That is behavioural, not a context-budget decision. An agent holding nine
stories in context *acts* like it holds nine stories — it references things she
has not raised, and it steers. The archive stays behind the `remember` tool so
the agent reaches for it only when the conversation actually calls for it.

### The session plan is a plan, not a dump
""")

code("""
from sampan.opener import MAX_OFFERS, build_session_plan, unlocked_depth

plan = build_session_plan(
    threads=memory_before.threads,
    sensitivities=memory_before.sensitivities,
    ask=repo.pending_ask(NARRATOR),
    session_count=memory_before.session_count,
    last_closure=memory_before.last_closure,
)

print("greeting:", plan.greeting)
print("offers  :", [(o.kind.value, o.label) for o in plan.offers])
print("max offers:", MAX_OFFERS)
print("considered but not offered:", len(plan.considered))
print("depth at session 0:", unlocked_depth(0), "| session 6:", unlocked_depth(6))
""")

md("""
- **At most two offers.** Elderly plus voice means a menu of four is cognitive
  load, not choice. Everything else scored is kept in `considered` for the
  family-facing overlay only — it never reaches the model.
- **Sensitivity-gated.** A forbidden topic is not merely unoffered, it is
  *never scored*. Her late sister does not enter the context window at all.
- **Depth-gated.** `unlocked_depth(session_count)` — hardship is not
  first-session material.
- **The greeting is resolved in code**, because the persona is static text and
  cannot evaluate *"is this our first meeting?"*. That one shipped broken once:
  the condition read as a suggestion and the agent reintroduced itself on a
  session-5 call with full memory loaded.
""")

# ── 5 ────────────────────────────────────────────────────────────────────────
md("""
## 5. Stage 3 — during the call

Two channels reach the model once the stream is open. That is all there are.

### Channel one: pull — the agent asks

`build_tools(memory)` closes five tools over a `CallMemory` — down from nine.
`recall`, `get_open_threads` and `what_do_you_remember` became one `remember`
call, and `note_preference` and `save_fragment` are gone because the Archivist
infers both from the transcript afterwards, and better than an agent noticing
mid-conversation while trying to listen.

The notebook calls them directly; in production the model calls exactly these.
""")

code("""
tools = {t.__name__: t for t in prepared.agent.tools}
print(list(tools))
""")

code("""
answer = tools["get_pending_ask"]()
print(json.dumps(answer, indent=2, ensure_ascii=False))
""")

md("""
Two things to notice.

`ask_delivered` is now set on the call's memory — the agent has taken
responsibility for reading his question out. Section 6 shows when that is
allowed to actually consume the question.

And the response carries `_guidance` and `_turn_length`, which the agent never
asked for. That is channel two, arriving as a passenger.

### `remember` — the closest thing here to retrieval
""")

code("""
found = tools["remember"]("Ah Hock")
print(json.dumps(found, indent=2, ensure_ascii=False))
""")

md("""
`remember` returns **three** things: `known` (facts, each with the sentence
behind it), `she_said` (a search of her actual transcripts — empty here, since
this in-memory archive has no conversations yet) and `unfinished` (threads she
left open, which nothing published treats as a memory type).

`known` is empty at this point because no facts exist yet; section 9 shows the
ranking that fills it.

The comment in `tools.py` says why:

> *Extracted records lose sequence, context and affect, so the graph is only an
> index — her own words are the thing worth reaching.*

This is RAG turned inside out. The structured index is the **lookup key**, and
what comes back is her speech. No embeddings: the key is a name the agent
already heard her say.

### Channel two: push — riding on the response

The system instruction is fixed for the session, so there is no way to send the
model new direction. I tried three and all three failed in front of a user:

| Route | What happened |
|---|---|
| `role="user"`, fenced "do not read aloud" | Read the fence out loud, brackets and all |
| `role="system"` | Agent acknowledged it aloud: *"Alright, understood."* |
| `role="model"` | Turn-taking broke; it stopped answering her |

Tool responses are the one payload the model treats as data rather than speech.
So `_with_guidance` attaches the current affect policy to **every** tool
response, whatever that response was for.

The affect monitor forks the same audio and folds readings into a state
machine:
""")

code("""
from sampan.affect import apply_assessment, policy
from sampan.models import Affect, AffectState, Assessment, Energy, Engagement

state = AffectState()
print("start:", state.energy.value, state.engagement.value, state.affect.value)

tired = Assessment(
    energy=Energy.FADING,
    engagement=Engagement.WITHDRAWING,
    affect=Affect.NEUTRAL,
    flags=[],
    signals=["longer pauses", "shorter answers"],
    confidence=0.7,
)

state = apply_assessment(state, tired)
print("after 1 reading:", state.energy.value, state.engagement.value,
      "| pending:", state.pending is not None)

state = apply_assessment(state, tired)
print("after 2 readings:", state.energy.value, state.engagement.value,
      "| transitions:", state.transitions)
""")

md("""
**Two consecutive agreeing readings are required to move.** A single odd window
cannot make the agent lurch. Distress and agitation are the exceptions and act
immediately — those are not moods to debounce.

Energy is also ratcheted: it only worsens, and only excitement partially
reverses it. An eighty-year-old who has been talking for eleven minutes does
not become fresh again because one sentence came out brightly.

Here is what that state does to the agent's behaviour. The reading was both
fading *and* withdrawing, and `policy` is ordered: withdrawal is read as being
about a subject before tiredness is read as being about the call, so what comes
back is "move to something lighter", not "start closing".

Watch the second half of the output too. The tools were closed over this call's
memory back in section 4, and the notebook never hands them the new reading, so
the guidance riding on that tool response is still the opening one. In
production that hand-off is a single line — `memory.affect = state`, in
`_publish_affect` (`app.py`) — run every time the monitor reports.
""")

code("""
knobs = policy(state)
print("turn_length:", knobs.turn_length)
print("guidance   :", knobs.guidance)

print()
print("...and this is what rides back on the next tool response:")
print(json.dumps(tools["remember"]("shop"), indent=2, ensure_ascii=False)[:400])
""")

md("""
**The honest weakness:** the push channel is parasitic on the pull channel. If
the agent never calls a tool — which is the *ideal* call, where she talks
steadily for eleven minutes and it just listens — the affect monitor's
conclusions reach nothing but the family-facing overlay.
`enable_affective_dialog` covers some of this natively in-turn, but inside one
call the coupling is real and unsolved.

Worse, it does not survive the call either. `finish_call` never reads
`prepared.memory.affect`, so nothing the monitor concluded is written down. All
the *next* opener inherits about how this call went is the closure reason, and
the Archivist reads that off the transcript rather than off the audio.
""")

# ── 6 ────────────────────────────────────────────────────────────────────────
md("""
## 6. Stage 4 — recording stops

`finish_call()` is where the knowledge base actually changes. Take a real seed
transcript as the call that just happened:
""")

code("""
from sampan.callflow import MIN_TURNS_TO_EXTRACT, Transcript

raw_transcript = (ROOT / "seeds" / "session-01.txt").read_text(encoding="utf-8")

transcript = Transcript()
for line in raw_transcript.splitlines():
    if line.startswith("K:"):
        transcript.add("user", line[2:])
    elif line.startswith("A:"):
        transcript.add("agent", line[2:])

print(len(transcript), "turns | extraction threshold:", MIN_TURNS_TO_EXTRACT)
print(transcript.render()[:400])
""")

md("""
`Transcript.add` collapses consecutive turns from the same speaker, because the
Live API streams transcription incrementally and those fragments are revisions,
not new turns.

Below `MIN_TURNS_TO_EXTRACT` the call is treated as a misdial: nothing is
extracted, **and the family's question is not consumed**. That ordering was a
real bug — a four-turn test call marked Wei Lun's question delivered forever,
so he was told she had been asked and she was never asked again.

Now run the real Archivist. This is seam 1: text in, everything derived out —
no audio, no streaming, no browser, which is what makes the whole spine
testable offline.
""")

code("""
from sampan.archivist import GeminiStoryExtractor
from sampan.callflow import finish_call

if not settings.configured:
    raise RuntimeError("Set GOOGLE_CLOUD_PROJECT in .env to run the extraction step.")

extractor = GeminiStoryExtractor(settings)

updated = finish_call(
    repo,
    extractor,
    prepared,
    transcript,
    narrator_id=NARRATOR,
)
print("session_count:", updated.session_count)
print("closure      :", updated.last_closure.value)
""")

md("""
`ClosureReason` is the distinction the opener depends on: a call that ended
because a neighbour rang the doorbell is *interrupted*; one that ended because
she tired is *fatigue*. The first earns *"you still owe me the rest"* next
time; the second earns *"did you sleep well?"*.

### What `ingest_conversation` computes — including what gets thrown away

`finish_call` wraps `ingest_conversation`. Calling it directly exposes the
`resolutions` that section 1 claimed exist and are then discarded:
""")

code("""
from sampan.archivist import ingest_conversation

outcome = ingest_conversation(
    transcript.render(),
    extractor,
    known_entities=intake,
    conversation_id="conv_demo",
)

print("stories   :", len(outcome.stories), "|", len(outcome.pinned), "pinnable")
print("entities  :", len(outcome.entities), "|", len(outcome.new_entities), "new")
print("threads   :", len(outcome.threads))
print("anchors   :", len(outcome.anchors))
print("preferences:", len(outcome.preferences))
print()
print("RESOLUTIONS — the story->entity edges, computed here and never persisted:")
for r in outcome.resolutions[:8]:
    print(f'  "{r.mention.surface_form}" -> {r.entity_id:20} via {r.matched_by}'
          f'{"  (new)" if r.created else ""}')
""")

md("""
### An aside you can see in the numbers above

That cell just ran extraction a **second** time on the same transcript, and it
will usually disagree with the run inside `finish_call` — a different story
count, a slightly different entity count. Same input, same temperature, same
prompt.

The model is nondeterministic about **where one memory ends and the next
begins**: whether the river and the line house are one childhood story or two
is a judgement call, and it makes it differently on different runs. Every story
still scores 5 or 6 with a place and a time; the boundaries move, not the
quality.

This is why the integration suite asserts *properties* — enough pins, three or
more distinct places, at least fifteen years spanned — instead of counts. A
threshold like `pinned >= 9` sat inside that spread and failed for no reason
anyone could act on.

### Back to the resolutions

Those `entity_id` values are exactly the missing foreign key. `save_stories`
writes the story with `PersonMention.surface_form` and no id; `save_entities`
writes the entities. Nothing writes the middle column. Every ingest recomputes
these edges and drops them.

Persisting them would be a small change — write the resolved id onto the
mention at ingest, from data already computed — and it is the single thing I
would fix first if this ran past the hackathon.

### The scored stories
""")

code("""
for s in outcome.stories:
    c = s.candidate
    missing = ",".join(s.missing_fields) or "-"
    print(f"[{s.status.value:8}] {s.score}/6  {c.title[:44]:44} missing={missing}")
    print(f"           when: {c.when.raw_phrase!r} -> {c.when.start_year}"
          f"  where: {c.where.raw_name!r}")
    print(f"           sense: {c.sense_detail[:70]!r}")
    print()
""")

md("""
`when.raw_phrase` beside `when.start_year` is the two-field design paying off
on real speech — her vague phrase preserved, a sortable year derived from it.

`sense_detail` is the field the letters are built around, and the one that
taught the hardest lesson: asked for "a concrete sensory detail" it filled
every time, which looked like success until the values were read. It was
returning paraphrases of the story. The fix was to demand **quotability** —
something she said, pointable to a line in the transcript — plus explicit
permission to leave it empty.
""")

# ── 7 ────────────────────────────────────────────────────────────────────────
md("""
## 7. Stage 5 — the diff

What the call actually changed in the knowledge base:
""")

code("""
memory_after = repo.load_memory(NARRATOR)
entities_after = repo.load_entities(NARRATOR)
stories_after = store.list(f"stories__{NARRATOR}")

rows = [
    ("entities", len(intake), len(entities_after)),
    ("stories", 0, len(stories_after)),
    ("threads", len(memory_before.threads), len(memory_after.threads)),
    ("anchors", len(memory_before.anchors), len(memory_after.anchors)),
    ("preferences", len(memory_before.preferences), len(memory_after.preferences)),
    ("sensitivities", len(memory_before.sensitivities),
     len(memory_after.sensitivities)),
    ("session_count", memory_before.session_count, memory_after.session_count),
]
print(f"{'':16}{'before':>8}{'after':>8}")
for name, before, after in rows:
    mark = "  <-" if after != before else ""
    print(f"{name:16}{before:>8}{after:>8}{mark}")
""")

code("""
print("NEW ENTITIES — provisional until the family confirms them:")
known_ids = {e.entity_id for e in intake}
for e in entities_after:
    if e.entity_id not in known_ids:
        print(f"  {e.canonical_name:26} {e.type.value:8}"
              f" provisional={e.provisional}")

print()
print("ANCHORS — dates that sharpen every relative phrase said afterwards:")
for a in memory_after.anchors:
    print(f"  {a.anchor_id:26} {a.year}  {a.label}")

print()
print("PREFERENCES — one value per kind; this is why session 20 differs:")
for p in memory_after.preferences:
    print(f"  {p.type.value:18} {p.value}")
""")

md("""
The row that looks alarming is `sensitivities`, nothing to five after a single
call. It is not a blocklist. `SensitiveTopic` is the ledger of how she answered
each subject that came up, and only one she refused once — or deflected twice —
and never engaged with becomes `do_not_raise`.

Nothing here was hand-written into the store. Every row came out of the
pipeline, which is the whole reason the seed sessions are run through the real
Archivist rather than stuffed into Firestore directly: if the pipeline cannot
produce this state, the pipeline is what needs fixing.

### The loop closes

Run `prepare_call` again and the *next* call's plan is different, because the
archive is:
""")

code("""
next_call = prepare_call(repo, settings, narrator_id=NARRATOR)
next_plan = build_session_plan(
    threads=memory_after.threads,
    sensitivities=memory_after.sensitivities,
    ask=repo.pending_ask(NARRATOR),
    session_count=memory_after.session_count,
    last_closure=memory_after.last_closure,
)
print("greeting now:", next_plan.greeting)
print("offers now  :", [(o.kind.value, o.label) for o in next_plan.offers])
for offer in next_plan.offers:
    print("   would say:", offer.say)
""")

md("""
Extraction feeds the opener; the opener produces conversation; conversation
feeds extraction. That loop is the engine, and it is why *"session 20 has a
sharper timeline than session 3"* is a mechanism rather than a claim.
""")

# ── 8 ────────────────────────────────────────────────────────────────────────
md("""
## 8. The memory graph

Everything above was the original spine. What follows is the layer built on top
of it, after **Zep** (*A Temporal Knowledge Graph Architecture for Agent
Memory*, arXiv 2501.13956) — with the departures argued rather than assumed,
because an oral history is not the enterprise dataset that paper targets.

Section 1 said this was an entity *index* and not a graph. That is what changed:
the graph now has edges, and they are **facts**.
""")

code("""
from sampan.facts import Fact, Predicate

print("A fact carries both timelines and the sentence behind it:")
for name in Fact.model_fields:
    print("   ", name)

print()
print("Relations are a closed vocabulary:", ", ".join(p.value for p in Predicate))
""")

md("""
Three departures from the paper, each visible in those fields.

**`Predicate` is a closed enum.** These are join keys. We already paid for
letting a model name them: one refusal came back as *"the reason the shop
closed"* in session 2 and *"grandfather's shop shutting"* in session 4, no
string match reconciles them, and the subject stayed marked `do_not_raise`
through the session meant to reopen it. The paper makes the same argument about
its own writes, preferring predefined Cypher to LLM-generated queries.

**`valid_from` / `valid_to` are `When`, not `datetime`.** She says *"before I
married"*. A timestamp forces a date she never gave. Published agent-memory
systems store valid-time edges but not *uncertain* valid-time intervals, and
sixty-year-old recollection is nothing else.

**`quote` is required and verified.** Fourth time this check has been needed.
""")

code("""
from sampan.fact_extraction import ExtractedFact, build_facts

TRANSCRIPT = (
    "K: Later he saved a bit of money, nineteen fifty-eight he opened a coffee "
    "shop in Ipoh, at Jalan Bandar. Sixty-nine the shop closed."
)

honest = ExtractedFact(
    subject_id=intake[0].entity_id,
    predicate=Predicate.OWNED,
    object_literal="a coffee shop at Jalan Bandar",
    statement="her father ran a coffee shop at Jalan Bandar",
    quote="nineteen fifty-eight he opened a coffee shop in Ipoh, at Jalan Bandar",
)
invented = honest.model_copy(
    update={"quote": "The father is identified as a coffee shop proprietor."}
)

kept = build_facts(
    [honest, invented],
    transcript=TRANSCRIPT,
    known_entities=intake,
    episode_id="conv_demo",
)
print(f"proposed 2 -> kept {len(kept)}")
for f in kept:
    print("   ", f.render())
    print("     because she said:", f.quote)
""")

md("""
The second was dropped silently. It reads like a citation and is the model's own
reasoning — the exact failure that produced `sense_detail` paraphrases, a
`flag_concern` that notified nobody, and place links justified by *"Identified
as being in the vicinity of Sungai Siput"*. **A claim about a source can be
tested against the source**, so it is.
""")

# ── 9 ────────────────────────────────────────────────────────────────────────
md("""
## 9. Retrieval — seam 4

Zep retrieves per turn: search, rerank, inject into the prompt. **The Live API
cannot do that** — the instruction is fixed at connect and all three injection
routes failed. So retrieval is *agent-initiated*: one `remember` tool the model
calls when the conversation needs it.

Ranking is a pure function over a fixture graph, with no model call anywhere. A
reranker that returns the wrong five facts throws nothing and fails nothing; the
agent simply sounds confidently wrong to an eighty-year-old.
""")

code("""
from sampan.facts import Fact
from sampan.retrieval import FactGraph, search_facts


def demo_fact(fact_id, subject, statement, obj=None, episode="conv_001"):
    return Fact(
        fact_id=fact_id, subject_id=subject, predicate=Predicate.WORKED_AT,
        object_id=obj, object_literal="" if obj else "somewhere",
        statement=statement, episode_id=episode,
        quote="a sentence long enough to satisfy the quote check comfortably",
        confidence=0.8,
    )


FACTS = [
    demo_fact("f_shop", "ent_father",
              "her father ran a coffee shop at Jalan Bandar", "ent_shop"),
    demo_fact("f_mother", "ent_mother",
              "her mother cooked at the back of the coffee shop", "ent_shop"),
    demo_fact("f_toast", "ent_father",
              "her father toasted bread over a charcoal fire"),
]
graph = FactGraph(facts=FACTS)

cold = search_facts("coffee", graph, limit=2)
seeded = search_facts("coffee", graph, seeds=["ent_mother"], limit=2)
print("cold  :", [f.fact_id for f in cold])
print("seeded:", [f.fact_id for f in seeded])
""")

md("""
The same query, answered differently. BM25 alone prefers the father's shop — the
shorter sentence — but seed the traversal on the mother, as it would be if she
had just been talking about her, and the mother's fact comes first.

**That is what makes agent-initiated retrieval feel contextual.** The seeds are
the entity asked about *plus* everyone already named in this call, so nothing has
to be injected per turn for the conversation's history to steer the answer.

Following Zep §3, with two deliberate omissions:

| | |
|---|---|
| φ_bm25 over `statement` | the search field for an edge is its fact text, not the entity name |
| φ_bfs from seeds | Zep: *"can accept nodes as parameters… recent episodes as seeds"* |
| φ_cos | a **slot**, not an implementation — nothing measurable to gain at this size |
| RRF | fuses rank *positions*; BM25 scores and hop counts share no scale |
| node distance, episode mentions | closeness to the conversation, and how often the archive has heard it |
| ~~MMR~~ | diversity matters at five hundred results, not five |
| ~~cross-encoder~~ | an extra LLM call inside a live voice turn |

Note what is **not** here: no recency decay, no importance score. Zep is IR, not
the Generative Agents formula — several retrievers for recall, then rerankers for
precision.

And the bug this found within hours of being written:
""")

code("""
print('remember("Ah Seng") ->', search_facts("Ah Seng", graph))
""")

md("""
Empty, correctly. It did not used to be: `Ah Seng` matched a fact about `Ah
Chwee` on the shared honorific `ah`, two characters half the family carries.
BM25's IDF is supposed to discount exactly that and across a few dozen sentences
has no room to. Query terms under three characters are now dropped.

The worst class of bug in this product: nothing throws, and the agent tells her
something confident and wrong about a person she asked after.
""")

# ── 10 ───────────────────────────────────────────────────────────────────────
md("""
## 10. Contradiction — the departure that matters

She will say the shop closed in 1969, and later say 1970.

Zep sets the old edge's `t_invalid` to the new edge's `t_valid` and prioritises
new information. Applied literally here that yields *"her father ran a coffee
shop, and that stopped being true in 1970"* — a claim she never made. **The shop
closed once.**

Two different things wear the same shape, and only one is what that rule is for:
""")

code("""
from sampan.contradiction import apply_conflicting_testimony, apply_state_change
from sampan.models import Precision


def when(v):
    return When(
        raw_phrase=str(v), start_year=v, precision=Precision.YEAR, confidence=0.9
    )


def shop(fid, statement, vf, vt):
    return Fact(
        fact_id=fid, subject_id="ent_father", predicate=Predicate.OWNED,
        object_literal="a coffee shop", statement=statement,
        valid_from=vf, valid_to=vt, episode_id="c1",
        quote="a sentence long enough to satisfy the quote check comfortably",
    )


held = shop("f_old", "the shop closed in 1969", when(1958), when(1969))
newer = shop("f_new", "the shop closed in 1970", when(1958), when(1970))

testimony = apply_conflicting_testimony(held, newer)
print("CONFLICTING TESTIMONY — her account moved")
print("   still asserted :", testimony.is_current)
print("   valid_to       :", testimony.valid_to.start_year, "  <- untouched")
print("   superseded_by  :", testimony.superseded_by)

# A different pair: she lived above the shop, then her son moved her to a flat.
lived = shop("f_lived", "she lived above the shop", when(1969), None)
flat = shop("f_flat", "she lived in a flat in Ipoh", when(2016), None)
moved = apply_state_change(lived, flat)

print()
print("STATE CHANGE — the world moved")
print("   still asserted :", moved.is_current)
print("   valid_to       :", moved.valid_to.start_year, "  <- where the new one opens")
""")

md("""
Both axes are already in the paper. The mistake would be collapsing onto one.

| | What moved | Axis |
|---|---|---|
| *"she moved house in 2016"* | the world | `valid_to` (T) — Zep as written |
| *"closed in 1969"* → *"1970"* | her account | `t_expired` (T′), valid time untouched |

An enterprise dataset is almost entirely the first. An oral history is almost
entirely the second: sixty years on she is not reporting state transitions, she
is recalling one fixed past with varying accuracy.

Three rules hold either way. **Nothing is ever deleted** — she said it, and that
stays true about her. **Newest wins for display.** And **a contradiction becomes
a question, not a decision**: it reaches the next call the way a missing field
does, because which telling is right is hers to settle.

The family cannot edit a fact. They *can* correct the geocoder that put Sungai
Siput ninety kilometres away — that is our error, not her memory.
""")

# ── 11 ───────────────────────────────────────────────────────────────────────
md("""
## 11. Communities — her chapters

The third tier. Entities that keep appearing together get clustered, and the
cluster is named from the facts joining them.

Zep uses **label propagation rather than Leiden**, chosen for "straightforward
dynamic extension". Both halves exist here: `extend` places one new entity by
plurality of its neighbours, and `detect` runs full propagation for the periodic
refresh the paper says remains necessary.
""")

code("""
from sampan.communities import detect, hub_entities
from sampan.models import EntityType

names = [
    ("father", "Lim Ah Hock"), ("shop", "Jalan Bandar"),
    ("husband", "Tan Eng Huat"), ("mother", "Tan Ah Tai"),
    ("estate", "Sungai Siput"), ("chwee", "Ah Chwee"), ("her", "Ah Khim"),
]
people = [
    Entity(entity_id=i, type=EntityType.PERSON, canonical_name=n, provisional=False)
    for i, n in names
]
links = [
    demo_fact("a", "father", "x", "shop"),
    demo_fact("b", "husband", "x", "shop"),
    demo_fact("c", "mother", "x", "estate"),
    demo_fact("d", "chwee", "x", "estate"),
]
# She is the subject of a fact about nearly everyone, as the real archive has.
others = ["shop", "estate", "father", "mother", "husband", "chwee"]
hub = [demo_fact(f"h{i}", "her", "x", o) for i, o in enumerate(others)]
everything = links + hub
found = hub_entities(people, everything)

print("with her   :", detect(people, everything))
print("hub found  :", found)
print("without her:", detect(people, everything, exclude=found))
""")

md("""
**The narrator wrecks her own clustering.** Nearly every fact in her archive is
about her life, so she neighbours everyone, and label propagation collapses her
estate childhood and her shop years into one chapter because she is the only
thing they share. She belongs to every chapter, which is exactly why she cannot
be used to tell them apart.

Two wrong fixes came first, and both are the finding:

- **By name.** The narrator entity is `Ah Khim`; the household record says `Lim
  Siew Khim`; the profile's `display_name` was empty. The exclusion set was
  empty, the code ran, chapters came out, and nothing said the filter had
  matched nothing.
- **By threshold.** "More than half the graph" also excluded nobody — 28
  entities exist but only 17 appear in any fact. "At least half" would have
  thrown out the coffee shop, which is a chapter and not a hub.
- **By dominance.** She has degree 8; the next entity has 3. An outlier, not a
  busy node. And the script now prints who it removed, because the previous two
  failures were both silent.

On her real archive this produces three chapters — the shop years, the estate
childhood, the grandfather's arrival — each opening down to her own sentences in
the app.
""")


# ── 12 ───────────────────────────────────────────────────────────────────────
md("""
## 12. Summary

| Component | Where | What it does |
|---|---|---|
| Domain model | `models.py` | Typed schema; `When`/`Where` keep her words beside the interpretation |
| Rubric | `models.assess` | Six fields, threshold four; `missing_fields` becomes the next question |
| Pre-set KB | `seeds/intake.json` | Child-completed family intake; stops painful questions |
| Call setup | `callflow.prepare_call` | Loads memory, builds the plan, closes tools over it |
| Session plan | `opener.build_session_plan` | Ranked, sensitivity-gated, depth-gated, max two offers |
| Instruction | `companion.build_instruction` | Three layers, sent **once** at connect |
| Facts | `facts.py` | Bi-temporal edges; `When` valid time, required verified quote |
| Extraction | `fact_extraction.py` | Second pass, own schema |
| Retrieval | `retrieval.search_facts` | Seam 4 — BM25 + BFS + RRF + rerankers, pure |
| Contradiction | `contradiction.py` | Routed to the right time axis; nothing deleted |
| Communities | `communities.py` | Label propagation; her chapters |
| Pull channel | `tools.remember` | One tool where there were three |
| Push channel | `tools._with_guidance` | Affect policy rides on every tool response |
| Affect | `affect.apply_assessment` | Two agreeing readings to move; distress acts immediately |
| Archivist | `archivist.ingest_conversation` | Seam 1 — text in, structured memory out |
| Persistence | `repository.py` | Entities, stories, threads, anchors, preferences, sensitivities |

### The four seams

`ingest_conversation`, `build_session_plan`, `apply_assessment` and
`search_facts` are pure functions with the model calls behind protocols. That is
why 382 tests run in under a second without touching a network.

### What I would change

Sections 8–11 did two of the three things this notebook originally listed as
future work: **join keys** are now a closed `Predicate` enum, and
**contradiction** is a modelled state rather than a last-write-wins accident.

What is still true:

1. **Persist the resolutions.** The story→entity edge is still computed every
   ingest and discarded. Facts have their own subject and object ids, so the
   graph works — but a *story* still names people as raw strings.
2. **φ_cos is a slot, not an implementation.** Retrieval is lexical and
   structural. Fine at this size, and the third leg of Zep's search is missing.
3. **Recency is not reliability.** Zep's "prioritise new information" is a
   database instinct; with a narrator of eighty the later telling may be the
   less accurate one. Followed anyway, because the alternatives need evidence we
   do not have — and `superseded_by` keeps the decision reversible.
4. **Carry affect past the hang-up.** The monitor's state is read on the
   overlay and on tool responses and is then dropped; `finish_call` could fold
   it into preferences the way the Archivist already infers them.
""")

nb = {
    "cells": cells,
    "metadata": {
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3",
        },
        "language_info": {"name": "python", "version": "3.12"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

out = pathlib.Path("notebooks/knowledge_base_flow.ipynb")
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(nb, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"wrote {out} — {len(cells)} cells")
