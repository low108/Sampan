# Sampan — 4:00 demo video script

Rubric: problem · value proposition · app in action · **proof the backend runs on
Google Cloud**. Budget 4:30, scripted to 4:20 so a slow page does not cost you
the ending.

---

## BEFORE YOU RECORD — deploy

The live service is a week behind. As of writing, Cloud Run serves bundle
`index-CeXpI5G1.js`; local is `index-BJ6NqfVh.js`, and
`/api/family/{id}/search` returns 405 there — **the memory panel does not exist
on the deployed build.** Beat 4 and the whole Google Cloud section fail if you
record against it.

```bash
./deploy.sh
```

Then set `SAMPAN_MIN_INSTANCES=1` for the recording so the first request is not
a cold start, and put it back to 0 afterwards.

**Verify before you hit record:**

```bash
URL=https://sampan-ig6xl5kf4q-as.a.run.app
curl -s "$URL/health"                                   # configured: true
curl -s "$URL/" | grep -o 'index-[A-Za-z0-9_-]*\.js'    # must match static/index.html
curl -s -X POST -H "X-Sampan-Key: $SAMPAN_API_KEY" -H 'Content-Type: application/json' \
     -d '{"question":"who is Ah Chwee"}' "$URL/api/family/ah_khim/search" | head -c 80
```

**Tabs to have open, in this order** — do not open anything live on camera:

1. `https://sampan-ig6xl5kf4q-as.a.run.app/?key=…&user=ah_khim` — her side
2. the same URL with `&user=wei_lun` — the family side
3. Cloud Run → service `sampan` → **Revisions**
4. Logs Explorer, query already run (below)
5. Firestore → Data, `facts__ah_khim` expanded

---

## 0:00 — 0:35 · The problem

Hold on her map, still, before you touch anything.

> My grandmother is eighty. She lives in Ipoh; her son is in Kuala Lumpur, her
> granddaughter is at university. They call on Sundays and ask if she has eaten.
>
> She knows things nobody else does. Which year the coffee shop opened. What her
> mother put in the fried rice. Who lived in the next line house on the estate.
> None of it is written down, and the family only finds out what they lost after
> she is gone.
>
> There are apps that will record an elderly person's memoir. They ask her to
> operate a phone, and they hand the family a transcript. That is a filing
> cabinet, and it is not the problem. **The problem is that she is lonely and the
> family is busy, and nobody has a way to turn one into the other.**

---

## 0:35 — 1:05 · What Sampan does

> Sampan phones her. She picks up and talks to Xiao Chuan — no app, no screen, no
> password. It listens, it remembers across months, and it turns what she says
> into a map her family can walk through.
>
> The part that matters is which direction it faces. **Xiao Chuan never speaks
> for the family and never stands in for them.** It carries their questions to
> her in their name, and carries her stories back. It is a bridge, and it is
> built to be obviously a bridge — because the failure mode for a product like
> this is becoming the company she has instead of her son.

---

## 1:05 — 1:50 · Her side: the call carries her son's question

**Tab 1, signed in as her.** Press **Tell a story**.

The screen opens with a question already waiting: **Wei Lun asked you something —
"how are you doing"**. Tap it and start the call.

> She has not opened an app. She pressed one button. And the first thing the
> agent says is not "hello, how can I help" —

Let the opening line play. It names Wei Lun and asks his question.

> — it is her son's question, in his name. She is not talking to an assistant.
> She is answering Wei Lun, and something is carrying it.

Talk for fifteen seconds. Say something with a place and a year in it.

> That is a live Gemini call — native audio, both directions, over a WebSocket to
> Cloud Run. Nothing on her end but a phone she already knows how to answer.

**Stop the call.** Do not wait for processing on camera.

---

## 1:50 — 2:15 · The family side: what came back

**Switch to tab 2, as Wei Lun.** The map.

> Every pin is a story she told, placed where it happened. Sixteen of them,
> across sixty years — the estate in Sungai Siput, the coffee shop on Jalan
> Bandar, her grandfather landing in Penang.

Tap **Father's shop in 1969**.

> Her words, kept as she said them. Her son has never heard this. He knows the
> shop closed; he does not know what the last day was like.

