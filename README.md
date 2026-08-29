# Sampan

> *ingat*: to remember, and to think of someone.

A voice companion for elderly parents that listens to their life stories, remembers across
months of conversations, and turns what it hears into a shared family memory map their
children and grandchildren can explore.

Built for the **All Things Agentic Hackathon** — Collaborative Partner track.

---

## Start here

**Live:** https://sampan-ig6xl5kf4q-as.a.run.app · Cloud Run, `asia-southeast1`

| | |
|---|---|
| **What it is and why** | [`docs/submission.md`](docs/submission.md) — the full submission: the problem, every design decision and the research behind it, and what each one cost |
| **The short version** | [`docs/text_description.md`](docs/text_description.md) — one-page pitch |
| **What it actually did** | [`docs/firestore-walkthrough.md`](docs/firestore-walkthrough.md) — four real calls, and exactly what each wrote to the database, with screenshots from the console |
| **Every prompt, verbatim** | [`docs/archivist_prompt.md`](docs/archivist_prompt.md) — all ten, with the failure each rule exists for |
| **How the backend is shaped** | [`docs/system-analysis.md`](docs/system-analysis.md) — design record, seventeen numbered decisions, and the alternative each one rejected |
| **Requirements** | [`PRD.md`](PRD.md) — tiered P0/P1/P2, with the limitations recorded honestly |

### Diagrams

| | |
|---|---|
| [`docs/architecture.png`](docs/architecture.png) | The system: browser to Cloud Run to three Google models to Firestore |
| [`docs/two-clocks.png`](docs/two-clocks.png) | Valid time versus transaction time — the idea the whole archive rests on |
| [`docs/round-trip.png`](docs/round-trip.png) | Son to mother and back, in nine messages |
| [`docs/call-map.png`](docs/call-map.png) | One call fanned into parallel timelines — every model, every collection, every write |

Each has an editable `.html` beside it.

### The archive these are built from

- [`docs/persona-bible.md`](docs/persona-bible.md) — the invented family
- [`docs/seed-sessions.md`](docs/seed-sessions.md) — four synthetic conversations, with pipeline assertions

---

## Status

Runs end to end on Cloud Run against Firestore. **542 unit tests** plus 63
integration tests over four chained sessions against the real model.

- **Companion** — browser mic to Cloud Run WebSocket to ADK to the Live API and
  native audio back, with the affect monitor forked off the same audio.
- **Archivist** — transcript to scored stories, entity graph, threads carrying
  the interrupted/tired distinction, anchors resolving her relative time
  expressions, and the learned preference layer.
- **Memory** — bi-temporal fact edges after Zep/Graphiti, retrieval behind a
  single `remember` tool with no model in the read path, contradiction routed to
  the correct time axis, and communities as her chapters.
- **Family archive** — map, timeline, letters, asks, corrections, and a bell
  that opens a recording with the asker's question already loaded.
- **Places** — relational names ("my father's shop") joined to places she named
  in other sessions, each link carrying the sentence that justifies it.

Everything is in English, including the seeds and the UI.

## One more thing worth opening

- **[`notebooks/knowledge_base_flow.ipynb`](notebooks/knowledge_base_flow.ipynb)** — the
  memory design walked end to end against the real code: the pre-set intake, what is
  committed into the model's context when recording starts, the two channels that reach
  it mid-call, and exactly what the Archivist changes when recording stops. Executed, with
  outputs.

## Spin-up

Two paths. **A** runs the whole app on your machine in about five minutes and
needs no Google Cloud account. **B** deploys the real thing.

### Prerequisites

