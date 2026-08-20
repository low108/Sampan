# Sampan

> *ingat*: to remember, and to think of someone.

A voice companion for elderly parents that listens to their life stories, remembers across
months of conversations, and turns what it hears into a shared family memory map their
children and grandchildren can explore.

Built for the **All Things Agentic Hackathon** — Collaborative Partner track.

---

## Status

All 20 tickets are done. The system runs end to end on Cloud Run against Firestore, seeded
with four conversations for one narrator and two for another.

- **Archivist** — transcript to scored stories, entity graph, threads carrying the
  interrupted/tired distinction, anchors resolving her relative time expressions, and the
  learned preference layer.
- **Companion** — browser mic to Cloud Run WebSocket to ADK to the Live API and native audio
  back, with the affect monitor forked off the same audio.
- **Family archive** — map, timeline, letters, asks, corrections, and a bell that opens a
  recording with the asker's question already loaded.
- **Places** — relational names ("my father's shop") joined to places she named in other
  sessions, each link carrying the sentence that justifies it.

**Memory v2** (`docs/spec-temporal-graph.md`) adds bi-temporal fact edges after
Zep/Graphiti, Zep-style retrieval behind a single `remember` tool, contradiction
routed to the correct time axis, a topic *lean* that never becomes a push, and
communities as her chapters.

**Gate 1: 60 integration tests** over four chained sessions against the real model, plus 442
unit tests. Everything is in English, including the seeds and the UI.

Remaining work is recording: sessions 5 and 6, and the dress rehearsal.

## Documents

- **[`docs/system-analysis.md`](docs/system-analysis.md)** — the backend design record:
  architecture, data model, the four seams, seventeen numbered decisions with the
  alternative each one rejected, a degradation matrix, and ten accepted risks. Read this
  before changing anything structural. Every claim in it is verified against source or
  labelled as unverified.

- **[`docs/spec-temporal-graph.md`](docs/spec-temporal-graph.md)** — the memory revamp:
  bi-temporal fact edges after Zep/Graphiti, Zep-style retrieval behind one tool,
  communities as her chapters, and the contradiction rules. Supersedes the memory
  sections of `spec-p0.md`.

- **[`notebooks/knowledge_base_flow.ipynb`](notebooks/knowledge_base_flow.ipynb)** — the
  memory design walked end to end against the real code: the pre-set intake, what is
  committed into the model's context when recording starts, the two channels that reach
  it mid-call, and exactly what the Archivist changes when recording stops. Executed, with
  outputs.

| File | What it is |
|---|---|
| `PRD.md` | The product requirements, tiered P0/P1/P2 |
| `docs/system-analysis.md` | Backend design record: why it is shaped this way, and what that cost |
| `docs/spec-p0.md` | Engineering spec for the P0 tier, with test seams |
| `docs/build-plan.md` | 17-day schedule with three go/no-go gates |
| `docs/persona-bible.md` | The invented family the demo is built around |
| `docs/seed-sessions.md` | Four synthetic conversations, with pipeline assertions |
| `docs/demo-scripts.md` | Recorded sessions 5 and 6, plus the video shot list |

## Spin-up

### Prerequisites

