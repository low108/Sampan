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

## Tool responses are the only silent channel into a live call

**2026-08-16, ticket 11.**

Since a live session cannot be steered mid-call (below), the affect guidance had to reach the
agent some other way. Tool responses turn out to be the one channel that works: the model
reads them, acts on them, and **never speaks them**. Every tool therefore returns `_guidance`
and `_turn_length` alongside its actual payload.

Verified with the agent set to a `depleted` state: it called `get_pending_ask`, received
「提早结束是好事」 in the response, and said only 「阿嬷,伟伦问阿公有没有留下什么东西?」 —
no leak, where the injected-turn approach had read its own stage directions aloud.

Two smaller things from the same ticket:

**Tools have to be announced.** The first live attempt called nothing at all. ADK declares the
functions to the model, but with no mention of them in the instruction the agent simply
carried on talking. Listing them, with a line on *when* to reach for each, was what made it
start using them.

**A tool's docstring is its prompt.** ADK builds the declaration from the signature and
docstring, so these are written in Chinese, addressed to the agent, in the register the rest
of the instruction uses — 「查不到就不要装懂」 sits in `recall`'s docstring, not in a comment.

## A live session cannot be steered mid-call

**2026-08-16, ticket 14.**

The affect monitor reads her every ninety seconds, so the obvious next step is to change how
the agent is behaving *during* the call. It cannot be done. A live session's system
instruction is sent once at connect, so ADK's `InstructionProvider` — a callable resolved per
invocation — never gets re-evaluated. Injecting direction as a turn was tried three ways, all
verified by running them:

| How | What happened |
|---|---|
| `role="user"`, fenced with 「不要念出来」 | Agent read the fence out loud: 「[系统提示,不是阿嬷讲的话。」 |
| `role="system"` | Agent acknowledged it aloud: 「好的,明白了。准备收尾。」 |
| `role="model"` | Turn-taking broke; it stopped answering her entirely |

The first is the worst outcome available: an eighty-year-old hears the machine read its own
stage directions about her.

So affect steers three other ways instead, none of them mid-turn:

1. **The next call's instruction** — real, deterministic, and the thing the demo shows
2. **Tool responses**, which are never spoken, so guidance can ride back on any tool the agent
   calls
3. **`enable_affective_dialog`**, the Live API's native in-turn adaptation

`LiveSession` has a comment where `steer()` would go, so the next person does not spend an
afternoon rediscovering this.

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

---

## Place resolution produces confident wrong answers on exactly the names that matter

**2026-08-16, tickets 8 and 17.**

A conventional geocoder is the wrong tool for this archive — the places that matter most are
a village named the way her father said it, an estate that stopped existing decades ago,
「板底街」 rather than Jalan Bandar. So resolution is a model call that must state its own
precision, and it does that well: 板底街 came back as Jalan Bandar Timah at street precision,
怡保火车站 as exact, 福建永春 as a region, and three places it could not place at all landed
in the tray with honest notes (「胶园工人排屋统称，无具体地理位置」).

But **双溪镇 resolved to Sungkai** — a real town in Perak, ninety kilometres from the one she
meant. Plausible, specific, and wrong, which is the failure mode I had predicted for a
geocoder and then reproduced.

The fix is not a better prompt. Anything coarser than street precision is now marked
`needs_confirmation` and rendered as a hollow pin under 「待确认」, because **a plausible wrong
pin is worse than an obviously missing one — nobody corrects what looks right.** The tray was
always designed to be visible; this extends the same reasoning to pins that merely look
confident.

Related: the ambiguity was partly self-inflicted. The persona bible calls her hometown 双溪镇,
which is not what Malaysian Chinese actually call Sungai Siput. An invented name inherited an
invented ambiguity — worth remembering when fixtures stand in for real data.

---

## An agent must not say it did something it did not do

**2026-08-16, audit.**

`flag_concern` — the tool for falls, chest pain, breathlessness, hopelessness — returned
`family_notified: True` and told her 「阿嬷,这个我会跟伟伦讲一声」. Nothing was sent anywhere.
It appended to an in-memory list that the Archivist did not even read.

Every other gap found in the same audit was a missing feature. This one was the agent stating
a falsehood to an eighty-year-old about her own safety, in the one code path where being
believed matters most, and it had been sitting there since the tools were written.

It now writes to Firestore the moment it is called — not at the end of the call, because a
fall should not wait for her to hang up — and the family view carries open concerns on every
tab rather than behind one. And when delivery fails, the agent says only 「这个我记下来了」 and
`family_notified` is false. There are tests for both the failure and the nothing-wired-up case,
because the honest sentence is the one that has to survive.

**Lesson:** any string a model speaks on behalf of the system is a claim the system has to
make true. Reassurance is the easiest thing for a tool to return and the easiest thing to
leave unimplemented.

## A route needs an order, and inventing one is not allowed either

**2026-08-16, journey view.**

The journey view sorts her stops by year. 阿公坐船南来 has no year — 「二十几年吧,我也不清楚」
was correctly left unresolved — so it sorted last, putting the origin of the family's migration
*after* her 1969, below a sea-crossing marker that then fired twice.

The tempting fix was to infer it: China precedes Malaysia, a grandfather precedes his
granddaughter, so put it first. All true, and all guessed. Undated stops are now shown under
「年份还没讲」 instead, the same way unplaceable ones sit in a tray.

Same shape as the pin problem: a plausible wrong position is worse than an admitted gap,
because the gap is the thing that gets the next call to ask her about it.

---

## The same crowding problem recurs at every zoom level

**2026-08-16, geographic view.**

The argument against a conventional map was that her pins are one dot in Fujian at 25°N and
four inside ninety kilometres of each other in Perak — illegible at any single scale. So the
SVG map got a Perak inset.

At inset scale, three of those four pins landed on **the same coordinate**: 板底街, the room
above the shop, and the railway station where the wedding photo was taken are a few hundred
metres apart. Three labels, one dot. The fix that solved the problem at ocean scale simply
moved it down one level.

They are now drawn as one marker named 「板底街 +2」, sized by story count, with all three
names in the tooltip — which is arguably truer to the life anyway: the shop, the room above
it and the station are one place to her, and only a projection insists otherwise.

**Lesson:** zooming does not fix crowding, it relocates it. Cluster, or accept that a map of
someone's life is mostly a map of one street.

---

## The pages 404'd in production while every API route worked

**2026-08-16, first full deploy.**

The deployed service answered `/health`, `/api/family/…` and `/api/talk/…` correctly and
returned 404 for `/family.html`, `/manifest.json`, `/icon.svg` and `/worklet.js`. Two
independent bugs, neither visible from a local checkout:

1. **The Dockerfile never copied `static/`.** It copies `pyproject.toml`, `uv.lock` and `src`,
   which is everything Python needs and nothing a browser does.
2. **The static path was resolved relative to `__file__`.** Once `uv sync` installs the
   project, `sampan` lives under `.venv/lib/python3.12/site-packages/`, so
   `parents[2] / "static"` points inside the virtualenv. Locally, running from a source
   checkout, the same expression happened to land on the repo root — it worked by accident.

Both were caught only by curling the deployed URL for pages rather than endpoints. A health
check would not have found it; neither would any test that imports the app, because the app
imports fine and simply mounts nothing.

There are now three tests: the static directory resolves, the Dockerfile copies it, and every
file the pages reference exists — a missing `worklet.js` fails silently in the browser, with
the microphone button doing nothing and no error anywhere.

**Lesson:** deploy verification has to fetch the things a *user* fetches. An API that answers
200 tells you the container is alive, not that the product is.

---

## The best stories had no place, and the answer was already in the archive

**2026-08-16.**

Four of eleven stories could not be put on the map — and they were the four
*best* stories, every one scoring 6/6, including the emotional peak of the whole
demo: the day her father closed the coffee shop and poured her a cup of Ovaltine
they could not normally afford, 「他讲，喝了就没有了」.

The reason was mundane. She names places by **relationship, not address**:
「爸爸的咖啡店」, 「家里」. A geocoder can do nothing with "my father's coffee
shop", so all four sat in the unlocated tray while the map showed her lesser
stories.

But she had already said where the shop was — six weeks earlier, in a different
session: 「一九五八年在怡保开了一间咖啡店,在板底街」. And 板底街 *was* placed, at
street precision. The two names had simply never been joined.

Linking them requires the same discipline as everything else here: each link
must carry **her own sentence** as evidence, and links without one are dropped.
That placed 「爸爸的咖啡店」 and 「line house」 — and correctly refused 「家里」,
because she never once said which house. Pins went 5 → 7, unlocated 3 → 1.

**Lesson:** before treating a gap as missing data, check whether it is
*unjoined* data. An archive that accumulates across months will often already
contain the answer, said in a different conversation, in a form no lookup would
match.

---

## The same bug, a third time: a tool that reassures and does not act

**2026-08-16, building the family chat agent.**

`mark_private` appended to a list on an in-memory object and told her
「好,这个我不写进去」 — *"alright, I won't write this down."* The list was
discarded when the call ended. Nothing filtered anything, anywhere: the feed,
the map and the new chat agent all served every story regardless.

This is the third instance of one pattern. `flag_concern` returned
`family_notified: True` and notified nobody. The extraction prompt filled
`sense_detail` with a paraphrase rather than admit it had nothing. Now this.

Each time, the reassuring branch was the easy one to write and the one nobody
checks, because a green result looks like success. **Any string a model speaks
on behalf of the system is a claim the system must make true** — and the
strings that promise safety, privacy or delivery are exactly the ones a test
suite full of happy paths will never contradict.

The fix keeps her promise: private subjects persist, and `build_cards` filters
them once, centrally, because a story that escapes into one view has escaped.

**What was deliberately not done:** stories the extractor marks `sensitive` are
still shown to the family, flagged rather than hidden. Both sensitive stories in
the archive are ones the teller *chose* to tell — she described the shop closing
when her son asked, and he described regretting the five-minute phone calls.
Burying those behind an approval workflow that does not exist yet would be a
worse record of the family than marking them and treading carefully.
