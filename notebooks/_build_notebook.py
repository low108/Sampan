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
knowledge base is swapped for an in-memory store, so the notebook is safe to
re-run and never touches the real Firestore archive.

Run it with `uv run python notebooks/run_notebook.py`, which clears every output
before executing. That matters more than it sounds: a run that fails partway
leaves earlier cells showing results from an older version of the code, and the
page then answers the same question two different ways with nothing marking
either as out of date. It happened here — section 4 printed nine tools while
section 5 printed five, from the same object.
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
## 1. What this knowledge base is, and what it is not

Most memory systems for AI agents store text and search it by meaning. You turn
every passage into a vector, and at query time you find the ones closest to the
question.

That approach does not fit here. Look at the kinds of question this product has
to answer:

- *Which subject did she leave unfinished, and did she stop because a neighbour
  rang the doorbell, or because she got tired?*
- *Which stories have a place but no year?*
- *What has she never said?*

None of those are questions about meaning. Take the first one. "She was
interrupted" and "she got tired" look nearly identical as text, but the agent
has to do opposite things with them:

| How the last call ended | What the agent says next time |
|---|---|
| interrupted | *"You still owe me the rest."* |
| tired | *"Did you sleep well after we talked?"* |

Similarity search cannot tell those apart. The difference has to be **recorded
as a field**, decided at the moment the call is filed away.

So this store is a set of typed records, not a searchable pile of text.
""")

code("""
from sampan.models import Entity, PersonMention

print("Entity fields:       ", list(Entity.model_fields))
print("PersonMention fields:", list(PersonMention.model_fields))
""")

md("""
### Right now it is an index, not a graph

Worth being precise, because "knowledge base" suggests more structure than there
actually is at this point.

`PersonMention` is how a story records who was in it, and it carries **no entity
id**. A story stores `"my sister"` as plain text. Nothing links that story to the
sister's record.

The links do get worked out. When a call is filed, `resolve_mentions()` matches
each mention to an entity and returns `Resolution(mention, entity_id,
matched_by)`. Those are used to build the family's confirmation screen — and
then discarded. `finish_call` saves entities and saves stories, and never saves
the resolutions. Section 6 shows them being computed and dropped.

Sections 8 to 11 are where this gets fixed, by adding **facts**: real edges that
carry ids on both ends. Read the next few sections as the original design, and
section 8 onward as what it grew into.
""")

# ── 2 ────────────────────────────────────────────────────────────────────────
md("""
## 2. The schema

Every type below is a Pydantic model, so the shape is enforced in code and
anything the model returns has to fit it.

The single most important idea in the design shows up in `When`, the type used
for time.
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
**Keep two things: what she said, and what you worked out from it.**

She says *"six, seven maybe"*. Eleven turns later she says *"I was born nineteen
forty-six."* The model puts those together and writes `start_year = 1952`. But
`raw_phrase` still holds *"six, seven maybe"*, word for word.

Both are kept, side by side. The same pattern repeats everywhere:

| What she said | What was worked out from it | Held in |
|---|---|---|
| *"before I married"* | `start_year`, plus a link to her wedding | `When` |
| *"my father's shop"* | a position on the map | `Where` → `Place` |
| *"my sister"* | `Lim Siew Choo` | `PersonMention` → `Entity` |

Three things follow from that one decision:

1. **Her voice survives.** The letters written for her grandchildren quote her,
   not a tidied-up version.
2. **The map and timeline can sort things.** They need years, and now they have
   them.
3. **Every conclusion can be checked and corrected**, because the original sits
   right next to it. That is why fixing a wrong place happens inside the story
   card, and not on a settings screen somewhere.

### The completeness score is computed in Python, not asked of the model
""")

code("""
from sampan.models import assess

print(assess.__doc__)
""")

md("""
Six fields are checked: where, when, who, what, a sensory detail, and why it
mattered. Four out of six is enough to put a story on the map. Place and time
are required no matter what the total is.

The scoring is done in code rather than in the prompt, for a simple reason: a
model asked to grade its own work drifts, and this threshold is a product
decision rather than a judgement call.

Here is the part that matters most. `missing_fields` is filled in **even for
stories that passed**. A story can reach the map and still carry a note saying
it never explained why it mattered. That note becomes a question on the next
call:

> *"That coffee shop — was it before you married, or after?"*