| | |
|---|---|
| [uv](https://docs.astral.sh/uv/) | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Node 20+ | only for the web client |
| [gcloud CLI](https://cloud.google.com/sdk/docs/install) | path B only, authenticated |

---

### A · Run it locally

**1. Install and configure.**

```bash
git clone git@github.com:low108/Sampan.git && cd Sampan
uv sync
cp .env.example .env
```

**2. Set one value.** Open `.env` and fill in `SAMPAN_API_KEY`:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

Leave `GOOGLE_CLOUD_PROJECT` blank and `SAMPAN_ALLOW_IN_MEMORY_STORE=true`, as
they ship. The service then runs against an in-memory store and never touches
Google Cloud.

That fallback is opt-in on purpose: a deployed revision that lost its project id
must fail loudly rather than accept an old woman's stories into a dictionary and
report success.

**3. Start the API.**

```bash
uv run uvicorn sampan.app:app --reload --port 8080
```

**4. Check it.** `/health` and `/debug/smoke` both name the backend they used,
so a green round trip cannot be misread as having reached Firestore:

```bash
curl -s localhost:8080/health
# {"status":"ok","configured":false,"location":"asia-southeast1","backend":"memory"}

curl -s -X POST localhost:8080/debug/smoke \
  -H "X-Sampan-Key: $SAMPAN_API_KEY" -H 'Content-Type: application/json' \
  -d '{"note":"the coffee shop on Jalan Bandar"}'
```

**5. Start the web client**, in a second terminal:

```bash
cd web && npm install && npm run dev
```

Open the printed URL with `?key=YOUR_SAMPAN_API_KEY` appended. The key is stored
locally on first load, so later visits need only the bare URL.

**What works without Google Cloud:** the family archive — map, timeline,
chapters, letters, corrections, the bell, and the "Inside the memory" retrieval
panel. **What does not:** the voice call and anything else needing a model.

### Verify

```bash
uv run pytest                     # 542 unit tests, ~2s
uv run ruff check src tests scripts
uv run pyright
cd web && npx tsc --noEmit && npx vitest run
```

The integration tests are deselected by default because they call real models
and cost money. Run them deliberately:

```bash
uv run pytest -m integration
```

---

### B · Deploy to Cloud Run

**1. Create the project and turn on what it needs.**

```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
gcloud services enable run.googleapis.com firestore.googleapis.com \
  aiplatform.googleapis.com cloudbuild.googleapis.com
gcloud firestore databases create --location=asia-southeast1
```

Firestore must be `asia-southeast1`: an elderly Malaysian woman's stories should
not leave the region she lives in.

**2. Configure.**

```bash
export GOOGLE_CLOUD_PROJECT=your-project-id
export SAMPAN_API_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
```

**3. Deploy.**

```bash
./deploy.sh
```

It prints the service URL and three acceptance checks with that URL filled in.
The flags in `deploy.sh` are part of the contract, not deployment detail —
`--timeout=3600` most of all, because the 300s default kills a call mid-story
and looks like a Live API bug.

**4. Open it.** `https://YOUR-SERVICE-URL/?key=$SAMPAN_API_KEY`

A fresh deploy starts with an empty archive — there is no one-command seeder,
because the archive is meant to be built by talking to it. Press **Talk**, say
something, hang up, and the map has a pin on it. `seeds/` holds the six
transcripts the demo archive was grown from, and
`tests/test_seed_run_integration.py` replays them through the real extraction
pipeline if you want to see that path exercised.

**5. Two maintenance passes** for an archive that already has conversations:

```bash
uv run python scripts/backfill_facts.py            # dry run
uv run python scripts/backfill_facts.py --apply    # extract facts from stored transcripts
uv run python scripts/refresh_communities.py --apply   # rebuild her chapters
```

### Optional extras

Each is off unless configured, and the app is complete without all three.

| | Script | What it adds |
|---|---|---|
| **Screening** | `scripts/setup_armor.sh` | Cloud DLP over every transcript before anything is written |
| **Card imagery** | `scripts/setup_memories.sh` | Veo clips for story cards, queued off the call path |
| **Chapter refresh** | `scripts/setup_scheduler.sh` | Weekly Cloud Scheduler job that re-clusters her chapters |

Each prints the `.env` lines it needs; add them and re-run `./deploy.sh`.
Details for the first two follow.

### Screening what gets stored (recommended)

Transcripts are screened before they reach Firestore, so a bank account number
she reads out is de-identified rather than archived. Off unless a template is
configured.

The detection is **Sensitive Data Protection (DLP)**, not Model Armor. Model
Armor is the façade: its SDP filter delegates to DLP, and in advanced mode to
the templates below. It is worth keeping only for the filters DLP has no
equivalent of — prompt injection and jailbreak — which are **not enabled yet**.

```bash
gcloud services enable modelarmor.googleapis.com dlp.googleapis.com

# The Model Armor service agent needs to read the DLP templates. Without this
# the filter is SKIPPED and the API still answers 200 — a screen that reports
# success and protects nothing.
NUM=$(gcloud projects describe "$GOOGLE_CLOUD_PROJECT" --format='value(projectNumber)')
gcloud projects add-iam-policy-binding "$GOOGLE_CLOUD_PROJECT" \
  --member="serviceAccount:service-${NUM}@gcp-sa-modelarmor.iam.gserviceaccount.com" \
  --role=roles/dlp.user
```

Then create the two DLP templates and the Model Armor template that points at
them — `scripts/setup_armor.sh` does all three.

**On what DLP can and cannot detect here.** `FINANCIAL_ACCOUNT_NUMBER` sounds
like the right built-in and detects nothing: a bare Malaysian account number
spoken aloud matches no built-in info type at any likelihood. There are no
`MALAYSIA_*` info types at all, so there is no IC detector either. What works is
`CREDIT_CARD_NUMBER` (Luhn-checkable) plus a custom regex for grouped 10–16
digit runs. That regex was measured against her entire real archive: one
finding, the planted account number, and no false positives on years or dates.

Model Armor's *basic* SDP config is not used, deliberately. It enables Google's
whole default set, which on an eighty-year-old's life story means names, dates,
addresses and health details — it would redact the archive itself.

Then redeploy with:

```
SAMPAN_DLP_INSPECT_TEMPLATE=sampan-bank-only
SAMPAN_DLP_DEIDENTIFY_TEMPLATE=sampan-bank-redact
```

That is the DLP-direct path, which is the default. To route through Model Armor
instead — for its prompt-injection and jailbreak filters, which DLP has no
equivalent of — add `SAMPAN_SCREEN_BACKEND=armor` and
`SAMPAN_ARMOR_TEMPLATE=sampan-transcripts`. Both produce identical redaction;
measured at 507ms and 429ms on the same transcript.

**It fails open.** If Model Armor cannot be reached, the plain transcript is
stored, the failure is logged at ERROR to `sampan.armor`, and the conversation
is flagged `unscreened: true` with the error. Deliberate: losing her account of
her own life because a screening API had a bad minute is worse than holding an
unscreened transcript in a private database until someone reads the log.

`unscreened: true` is not the same as an empty `screened` list. The first means
the screen never ran; the second means it ran and objected to nothing. Both are
returned by `GET /api/talk/{id}/calls`, so "which calls went through unchecked"
is a query:

```bash
curl -H "X-Sampan-Key: $KEY" "$URL/api/talk/ah_khim/calls?limit=50" \
  | python3 -c "import json,sys;[print(c['conversation_id']) for c in json.load(sys.stdin)['calls'] if c['unscreened']]"
```

### Generated card imagery (optional)

Story cards can open on a short clip generated by Veo from what she said. It is
off unless configured, and the app is complete without it.

```bash
scripts/setup_memories.sh     # bucket, topic, push subscription, IAM
```

Then put the two lines it prints into `.env` and `./deploy.sh`. Stories told
after that queue themselves; anything already in the archive needs

```bash
python scripts/backfill_memories.py            # dry run, always
python scripts/backfill_memories.py --commit --limit 4
```

`--ack-deadline=600` matters: Veo takes tens of seconds and the 10s default
would redeliver the same message while the first is still generating, billing
for each. The dead-letter topic is the backstop — a message that keeps failing
stops rather than retrying a paid model call forever. (`--max-delivery-attempts`
has a floor of 5; it rarely binds, because the endpoint answers 200 even on
failure for exactly the same reason.)

The clip reaches the card through `attach_memories`, applied to every view
before any of them splits off. That join is the whole feature: without it Veo
renders, the bucket fills, Firestore records the asset, and no page ever shows
one — a pipeline that is green, billed for, and invisible.

### Cost

`--min-instances=0` and `--max-instances=3` by default. Set `SAMPAN_MIN_INSTANCES=1` only
while recording the demo, and put it back to `0` immediately after. Set a billing alert.

## Architecture

```
Browser ──WebSocket──> Cloud Run (FastAPI + ADK) ──> Gemini Live API
                            │
                            ├── audio fork ──> affect monitor (Gemini 3.7 Flash)
                            └── on hang-up ──> Archivist ──> Firestore
```

The Archivist runs in a worker thread once the socket closes, not via Pub/Sub. The call is
over for her the moment she hangs up, so extraction never holds the connection — but it is
in-process, which means a crash between hang-up and write loses that call's extraction. The
transcript is stored first, so nothing she said is lost and the call can be re-extracted.
Pub/Sub is the right answer at any real volume and is deliberately not built (`PRD.md` §6).

ADK is server-side and has no client-direct path, so the browser cannot connect to the Live
API itself — doing so would remove ADK entirely, taking tools, sessions and the audio fork
with it. See `PRD.md` §9.3.

**Cloud Run settings are part of the contract, not deployment detail.** `--timeout=3600`
matters most: the 300s default kills calls mid-story and looks like a Live API bug.

## Models and services

### Google AI models — three, doing nine jobs

| Model | Region | Used for | Temp |
|---|---|---|---|
| `gemini-live-2.5-flash-native-audio` | `us-central1` | the call itself — duplex audio, interruption, five ADK tools | — |
| `gemini-3.7-flash` | `global` | story extraction (`archivist.py`) | 0.2 |
| | | fact extraction (`fact_extraction.py`) | **0.0** |
| | | contradiction judge (`contradiction.py`) | **0.0** |
| | | affect monitor (`affect.py`) | **0.0** |
| | | place resolver and linker (`places.py`) | **0.0** |
| | | community naming (`communities.py`) | 0.3 |
| | | answering the family's questions (`ask_about.py`) | 0.3 |
| | | letters (`letters.py`) | 0.6 |
| `veo-3.1-fast-generate-001` | `us-central1` | four-second story-card clips, queued off the call path | — |

**Temperature is a decision each time, not a default.** Anything that must not
drift runs at 0.0 — the fact pass was measured yielding a stored fact on one run
and nothing on the next at 0.1, which made recording her correction a coin flip.
Story extraction sits at 0.2 because the narrative has to read like prose, and
letters at 0.6 because they are written once and read by people.

**Where there is deliberately no model:** retrieval (BM25 + two-hop graph search
+ reciprocal rank fusion) and the pinnability rubric. Both decide what the family
sees, so both are deterministic and show their working.

Three regions, each for a reason: story data lives in `asia-southeast1` (PDPA),
text models are served from `global`, and the Live API's native-audio model is
only available from `us-central1`. Verified by probing; the documented model
names do not all exist on Vertex.

The hackathon requires Gemini 3.5 or newer. No Live dialog model currently meets
that bar, so the requirement is satisfied by everything except the call itself
running on 3.7 — stated here rather than left for a reader to work out. See
`PRD.md` §9.2.

### Google Cloud services

| Service | Role |
|---|---|
| **Cloud Run** (`asia-southeast1`) | one FastAPI service. `--timeout=3600` because the 300s default kills a call mid-story; `--max-instances=3` caps spend |
| **Firestore** (`asia-southeast1`) | the archive. Ten collections per narrator, bi-temporal facts |
| **Vertex AI** | every model call, via `google-genai` |
| **Google ADK 2.7.0** | agent runtime — tool dispatch, session management, the live audio loop |
| **Sensitive Data Protection (DLP)** | screens every transcript before anything is written |
| **Model Armor** | provisioned, opt-in, not the default backend — see below |
| **Pub/Sub** | the Veo queue, push-subscribed to `/internal/memories` |
| **Cloud Storage** | the generated mp4s, public-read so a card can use the URL directly |
| **Cloud Scheduler** | weekly chapter refresh to `/internal/communities` — the only scheduled work in the product; everything else is written by the call that caused it |

## Limitations

Recorded honestly in `PRD.md` §16. The most important: **no real elderly person has tested
this.** Whether a lonely elder will open up to an AI voice — the premise the product rests on
— is unvalidated, and all testing is the developer voicing a scripted persona.