- [uv](https://docs.astral.sh/uv/) — `curl -LsSf https://astral.sh/uv/install.sh | sh`
- [gcloud CLI](https://cloud.google.com/sdk/docs/install), authenticated
- A Google Cloud project with billing enabled and Firestore provisioned

### Run locally

```bash
uv sync
cp .env.example .env      # then fill in SAMPAN_API_KEY at minimum
uv run uvicorn sampan.app:app --reload --port 8080
```

With `SAMPAN_ALLOW_IN_MEMORY_STORE=true` the service runs against an in-memory store, so it
works on a machine that has never seen a Google Cloud credential. The fallback is opt-in on
purpose: a deployed revision that lost its project id must fail loudly rather than accept
stories into a dictionary and report success. `/health` and `/debug/smoke` both name the
backend they used, so a green round trip can't be misread as having reached Firestore.

```bash
curl -s localhost:8080/health

curl -s -X POST localhost:8080/debug/smoke \
  -H "X-Sampan-Key: $SAMPAN_API_KEY" -H 'Content-Type: application/json' \
  -d '{"note":"the coffee shop on Jalan Bandar"}'
```

### Tests, lint, types

```bash
uv run pytest
uv run ruff check src tests
uv run pyright
```

### Deploy to Cloud Run

One-time project setup:

```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
gcloud services enable run.googleapis.com firestore.googleapis.com \
  aiplatform.googleapis.com cloudbuild.googleapis.com
gcloud firestore databases create --location=asia-southeast1
```

Then:

```bash
export GOOGLE_CLOUD_PROJECT=your-project-id
export SAMPAN_API_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
./deploy.sh
```

`deploy.sh` prints the three acceptance checks for ticket 1 with the deployed URL filled in.

### Screening what gets stored (recommended)

Transcripts are screened by Model Armor before they reach Firestore, so a bank
account number she reads out is de-identified rather than archived. Off unless a
template is configured.

```bash
gcloud services enable modelarmor.googleapis.com dlp.googleapis.com

# Narrow on purpose: one info type. Model Armor's *basic* SDP config enables
# Google's whole default set, which on an eighty-year-old's life story means
# names, dates, addresses and health details — the archive itself. Advanced
# config against a DLP inspect template is what keeps it to the account number.
gcloud dlp inspect-templates create \
  --location=asia-southeast1 \
  --template-id=sampan-bank-only \
  --inspect-config-info-types=<VERIFIED_INFO_TYPE>

gcloud model-armor templates create sampan-transcripts \
  --location=asia-southeast1 \
  --advanced-config-inspect-template=projects/$GOOGLE_CLOUD_PROJECT/locations/asia-southeast1/inspectTemplates/sampan-bank-only
```

Then redeploy with `SAMPAN_ARMOR_TEMPLATE=sampan-transcripts`.

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
export BUCKET="${GOOGLE_CLOUD_PROJECT}-memories"
gcloud services enable pubsub.googleapis.com storage.googleapis.com

gcloud storage buckets create "gs://$BUCKET" --location=asia-southeast1
gcloud storage buckets add-iam-policy-binding "gs://$BUCKET" \
  --member=allUsers --role=roles/storage.objectViewer   # cards load the URL directly

gcloud pubsub topics create sampan-memories
gcloud pubsub subscriptions create sampan-memories-push \
  --topic=sampan-memories \
  --push-endpoint="${SERVICE_URL}/internal/memories?key=${SAMPAN_API_KEY}" \
  --ack-deadline=600 \
  --max-delivery-attempts=3 \
  --dead-letter-topic=sampan-memories-dead
```

Then redeploy with `SAMPAN_MEMORIES_TOPIC=sampan-memories` and
`SAMPAN_MEMORIES_BUCKET=$BUCKET`.

`--ack-deadline=600` matters: Veo takes tens of seconds and the 10s default
would redeliver the same message while the first is still generating, billing
for each. The dead-letter topic is the backstop — a message that fails three
times stops rather than retrying a paid model call forever.

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

## Models

| Role | Model | Region |
|---|---|---|
| Voice | `gemini-live-2.5-flash-native-audio` | `us-central1` |
| Archivist (extraction) | `gemini-3.7-flash` | `global` |
| Affect monitor | `gemini-3.7-flash` | `global` |

Three regions, each for a different reason: story data lives in `asia-southeast1` (PDPA),
text models are served from `global`, and the Live API's native-audio model is only available
from `us-central1`. Verified by probing — see `FINDINGS.md`; the documented model names do not
all exist on Vertex.

The hackathon requires Gemini 3.5 or newer. No Live dialog model currently meets that bar, so
the requirement is satisfied by the Archivist and affect monitor running on 3.7 — stated here
explicitly rather than left for a reader to work out. See `PRD.md` §9.2.

## Limitations

Recorded honestly in `PRD.md` §16. The most important: **no real elderly person has tested
this.** Whether a lonely elder will open up to an AI voice — the premise the product rests on
— is unvalidated, and all testing is the developer voicing a scripted persona.
