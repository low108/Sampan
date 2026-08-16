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

## The model will not choose a pin type unless you tell it how

**2026-08-16, ticket 2.**

First run of extraction against seed session 1 produced both expected stories, correctly
scored, with genuinely good sensory details — but `pin_type` was wrong on both. A story about
playing in a river came back as `person`; a story with a named location came back as
`timeline`. Either would have silently dropped the story off the map.

The schema's enum and field descriptions were not enough. What fixed it was an explicit
decision procedure in the prompt, in priority order, ending with a hard rule: *if `where` has
a real location, never choose `timeline`.*

Same run, same fix: asking for "a sensory detail" produced a list of three. Asking for
**one** produced 「煤油灯下一碗白饭配酱油」 — a bowl of rice and soy sauce under a kerosene
lamp. The constraint is what makes it a story instead of an inventory.

**Lesson:** structured output guarantees the *shape*, never the *judgement*. Any field whose
value is a decision rather than a transcription needs the decision procedure written out.

## A model will satisfy a qualitative field by paraphrasing the answer back at you

**2026-08-16, ticket 4.**

`sense_detail` is the field the whole product leans on — the difference between 「我们很穷」
and 「我们吃白饭配酱油,妈妈说她已经吃过了」. Asking for "one concrete sensory detail" got it
filled every single time, which looked like success until the values were read:

> `sense_detail: '从福建永春坐船在槟城上岸的迁徙画面'`
> *("the scene of migrating from Yongchun and landing at Penang")*

She never described a boat, the sea, or anything she perceived. The model restated the story's
own facts and appended 「的画面」 — *the scene of*. A fact wearing a sensory costume. It passed
every structural check: non-empty, one item, on topic.

What fixed it was demanding **quotability** rather than describing the quality wanted: it must
be something she said, pointable to a line in the transcript, plus worked examples of the
failure mode, plus explicit permission to leave it empty. After that, 阿公坐船到槟城 returned
her own 「坐船来的,槟城上岸」, and 一九六九年咖啡店结业 correctly returned **nothing at all**.

**Lesson:** a field a model can satisfy by rephrasing its own output will be satisfied that
way. Anchor such fields to the source text, and say plainly that empty is an acceptable answer
— otherwise "always filled" is indistinguishable from "always fabricated".

## The three-axis affect model earned its keep, then a bug erased the benefit

**2026-08-16, tickets 13-14.**

The design argument for three orthogonal axes rather than one emotion label was that *sad and
engaged* and *sad and withdrawing* need opposite responses. Controlled TTS samples, same voice,
different delivery, put that to the test:

| Delivery | energy | engagement | affect |
|---|---|---|---|
| loud, fast, laughing | fresh | engaged | excited |
| slow, trailing off, 「都过去了」 | fading | **withdrawing** | sad |
| slow, grieving, telling the Milo story | fresh | **engaged** | sad |

The model heard the sigh, the pace, and the lexical closers, and separated the last two
correctly. The design was right.

Then `policy()` gave both sad states **identical** knobs — because `affect is SAD` was checked
before `engagement is WITHDRAWING`, so sadness swallowed withdrawal. The three axes were being
computed accurately and then collapsed one line later.

**Every unit test passed.** Each one exercised a single axis — sadness alone, withdrawal alone
— and the combination that motivated the entire design had no test at all. It was only visible
by printing the two policies side by side and seeing the same string twice.

**Lesson:** when a design's justification is *"these two cases differ"*, that pair is the test
worth writing first. Testing each axis in isolation verifies the axes exist, not that they do
anything.

## A persona cannot hold state, and a hardcoded greeting fires forever

**2026-08-16, ticket 12.**

The Companion's base instruction carried its own opening line, guarded in prose:

> 第一次见面这样开场:「阿嬷,我是小船。你儿子伟伦叫我来陪你聊天…」
> *("On the first meeting, open like this: …")*

On a session-5 call — full memory loaded, the interrupted thread ranked, the family ask
attributed — the agent opened by **introducing itself from scratch**. The condition read as a
suggestion because nothing in its context could tell it whether this was the first meeting.
Everything else about memory was working, and the very first thing she would have heard was
an agent that had never met her.

Moving the greeting out of the persona and into the rendered session plan fixed it: the plan
knows `session_count`, so it either supplies the introduction or says *"you have spoken 4
times, do not introduce yourself."* Session 1 now introduces; session 5 opens 「阿嬷,您好」
and, one turn later, 「伟伦想知道,阿公有没留下什么东西?」

**Lesson:** a persona is static text and cannot evaluate a condition about state it does not
have. Any instruction of the form *"if X, say Y"* must be resolved by the code that knows X,
and only the resolved branch handed to the model.

## Watch your own test prompts before blaming the agent

**2026-08-16, ticket 12.**

Three times in one ticket the agent looked broken and was not:

- Fed 「阿嬷,我是小船。你今天早上吃了没有?」 — *the agent's own line* — as a **user** turn, it
  replied in the grandmother's voice. Correct: it was answering the person who said that.
- Fed 「喂?小船啊?」 — literally *"is that Xiao Chuan?"* — it identified itself. Correct.
- Fed a single 「喂」 and expected the full opener; the plan says read her first two turns
  before offering anything, so greeting and waiting was the specified behaviour.

Only the first-meeting problem was real. With a conversational agent the prompt is part of
the test fixture, and a sloppy one produces a convincing false failure — the temptation each
time was to go and "fix" behaviour that was already right.

## ADK builds its own genai client from the environment and never sees your config

**2026-08-16, ticket 10.**

The first attempt at a live session failed with:

> `ValueError: No API key was provided. Please pass a valid API key. Learn how to create an
> API key at https://ai.google.dev/gemini-api/docs/api-key`

The project was configured, credentials were fine, and the Archivist had been calling Vertex
successfully for days. The message points at the Gemini API — a completely different product
— and says nothing about the actual cause: **ADK constructs its own `genai.Client` from
environment variables** and has no way to receive a settings object. Without
`GOOGLE_GENAI_USE_VERTEXAI=true` it defaults to the Gemini API and looks for a key that was
never going to exist.

Configuration has to be *pushed* to ADK rather than passed. `apply_genai_env()` exports what
it reads, and is called at app startup.

## The Live API's model names and regions are not the ones in the docs

**2026-08-16, ticket 10.**

Research said the Gemini API offers `gemini-3.1-flash-live-preview` and Google Cloud offers a
GA `gemini-live-2.5-flash-native-audio`. Both true, and neither directly usable: the first
does not exist on Vertex at all, and the second is not served from `global`. Probing:

| Location | Model | |
|---|---|---|
| `global` | `gemini-3.1-flash-live-preview` | ✗ no such publisher model |
| `global` | `gemini-live-2.5-flash-native-audio` | ✗ |
| `global` | `gemini-live-2.5-flash` | ✓ |
| `us-central1` | `gemini-live-2.5-flash-native-audio` | ✓ |
| `us-central1` | `gemini-2.0-flash-live-preview-04-09` | ✗ |

So the Live API needs its **own region**, separate from the text models: native audio at
`us-central1`, while the Archivist runs `gemini-3.7-flash` at `global`. Three regions in total
once the Firestore data region is counted, each for a different reason.

This also confirms empirically what the hackathon-compliance note in PRD §9.2 assumed: the
best available Live dialog model is 2.5, below the required 3.5, so compliance rests on the
Archivist and affect monitor running 3.7.

**Lesson:** for preview-tier model availability, a five-line probe beats any documentation.
Write it once and keep it.

## ADK's `run_live` generator cannot be left early

**2026-08-16, ticket 10.**

`break`, `return` or `cancel` inside `async for event in runner.run_live(...)` produces:

> `RuntimeError: generator didn't stop after athrow()`

followed by orphaned pending tasks. This is not an edge case — **a browser disconnect does
exactly that on every call**, so the naive implementation raises on every hang-up.

The correct shape is to never leave the loop: close the `LiveRequestQueue` and let the
generator wind down on its own. `pump` closes the queue when the client goes away and
suppresses that specific RuntimeError for the cases where the generator still cannot finish
cleanly, while letting any other RuntimeError through.

## Give the model the vocabulary, or nothing downstream can unify its labels

**2026-08-16, ticket 6.**

Sensitive topics and open threads are both keyed by a short label the model writes. Left to
itself it invents a fresh one every call: she refused to discuss why the coffee shop closed,
which came back as 关店的原因 in session 2 and 阿公的店关门 in session 4.

No string matching can reconcile those. They share no substring, and semantically-similar
matching needs embeddings — expensive, and still guessy. The consequence was concrete and
bad: she *told* the shop-closing story in session 4 when her son asked, but because the
engagement landed on a differently-named topic, the subject stayed marked
`do_not_raise` — and session 5 would have tiptoed around the very thread it was supposed
to reopen.

The fix was to stop matching after the fact and pass the labels already in use into the
prompt, with an instruction to reuse them. Topic count fell from 10 to 8, 关店的原因
correctly accumulated `refusals=1, engagements=1`, and `do_not_raise` flipped back to false.

**Lesson:** when a model generates the keys that later join your data, it is not enough to
reconcile them downstream — give it the existing key space and tell it to reuse it. The same
pattern that made entity resolution work (seeding the family intake) applies to every
model-authored identifier.

## A refusal should not be permanent

**2026-08-16, ticket 6.**

The first cut of sensitivity treated a refusal as an absorbing state: she says 「不要讲这个」
once and the agent never raises it again. That is right for her sister, and wrong for the
shop closing — she declined it in session 2 and then told the whole story herself in session
4 when her son asked.

An agent that keeps avoiding a subject the person has since chosen to talk about is not being
sensitive; it is being obtuse. `do_not_raise` now clears when she engages, while the topic
stays marked `sensitive` so it is still approached gently. The gate constrains the agent,
never her — she may always raise anything.

## An invented target number nearly caused a real regression

**2026-08-16, ticket 4.**

`docs/seed-sessions.md` asserted the seed run should produce "4-6 fragments". The pipeline
produced zero, and the reflex was to loosen the pinning rule until the number matched.

The number was invented when the document was written, with no run behind it. With WHERE and
WHEN mandatory at a threshold of four, and her transcripts nearly always carrying both, almost
every story legitimately pins — and the extraction-feeds-the-next-question loop works anyway,
because `missing_fields` is populated on *pinned* stories too. 一九六九年咖啡店结业 pins at
4/6 with `["sense", "why"]`: it reaches the map *and* supplies a later question. Strictly
better than withholding it.

The document was corrected to match the pipeline. **Planning documents written before any code
contain guesses stated in the same tone as requirements**, and the tone is not a reliable
guide to which is which.

## Date inference across a transcript works better than expected

**2026-08-16, ticket 2.**

She says 「六七岁吧」 in one turn and 「我是一九四六年生的」 several turns later. The model
resolved the first against the second and returned `start_year: 1952, end_year: 1953` while
preserving `raw_phrase: '六七岁吧'`.

That is the two-fields-for-time design paying off on the very first run, and it is the
mechanism the whole "session 20 has a sharper timeline than session 3" claim rests on.

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