---

## 2:15 — 2:40 · The bell: the bridge working the other way

Open the bell. **Two unseen, both flagged concerns.**

> And this is the part I would not ship without. Twice, she said something the
> system will not keep to itself.

Open one: *Siew Khim mentioned hopelessness · "mentioned feeling like dying"*.

> An affect monitor runs on the audio alongside the conversation. It does not
> counsel her, it does not tell her she seems sad, and it does not decide
> anything. **It tells her son.**
>
> A product that made an eighty-year-old feel less lonely while her family
> learned nothing would be a failure that looked like a success. This is the
> line that stops that.

---

## 2:40 — 3:25 · Inside the memory

Click **Inside the memory**. It opens on
`what did her father do at the coffee shop`.

> The memory is a graph, not a transcript pile, and you can watch it work.
>
> Two entities found in one question: the coffee shop by name, and **her father
> by his role** — she never says his name.

Point at rows 2 and 3.

> Row three scores higher on keywords — 4.25 against 3.83 — and ranks below it,
> because row two sits on an entity the question named and row three is a hop
> away. **A keyword search returns those in the other order.** No model in this
> path, so those numbers are the same every time.

Click **Update**, click row 1, type and enter:

```
Ah Chwee moved to Kampung Baru in 2026.
```

> She says something new. Gemini decides what kind of disagreement it is —

Verdict lands: **State change · 0.95**.

> — she *moved*. So valid time closes and **nothing is withdrawn**. The old
> telling goes dim, not deleted, and the archive never records that she was
> wrong. If she had misremembered instead, transaction time would move and the
> old one would be retired. Two different clocks, and collapsing them is how you
> end up quietly overwriting an old woman's memory.

---

## 3:25 — 4:05 · Running on Google Cloud

**Tab 1, point at the address bar: `sampan-ig6xl5kf4q-as.a.run.app`.**

> Everything you just saw came off Cloud Run.

**Tab 3 — Cloud Run revisions.** Point at the revision and region.

> Service `sampan`, region `asia-southeast1`, request timeout an hour, because
> the default five minutes kills a call in the middle of a story.

**Tab 4 — Logs Explorer**, already showing the run.

> Vertex AI, this recording: the Live API on `gemini-live-2.5-flash-native-audio`
> in us-central1 for the call, `gemini-3.7-flash` for extraction and for the
> contradiction judge you just watched decide.

**Tab 5 — Firestore.**

> And the archive itself. `facts__ah_khim` — eighteen facts, thirty-three
> entities, each one carrying both timestamps. And Cloud DLP screens every
> write, so an account number she reads aloud never reaches this.

---

## 4:05 — 4:20 · Close

Back to her map.

> Sampan is one narrator, her family, and about sixty years, running on Google
> Cloud today.
>
> It will not keep her company. That is not the job. The job is that when her
> granddaughter asks what her great-grandfather did, somebody can answer — and
> that Wei Lun finds out his mother is struggling **this week**, not at the
> funeral.

---

## Logs Explorer query — run it before you record

```
resource.type="cloud_run_revision"
resource.labels.service_name="sampan"
severity>=DEFAULT
```

Add `jsonPayload.message=~"judge|gemini|live"` if the volume is noisy. Have the
results already on screen; do not type a query on camera.

---

## Cuts, in the order you should make them

You will overrun. Drop in this order and nothing structural breaks:

1. **The story card at 2:05** (−15s). The map alone carries it.
2. **Firestore, tab 5** (−12s). Cloud Run and the logs already satisfy the rubric.
3. **The second half of the update verdict** — stop after "she *moved*, so
   nothing is withdrawn" (−15s).
4. **The live call down to five seconds** (−10s). Keep the opening line: the
   agent saying Wei Lun's name is the single most important second in the video.

Never cut: the opening line of the call, the concern notification, or the
`.run.app` URL.

---

## If the live call fails on camera

It is the only beat that depends on a network round trip while you are speaking.
Record it separately, first, and edit it in. If it fails live:

> The call is a WebSocket to Cloud Run — let me show you what it produced
> instead.

and go straight to the map. The stories are already there; the beat still lands.
