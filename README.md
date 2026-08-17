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

**Gate 1: 51 integration tests** over four chained sessions against the real model, plus 292
unit tests. Everything is in English, including the seeds and the UI.

Remaining work is recording: sessions 5 and 6, and the dress rehearsal.

## Documents

| File | What it is |
|---|---|
| `PRD.md` | The product requirements, tiered P0/P1/P2 |
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
