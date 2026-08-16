# Sampan

> *ingat*: to remember, and to think of someone.

A voice companion for elderly parents that listens to their life stories, remembers across
months of conversations, and turns what it hears into a shared family memory map their
children and grandchildren can explore.

Built for the **All Things Agentic Hackathon** — Collaborative Partner track.

---

## Status

Early. Ticket 1 of 20 (`docs/spec-p0.md`, `docs/build-plan.md`) — the walking skeleton: a
deployable service that proves the Firestore round trip and refuses unauthenticated traffic.
The Companion voice agent and the Archivist pipeline land on top of this.

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
  -d '{"note":"板底街的咖啡店"}'
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
                            └── Pub/Sub ──> Archivist job ──> Firestore
```

ADK is server-side and has no client-direct path, so the browser cannot connect to the Live
API itself — doing so would remove ADK entirely, taking tools, sessions and the audio fork
with it. See `PRD.md` §9.3.

**Cloud Run settings are part of the contract, not deployment detail.** `--timeout=3600`
matters most: the 300s default kills calls mid-story and looks like a Live API bug.

## Models

| Role | Model |
|---|---|
| Voice | `gemini-3.1-flash-live-preview` |
| Archivist (extraction) | `gemini-3.7-flash` |
| Affect monitor | `gemini-3.7-flash` |

The hackathon requires Gemini 3.5 or newer. No Live dialog model currently meets that bar, so
the requirement is satisfied by the Archivist and affect monitor running on 3.7 — stated here
explicitly rather than left for a reader to work out. See `PRD.md` §9.2.

## Limitations

Recorded honestly in `PRD.md` §16. The most important: **no real elderly person has tested
this.** Whether a lonely elder will open up to an AI voice — the premise the product rests on
— is unvalidated, and all testing is the developer voicing a scripted persona.
