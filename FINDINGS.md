# Findings

Surprises encountered while building Sampan. Kept as we go, because the hackathon submission
asks for "findings and learnings" and reconstructing them at the end never works.

---

## Cloud Run's front end silently swallows `/healthz`

**2026-08-16, ticket 1.**

A `GET /healthz` against the deployed service returned Google's generic HTML 404 page, while
`POST /debug/smoke` on the same host worked and reached Firestore. The route was registered —
`/openapi.json` listed `['/healthz', '/debug/smoke']`.

What isolated it: `/health` and `/totally-made-up-path-xyz` both returned FastAPI's own
`{"detail":"Not Found"}`, proving requests reach the container, while `/healthz` returned
Google's HTML with no `server` header. So the **Google Front End intercepts `/healthz` before
it reaches Cloud Run at all.**

Renaming the endpoint to `/health` fixed it. Nothing in the application was ever wrong, which
is what makes this expensive — the natural debugging instinct is to suspect your own routing,
your Dockerfile, or your uvicorn command.

`/healthz/` (trailing slash) returns a 307 from FastAPI's own redirect handling, so the path
is only intercepted in its exact bare form.

**Lesson:** don't use `/healthz` on Cloud Run. Verify a health endpoint from *outside* the
container, not just in tests.

---

## `secrets.compare_digest` raises on non-ASCII strings

**2026-08-16, ticket 1 code review.**

Starlette decodes HTTP headers as latin-1, so any byte above `0x7F` in a header arrives as a
non-ASCII `str`. `secrets.compare_digest` refuses those:

```
TypeError: comparing strings with non-ASCII characters is not supported
```

An API key check written the obvious way therefore returns an unhandled **500 with a traceback**
instead of a clean 401, for any mis-encoded or hostile client. Comparing `.encode("utf-8")`
bytes on both sides fixes it.

Worth noting for a product handling Chinese text everywhere: the failure only appears on the
*header* path, not the body, so it survives any amount of testing with ASCII keys.

Also: httpx (and so `TestClient`) refuses to *send* a non-ASCII `str` header at all, encoding
to ASCII and raising `UnicodeEncodeError`. The regression test has to pass raw `bytes` to
reproduce what a real client puts on the wire.

---

## A silent storage fallback makes an acceptance check unfalsifiable

**2026-08-16, ticket 1 code review.**

The first version fell back to an in-memory store whenever `GOOGLE_CLOUD_PROJECT` was empty,
so local development worked without credentials. On a deployed revision that lost its project
id — a typo in `--set-env-vars`, or a later `gcloud run deploy` without the flag — the smoke
endpoint would report `round_trip_ok: true` while writing to a dictionary that was discarded
at the end of the request.

The acceptance check for "we can reach Firestore" would pass without Firestore existing.

Two changes: the fallback is opt-in via an explicit flag, and both endpoints now report which
backend they actually used. A green result that doesn't name its backend isn't evidence.

---

## ADK never touches the microphone, so forking audio is trivial

**2026-08-15, architecture research.**

The PRD's highest-severity risk was whether the user's raw audio could be tee'd out of ADK to
feed a separate prosody model. It turned out to be a non-issue for a reason worth stating
plainly: **ADK does not capture audio.** The application pushes PCM into
`LiveRequestQueue.send_realtime(blob)`, so the bytes are already in hand before ADK sees them.
The fork is one extra line at the application's own WebSocket handler.

There is no ADK plugin hook for live audio — `base_plugin.py` has no `live` callbacks at all —
and none is needed. `RunConfig(save_live_blob=True)` exists but only flushes on turn
boundaries and requires an artifact service, which is worse for this purpose.

Corollary that did change the architecture: because ADK is server-side only, the browser
cannot connect to the Live API directly. Doing so removes ADK entirely — tools, sessions and
the audio fork with it. The server-relay topology is forced, not chosen.

---

## Cloud Run's default request timeout would have killed every call

**2026-08-15, architecture research.**

Cloud Run's default request timeout is **300 seconds**, and a WebSocket is just a long-running
HTTP request. Every conversation would have been severed at exactly five minutes, which would
present as a Live API failure rather than a deployment setting.

`--timeout=3600` is in `deploy.sh` from the first commit for this reason. Separately, Live API
audio sessions cap at roughly 15 minutes regardless, so session resumption is required for a
grandmother who wants to keep talking.

---

## A PWA cannot ring

**2026-08-15, architecture research.**

The product's core interaction — the family reaching an elder who isn't already looking at
their phone — cannot be built as a PWA on Android. Verified:

- Android reserves `USE_FULL_SCREEN_INTENT` for apps providing calling or alarm functionality,
  and the Play Store revokes it otherwise. No web API reaches it.
- `Notification.CallStyle` is native-only.
- The web `scenario: "incoming-call"` proposal is Windows-only, behind a flag, with no Android
  milestone and no signal from Firefox or Safari.
- Custom notification sounds are absent from the Notifications spec and from every browser —
  proposed 2014, removed 2018. One default chirp, no loop. (Several current blog posts claim
  otherwise; they are wrong.)
- A service worker cannot play audio, so nothing sounds until the user taps.

What ships instead: push wakes the closed PWA, a high-priority notification vibrates, and
tapping opens the app with audio playing and the mic live. That is a notification, not a call,
and for an elderly user who may not notice a single chirp it is a material product risk rather
than a cosmetic one.

---

## "Gemini 3.5 Flash" is real but already legacy, and no Live model meets the hackathon bar

**2026-08-15, architecture research.**

The hackathon requires Gemini 3.5 or newer. `gemini-3.5-flash` exists but is documented as
legacy; current stable is `gemini-3.7-flash`. More awkwardly, the available Live dialog models
are `gemini-3.1-flash-live-preview` and `gemini-live-2.5-flash-native-audio` — **neither meets
the stated requirement.**

Resolution: voice on a Live model, extraction and affect analysis on `gemini-3.7-flash`, and
say so explicitly in the write-up rather than leaving a judge to work it out.

Also: Vertex AI's generative-AI documentation is frozen and the platform has been renamed to
Gemini Enterprise Agent Platform. Anything referencing `vertex-ai/generative-ai` paths is
months stale — including, in practice, a lot of AI-generated GCP config.