Gaps are not errors to be logged somewhere. **They are the list of things to ask
her about.**
""")

# ── 3 ────────────────────────────────────────────────────────────────────────
md("""
## 3. Stage 1 — what the archive knows before it starts

One thing is filled in before the agent ever calls, and it is filled in by her
**child**, not by her: a short form naming the family.

It exists to prevent a specific cruelty. Without it, the agent would cheerfully
ask how her sister is doing. Her sister died in 2019.
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
Every one of those is marked `provisional=False, confirmed_by_family=True`. The
family stated them, so the agent can treat them as settled.

Anything the agent works out later arrives as `provisional=True` and waits for
someone to confirm it. The archive keeps track of the difference between what it
was told and what it guessed.

Now add the thing this whole product is built around — a question from her son:
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
## 4. Stage 2 — the call starts

This is where the design departs most sharply from an ordinary AI agent.

A normal agent works in turns. You send the conversation so far, plus anything
you looked up, and you get a reply. Every turn is a fresh chance to add context.

**The Live API does not work like that.** It holds one open connection for the
whole call. The system instruction is sent **once**, at the moment the call
connects, and cannot be changed afterwards. The model keeps the conversation in
its own memory, on the server.

So the question is not *"what do I look up each turn?"*. It is: **what do I
decide before she has said a word, and how can anything reach the model after
that?**

`prepare_call()` makes those decisions.
""")

code("""
from sampan.callflow import prepare_call

prepared = prepare_call(repo, settings, narrator_id=NARRATOR)

print("conversation_id:", prepared.conversation_id)
print("tools exposed:  ", [t.__name__ for t in prepared.agent.tools])
""")

md("""
Notice that the `conversation_id` ends in random characters, not just a
timestamp.

Live sessions drop after roughly fifteen minutes. If she redials straight away,
the second call can begin in the same *second* the first one ended. With
timestamps alone, the second call's stories would overwrite the first call's,
and nothing would say so.

Next, the instruction that actually goes to the model. It is built in three
layers, stacked rather than blended together, so you can see at a glance what
changed between her first call and her twentieth.
""")

code("""
print(prepared.agent.instruction)
""")

md("""
Read what is in there. Then notice what is missing.

**In it:** who the agent is and the rules it follows; what has been learned
about talking to her; and the plan for this particular call.

**Not in it:** her stories. Her people and places. The transcripts. **None of the
archive is loaded up front.**

That is not about saving space. It is about behaviour. An agent holding nine of
her stories in its context *behaves* as though it holds nine stories — it brings
up things she has not mentioned, and it starts steering. So the archive stays
behind a tool, and the agent reaches for it only when the conversation actually
calls for it.

### The plan is a short list, not everything the archive knows
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
Four rules shape that plan:

- **At most two things to offer her.** She is eighty and this is a voice call. A
  list of four options is not choice, it is work. Everything else that scored is
  kept in `considered` for the family's screen, and never shown to the model.
- **Anything she has refused is removed completely.** Not ranked lower — it never
  enters the scoring at all. Her late sister appears nowhere in the context.
- **Deeper subjects unlock slowly**, through `unlocked_depth(session_count)`.
  Hardship is not a first-conversation subject.
- **The greeting is chosen in Python.** The persona is fixed text and cannot
  work out "is this our first meeting?". That shipped broken once: the agent
  introduced itself from scratch on her fifth call, with her whole history
  loaded.
""")

# ── 5 ────────────────────────────────────────────────────────────────────────
md("""
## 5. Stage 3 — during the call

Once the connection is open, exactly two things can reach the model. There are
no others.

### Channel one: the agent asks for something

`build_tools(memory)` gives the agent five tools — down from nine. `recall`,
`get_open_threads` and `what_do_you_remember` became a single `remember` call.
`note_preference` and `save_fragment` were removed entirely, because the
Archivist works both out from the transcript afterwards, and does it better than
an agent noticing things mid-conversation while trying to listen to her.

The notebook calls these directly. In a real call the model calls exactly the
same functions.
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
Two things happened there.

`ask_delivered` is now set on this call's memory. The agent has taken
responsibility for reading his question out loud. Section 6 covers when that is
allowed to actually use the question up.

And the reply contains `_guidance` and `_turn_length`, which the agent never
asked for. That is the second channel, arriving as a passenger on the first one.

### `remember` — the closest thing here to looking something up
""")

code("""
found = tools["remember"]("Ah Hock")
print(json.dumps(found, indent=2, ensure_ascii=False))
""")

md("""
`remember` returns three things:

- **`known`** — facts, each with the sentence she said that put it there.
- **`she_said`** — a search of her actual transcripts. Empty here, because this
  in-memory archive has no conversations in it yet.
- **`unfinished`** — subjects she left open.

`known` is empty at this point because no facts exist yet; section 9 covers the
ranking that fills it.

The comment in `tools.py` explains why her transcripts are searched at all,
rather than only the tidy extracted records:

> *Extracted records lose sequence, context and affect, so the graph is only an
> index — her own words are the thing worth reaching.*

### Channel two: pushing information back on a tool's reply

The system instruction is fixed for the whole call, so there is no way to send
the model new directions partway through. I tried three, and all three failed in
front of a user:

| What I tried | What happened |
|---|---|
| a `user` message, fenced with "do not read aloud" | The agent read the fence out loud, brackets and all |
| a `system` message | The agent said *"Alright, understood. Preparing to wrap up"* out loud |
| a `model` message | Turn-taking broke and it stopped answering her |

A tool's reply is the one thing the model treats as data rather than as
something to say. So `_with_guidance` attaches the current behavioural settings
to **every** tool reply, whatever that tool was actually asked for.

Meanwhile a second model listens to the same audio and works out how she is
doing. Its readings feed a small state machine:
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
**Two readings in a row have to agree before anything changes.** One odd
five-second window cannot make the agent lurch. Distress and agitation are the
exceptions and take effect immediately, because those are not moods to wait out.

Energy also only moves one way: it can drop, and only excitement partly lifts it
again. Someone who has been talking for eleven minutes does not become fresh
because one sentence came out brightly.

Here is what that state actually does to the agent's behaviour:
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
**The honest weakness:** the push channel depends entirely on the pull channel.
If the agent never calls a tool — which is what the *best* calls look like, where
she talks for eleven minutes and it simply listens — then nothing the affect
monitor concludes reaches the model during that call.

`enable_affective_dialog` covers some of this natively, and affect still shapes
the *next* call's instruction. But within a single call the coupling is real,
and I have not solved it.
""")

# ── 6 ────────────────────────────────────────────────────────────────────────
md("""
## 6. Stage 4 — the call ends

`finish_call()` is where the archive actually changes. Take a real seed
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

rendered = transcript.render()
lines = rendered.splitlines()

print(len(transcript), "turns | extraction threshold:", MIN_TURNS_TO_EXTRACT)
print()

# The first six turns only. Cut by line rather than by character count, so
# nothing ends mid-word and looks as though the pipeline lost it.
for line in lines[:6]:
    print(line)
print()
print(f"... and {len(lines) - 6} more turns "
      f"({len(rendered)} characters in all)")
""")

md("""
`Transcript.add` merges consecutive turns from the same speaker. The Live API
sends transcription in pieces as it goes, so those pieces are revisions of one
turn rather than separate turns.

If the call is shorter than `MIN_TURNS_TO_EXTRACT`, it is treated as a misdial:
nothing is extracted, **and the family's question is not used up**. That ordering
was a real bug. A four-turn test call marked Wei Lun's question as delivered
forever, so he was told she had been asked, and she was never asked again.

Now the Archivist runs. This is the main seam of the system: text goes in,
everything else is worked out from it. No audio, no streaming, no browser —
which is what makes the whole pipeline testable offline.
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
`ClosureReason` is the distinction the next call depends on. A call that ended
because a neighbour rang the doorbell is *interrupted*. One that ended because
she got tired is *fatigue*. The first earns *"you still owe me the rest"* next
time; the second earns *"did you sleep well?"*.

### What the Archivist actually does

`finish_call` in the cell above did the real work by calling
`ingest_conversation`. That one function is the entire post-call pipeline: a
transcript goes in, structured memory comes out. Inside it, in order:

| Step | What it does |
|---|---|
| `extractor.extract()` | **The one model call.** Returns raw stories, the people and places she mentioned, subjects left unfinished, dates, and preferences |
| `resolve_mentions()` | Works out who each mention refers to. Creates a record for anyone new |
| `fold_anchors()`, `apply_anchors()` | Adds newly-learned dates, then uses them to turn *"before I married"* into a year |
| `assess()` | Scores each story against the six-field rubric from section 2 |
| `fold_threads()`, `fold_preferences()` | Merges with what was already known instead of replacing it |

