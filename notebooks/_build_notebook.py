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
has not raised, and it steers. The archive stays behind the `recall` tool so
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

`build_tools(memory)` closes nine tools over a `CallMemory`. The notebook calls
them directly; in production the model calls exactly these.
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

### `recall` — the closest thing here to retrieval
""")

code("""
found = tools["recall"]("Ah Hock")
print(json.dumps(found, indent=2, ensure_ascii=False))
""")

md("""
`recall` returns **two** things: `found` (substring hits over the entity index)
and `she_said` (a search of her actual transcripts — empty here, since this
in-memory archive has no conversations in it yet).

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
print(json.dumps(tools["get_open_threads"](), indent=2, ensure_ascii=False)[:400])
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
## 8. Summary

| Component | Where | What it does |
|---|---|---|
| Domain model | `models.py` | Typed schema; `When`/`Where` keep her words beside the interpretation |
| Rubric | `models.assess` | Six fields, threshold four; `missing_fields` becomes the next question |
| Pre-set KB | `seeds/intake.json` | Child-completed family intake; stops painful questions |
| Call setup | `callflow.prepare_call` | Loads memory, builds the plan, closes tools over it |
| Session plan | `opener.build_session_plan` | Ranked, sensitivity-gated, depth-gated, max two offers |
| Instruction | `companion.build_instruction` | Three layers, sent **once** at connect |
| Pull channel | `tools.recall` | Entity index as lookup key; returns her actual words |
| Push channel | `tools._with_guidance` | Affect policy rides on every tool response |
| Affect | `affect.apply_assessment` | Two agreeing readings to move; distress acts immediately |
| Archivist | `archivist.ingest_conversation` | Seam 1 — text in, structured memory out |
| Persistence | `repository.py` | Entities, stories, threads, anchors, preferences, sensitivities |

### The three seams

`ingest_conversation`, `build_session_plan`, and `apply_assessment` are pure
functions with the model calls behind protocols. That is why 297 tests run in
under a second without touching a network.

### What I would change

1. **Persist the resolutions.** The story→entity edge is computed every ingest
   and discarded. Cheapest high-value fix.
2. **Stop letting the model own join keys.** Topic labels, entity names and
   place names are strings a nondeterministic model produces. It already bit:
   one refusal came back as *"the reason the shop closed"* in session 2 and
   *"grandfather's shop shutting"* in session 4, so an engagement landed on a
   different topic and the subject stayed marked do-not-raise.
3. **Model contradiction.** If she contradicts herself in session 9 there is no
   principled merge. In an oral history, contradiction is interesting — it
   should be a state, not a last-write-wins accident.
4. **Carry affect past the hang-up.** The monitor's state is read on the
   overlay and on tool responses and is then dropped; `finish_call` could fold
   it into preferences the way `note_preference` observations already are.
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