The next cell calls `ingest_conversation` **a second time**, directly. That is
not how production works, and it is here for one reason: `finish_call` hands
back only the updated memory, so the `resolutions` — the links between a story
and the people in it — never come out of it. Calling the inner function is the
only way to see them.

Reading a resolution line:

```
"my father"  -> ent_father         via alias        she said "my father", and the
                                                    family intake lists that as
                                                    one of his names
"Ah Chwee"   -> ent_5f3a...        via new  (new)   nobody in the intake is Ah
                                                    Chwee, so a new record was
                                                    created for him
```

Those arrows are exactly the links section 1 said are missing. Watch what
happens to them.
""")

code("""
from sampan.archivist import ingest_conversation

# The same transcript, the same prompt, the same temperature -- run a second
# time. `finish_call` already ran one of these and saved the result, so the two
# can be compared directly.
outcome = ingest_conversation(
    transcript.render(),
    extractor,
    known_entities=intake,
    conversation_id="conv_demo",
)

filed = repo.load_memory(NARRATOR)
saved_entities = len(repo.load_entities(NARRATOR))

rows = [
    ("entities", saved_entities, len(outcome.entities)),
    ("threads", len(filed.threads), len(outcome.threads)),
    ("preferences", len(filed.preferences), len(outcome.preferences)),
    ("anchors", len(filed.anchors), len(outcome.anchors)),
]
print(f"{'':14}{'filed by':>12}{'this second':>14}")
print(f"{'':14}{'finish_call':>12}{'run':>14}")
for name, first, second in rows:
    flag = "   <- differs" if first != second else ""
    print(f"  {name:12}{first:>12}{second:>14}{flag}")

print()
print("  stories this run:", len(outcome.stories),
      "|", len(outcome.pinned), "of them pinnable")
for story in outcome.stories:
    print("     ", story.candidate.title)
print()
print("RESOLUTIONS — the story-to-entity links, worked out here and then thrown away:")
for r in outcome.resolutions[:8]:
    print(f'  "{r.mention.surface_form}" -> {r.entity_id:20} via {r.matched_by}'
          f'{"  (new)" if r.created else ""}')
""")

md("""
### The two runs do not agree, and that is the point

Look at the table above. The same transcript went through the same function
twice, with the same prompt and the same temperature setting — and the rows
marked `<- differs` came out with different numbers.

Which rows differ is itself not fixed. One run it is the entity count; another
run it is threads and preferences as well. Run the notebook again and the table
will very likely disagree in a different place.

Nothing is broken. **The model is making judgement calls, and it does not make
them the same way twice.**

Take one concrete example. In this conversation she mentions playing in the
river, and she mentions the line house she grew up in. Is that:

- one story — *"her childhood on the estate"* — or
- two stories — *"playing in the river"* and *"the line house"*?

Both readings are defensible. A human archivist would also hesitate. The model
picks one, and on the next run it might pick the other. The same thing happens
with entities: is *"the river"* a place worth its own record, or just a detail
inside a story? Is *"speak louder, my left ear is not good"* one preference
about hearing, or two about hearing and pace?

What does **not** vary is quality. Every story still scores 5 or 6 out of 6.
Every one still has a place and a time. The *boundaries* move; the content does
not.

### Why this changed how the tests are written

If the output count moves between runs, then a test like this is a coin flip:

```python
assert len(pinned_stories) >= 9      # fails for no reason anyone can act on
```

It did exactly that. It failed one afternoon, and passed unchanged an hour later
with no code in between. A failing test is supposed to tell you what to fix, and
this one could not, because nothing was wrong.

So the integration tests assert **properties** instead of counts:

| Instead of | Assert |
|---|---|
| "9 stories" | enough stories to fill a map |
| "exactly these entities" | no duplicate of anyone in the family intake |
| "12 preferences" | preferences never *decrease* between sessions |

Each of those is true regardless of where the model draws its boundaries, and
each still fails loudly if the pipeline genuinely breaks.
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
Those `entity_id` values are exactly the missing link. `save_stories` writes the
story with `"my sister"` as text and no id. `save_entities` writes the entities.
Nothing writes the column joining them. Every ingest works these out again and
drops them.

Section 8 is where this stops being true.

### The stories themselves
""")

# ── 7 ────────────────────────────────────────────────────────────────────────
md("""
`when.raw_phrase` sitting next to `when.start_year` is the two-field idea
working on real speech: her vague phrase kept, and a sortable year derived from
it.

`sense_detail` is the field the letters are built from, and it taught the
hardest lesson here. Asked for "a concrete sensory detail" the model filled it in
every single time, which looked like success until anyone read the values. It was
returning paraphrases of the story rather than anything she had actually
described.

The fix was to demand something **quotable** — a phrase she said, findable in the
transcript — and to say explicitly that leaving it empty was fine.
""")

# ── 7 ────────────────────────────────────────────────────────────────────────
md("""
## 7. Stage 5 — what actually changed

One call has now been filed. Here is the difference it made to the archive,
counted rather than described.
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
## 8. Adding a real graph

Everything up to here is the original design. What follows is the layer built on
top of it.

It follows **Zep**, a published architecture for agent memory (*A Temporal
Knowledge Graph Architecture for Agent Memory*, arXiv 2501.13956) — with three
deliberate departures, because Zep is built for business data and this is an
eighty-year-old's life story.

Section 1 said this was an index rather than a graph. That is what changes now.
The graph gets edges, and the edges are called **facts**.
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
A fact is one thing she asserted, with two separate timelines attached.

That "two timelines" idea is the core of Zep, and it is worth being clear about:

| Timeline | Fields | Answers |
|---|---|---|
| **valid time** | `valid_from`, `valid_to` | *When was this true in her life?* |
| **transaction time** | `t_created`, `t_expired` | *When did the archive believe it?* |

So "her father ran a coffee shop" was true from 1958 to 1969 (valid time), and
the archive has believed that since the 15th of July (transaction time). Keeping
them apart is what makes section 10 possible.

Three things here differ from the paper:

**1. Relations come from a fixed list.** Zep lets the model invent relation
names. We already paid for that: a subject she refused came back labelled *"the
reason the shop closed"* in one session and *"grandfather's shop shutting"* in
another. No string matching connects those two, so the archive thought they were
different subjects. Now the model picks from a closed set and cannot invent one.

**2. Times are `When`, not timestamps.** She says *"before I married"*. A
timestamp would force a date she never gave. `When` keeps her phrase alongside
whatever year could be worked out. Published memory systems store valid time as
exact dates; none of them store *uncertain* ranges, and sixty-year-old
recollection is nothing but uncertain ranges.

**3. Every fact must quote her.** The sentence she said is a required field, and
it is checked against the transcript.
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
One was kept and one was dropped, silently.

The dropped one's "quote" is the model's own reasoning dressed up as a citation.
This is the fourth time the same thing has happened in this project: asked for
evidence, a model produces something evidence-*shaped*. It happened with sensory
details, with a safety tool that reported notifying the family and notified
nobody, and with place links justified by *"Identified as being in the vicinity
of Sungai Siput"*.

The fix is always the same and always cheap: **a claim about a source can be
checked against the source.** So it is.
""")

# ── 9 ────────────────────────────────────────────────────────────────────────
md("""
## 9. Looking things up during a call

Zep looks things up on every turn: search, rank, and paste the results into that
turn's prompt.

**The Live API cannot do that**, for the reason section 4 explained — the
instruction is fixed once the call connects. So looking things up has to be
started by the *agent*, through one tool it calls when the conversation needs it.

The ranking itself is a plain function with no model call anywhere in it. That
matters here more than elsewhere: if the ranking returns the wrong five facts,
nothing crashes and no test fails. The agent simply says something confident and
wrong to an eighty-year-old.
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
The same query, answered two different ways.

Word matching alone prefers the father's shop, because it is the shorter
sentence. But if the conversation has just been about her mother, the search
starts from the mother's record and walks outward through the graph — and the
mother's fact comes first instead.

**This is what makes agent-started lookup feel like it is paying attention.** The
starting points are whatever the agent asked about, *plus* everyone already
mentioned in this call. Nothing has to be injected per turn for the conversation
so far to shape the answer.

Three searches run, and the results are combined:

| Search | What it finds |
|---|---|
| **word matching** (BM25) | facts whose text shares rare words with the query |
| **graph walking** | facts one or two steps from where the conversation already is |
| **meaning matching** | *not implemented* — a slot, since it adds nothing measurable at this size |

Combining them uses **rank fusion**: each search produces an ordered list, and a
fact scores well if it appears near the top of several lists. Positions are
combined rather than scores, because a word-match score and a hop count are not
measured in the same units, and pretending otherwise would invent a relationship
between them.

Two of Zep's rankers are deliberately left out. One increases variety among
results, which matters at five hundred results and not at five. The other asks
an LLM to score each candidate, which is the most accurate option and costs an
extra model call in the middle of a live conversation while she waits.

Worth noting what is **absent**: no recency decay and no importance score. This
is ordinary information retrieval, not the "recency + importance + relevance"
formula from the Generative Agents paper.

And here is a bug this found within hours of being written:
""")

code("""
print('remember("Ah Seng") ->', search_facts("Ah Seng", graph))
""")

md("""
Empty, which is right — she asked about someone the archive has never heard of.

It did not used to be empty. `"Ah Seng"` matched a fact about `"Ah Chwee"`,
because both contain `"ah"`, an honorific half the family shares. Word matching
is supposed to discount common words automatically, by noticing they appear
everywhere. With only a few dozen sentences in the archive, nothing appears
often enough for that to work.

Query words shorter than three characters are now ignored.

This is the worst kind of bug in this product. Nothing throws an error. The agent
just tells her something confident and wrong about a person she asked after, in
a voice she has come to trust.
""")

# ── 10 ───────────────────────────────────────────────────────────────────────
md("""
## 10. When she remembers something differently

She will say the shop closed in 1969, and months later say 1970.

Zep's rule is to mark the older fact as no longer valid from the moment the newer
one becomes valid. Applied literally here, that produces: *"her father ran a
coffee shop, and that stopped being true in 1970"*. She never said that. **The
shop closed once.**

The problem is that two very different situations look identical in the data:
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
Both timelines already exist in the paper. The mistake would be pushing
everything onto one of them.

| Situation | What actually changed | Which timeline records it |
|---|---|---|
| *"she moved house in 2016"* | the world | **valid time** — Zep's rule, unchanged |
| *"closed in 1969"* → *"1970"* | her account of the world | **transaction time**, valid time untouched |

Business data is almost all the first kind: a customer changed address, a plan
was upgraded. An oral history is almost all the second. Sixty years on she is not
reporting changes in the world, she is recalling one fixed past with varying
accuracy.

Three rules hold either way:

1. **Nothing is ever deleted.** She said it, and that stays true about her.
2. **The newest version is what gets shown** on the map and in the letters.
3. **A disagreement becomes a question, not a decision.** It reaches the next
   call the same way a missing field does, because which version is right is
   hers to settle and not the database's.

Her family can correct the *system* — the geocoder that put her village ninety
kilometres from where it is. They cannot edit what she said.
""")

# ── 11 ───────────────────────────────────────────────────────────────────────
md("""
## 11. Chapters

The last layer. Entities that keep turning up together get grouped, and each
group is named from the facts connecting it.

The grouping algorithm is **label propagation**, which is simple enough to
describe in a sentence: every entity starts in its own group, then repeatedly
joins whichever group most of its neighbours are in, until nothing moves.

Zep chooses it over the better-known Leiden algorithm for one reason — a single
new entity can be slotted in without recomputing everything, which is cheap
enough to run after every call. That drifts over time, so a full recomputation
is also scheduled periodically. Both exist here.
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
**She breaks her own clustering.** Almost every fact in her archive is about her
life, so she is connected to everyone in it. That means she joins everything to
everything, and her childhood on the estate and her years at the shop collapse
into a single chapter — because she is the only thing they have in common.

She belongs to every chapter of her life. That is exactly why she cannot be used
to tell them apart.

Two wrong fixes came first, and both are worth recording:

- **Excluding her by name.** Her entity is called `Ah Khim`; the household record
  says `Lim Siew Khim`; the profile field was empty. So the exclusion list came
  out empty, the code ran, chapters appeared, and **nothing anywhere said the
  filter had matched nobody**.
- **Excluding anyone connected to more than half the graph.** Also matched
  nobody: 28 entities exist, but only 17 appear in any fact, so the denominator
  was wrong. Lowering it to "half" would have excluded the coffee shop, which is
  a chapter and not a hub.
- **Excluding the clear outlier.** She has 8 connections; the next entity has 3.
  That is what the rule should say. And the script now prints who it removed,
  because the two failures before it were both silent.

On her real archive this produces three chapters — the shop years, the estate
childhood, and her grandfather's arrival — each opening down to her own
sentences in the app.
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
