# Sampan

## One-line positioning

**A voice companion that phones an elderly parent, listens, and remembers
across months , turning a lifetime of spoken stories into a family memory map,
so the things only she knows are heard, kept, and inherited.**

### What the name means

**Sampan** a Malay word that comes from *三板*  "three planks." A small flat-bottomed boat.
The cheapest thing that will still cross water.

It is the boat that carried people out of southern China ( Fujian, Guangdong) during the famine
years , hunger behind them and the South China Sea in front
 to Penang, to Ipoh, to the tin mines and the rubber estates. Almost every
Malaysian Chinese family begins with somebody getting into one.


**The agent (XiaoChuan) is a bridge to her family, not a substitute for them.** Every
decision below is measured against that.

This is a love letter to Ah Ma.

---

## Overview of problem

**Nowadays nobody has time to listen.** 
Email, smartphones, automation, now AI. all of
them promised time back. But ask anyone if their job feels lighter. It doesn't;
the bar just moved, and everybody got busier. 

**She is lonely, and she will tell you she's fine.** The day is long and the
phone doesn't ring much. Everyone who knew her as a young woman is gone, so
there's nobody left who remembers the same things she does. She isn't unusual,
elderly isolation is big enough that health services now deploy AI phone
companions at national scale (CareCall, CHI 2023).

### Inspiration

My grandmother came from China. She worked hard her whole life just to put food
on the table and raise my parents. Then my parents grew up, moved to the city,
built their own lives there. That's just how it goes , one generation moves so
the next one can move further.

And then somewhere along the way, I grew up too. Went to college, and then
suddenly I'm an adult, and it's like everything hits you at once. Work,
bills, deadlines. I don't even notice it
happening. One day after work, I just realised I haven't called home in
weeks.

Not because I don't love them. I'm just drowning, a little, in my own
life.

And so the stories sit there. The name she used to call my grandfather when no
one else was around. The song she used to hum while cooking, that I can still
hear but couldn't tell you the name of. Little things. **Things you don't think
to ask about until there's no one left to ask.**

Guess we all know that thing in the movie **Coco**, that you're only really gone once nobody
remembers your name? I always thought it was just a nice line for a kids' movie.

But it's true, isn't it.

**She doesn't disappear when she passes. She disappears the day nobody can
answer a question about her anymore.**


### Who is this for, and what value does it bring?

**The teller (80+):** turns her from someone who is *checked on* into someone
who is *listened to*. One button. No app, no login, no menu. Being heard is
itself the point.

**Her son (45, two hours away):** leaves a question in ten seconds . in his
own recorded voice if he wants , and it reaches her *in his name*. Her stories
come back on a map. If something is wrong, he is told.

**Her granddaughter (20):** inherits an archive made of her grandmother's
actual sentences, not a machine's summary of them.
 
**The whole family:** stories pinned where they happened, clustered into
named chapters of her life, each one openable down to the words she said.

---

## Solution highlights

**AI companionship calls** — Xiao Chuan phones and talks with her for as long as
she likes, in her own pace and her own language. It opens with a real question
from her family, by name, and it never interrupts her.

**Memory that lasts** — every call is remembered. The
fifteenth call is not the first call: it picks up the story she left unfinished,
remembers who her neighbours are, and knows what she would rather not discuss.

**Automatic memory generation** — each call becomes a story card in her own
words, with a short letter written back in her voice and a generated image built
from the one sensory detail she gave.

**A family memory map** — every story pinned where it happened, from the rubber
estate to the coffee shop to the market. Pins show plainly which places she
named herself and which the system guessed.

**Chapters of her life** — the people and places that keep appearing together
become named chapters, so a grandchild can read "the coffee shop years" rather
than browse a database.

**Quiet care, reported the right way** — if she mentions a fall or that life
feels not worth living, her son is told, and she is told plainly that he is
being told. The agent never counsels her and never reports her behind her back.

**Consent she can use mid-sentence** — "don't write that down" and "forget that"
work as spoken instructions during the call. She never has to find a settings
screen.

**Family circle** — relatives browse her map, leave her questions, and correct a
misheard name or a wrong place. Cross-generational company, even at a distance.

**It earns its way inward** — it does not ask an eighty-year-old about the hard
years on the first call. Subjects are ranked and gated by how many times she has
talked: food and childhood immediately, how she and her husband met by the third
call, hardship not until the sixth. 

**It listens to how she sounds, not only what she says** — a second model reads
her pace, her pauses and her tone while the conversation runs. If she is tiring,
the agent shortens its own turns and opens no new subjects before she has to say
she is tired. 

**Not every story reaches the map** — a story needs a place and a time she
actually gave, plus four of six details, before it becomes a pin. That test is
arithmetic in code, not a judgement made by a model, and a story that falls short
records exactly which pieces were missing — which is how the next call knows what
to ask her.

---

## Key differentiators

| Compared with | Their problem | What Sampan does differently |
|---|---|---|
| **Traditional ghostwritten memoirs** | Expensive, one-shot, and the interviewer leaves | A relationship that continues; the archive grows every call |
| **Voice recorders / call recording** | Recorded but never listened to; nothing is passed down | Every call becomes a story, a map pin and a letter |
| **General chatbots with memory** | The conversation ends and the artifact is a chat log | The artifact is a family map, addressed outward |
| **Managed memory services** | Consolidate toward one current "best" fact | Both tellings kept; every fact carries **her sentence** |
| **Memoir apps aimed at the family** | The elder is a subject others write about | The elder is the author |
| **Social feeds / short video** | Assume app fluency an eighty-year-old may not have | Zero interface. One button. No login. |
| **Human befriending services** | One-to-one; cannot scale | One service, many households — while refusing to replace the son |

## Technical architecture

| Module | Solution |
|---|---|
| **Voice conversation** | `gemini-live-2.5-flash-native-audio` — duplex audio, interruption, five agent tools |
| **Agent runtime** | Google ADK 2.7.0 |
| **Story + fact extraction** | `gemini-3.7-flash` — two separate passes with separate schemas |
| **Contradiction judgement** | `gemini-3.7-flash`, temperature 0.0 — decides whether the world changed or her account did |
| **Card imagery** | `veo-3.1-fast-generate-001`, queued off the call path|
| **Affect monitoring** | Runs on the audio in parallel; raises flags to family, never speaks to her |
| **Call opening** | Deterministic — candidates scored, depth gated on trust, and the plan voided the moment she leads |
| **Pinnability** | Six fields, `where` and `when` mandatory, four of six pins. Computed in code, never asked of a model |
| **Memory store** | Firestore (asia-southeast1) — bi-temporal graph, valid time and transaction time kept apart |
| **Retrieval** | BM25 + two-hop graph search + reciprocal rank fusion.|
| **Place resolution** | Explicit precision scale; anything vaguer than a street is drawn as provisional |
| **Screening** | Cloud DLP on every transcript *before* anything is written |
| **Scheduled work** | Cloud Scheduler → weekly chapter refresh, the only work not caused by a call |
| **Service** | FastAPI on Cloud Run (asia-southeast1), 3600s timeout so a call is never cut off |
| **Frontend** | React PWA. Teller side: one button, nothing under 22px, no touch target under 64px |

---

## Academic references

**Jo et al., CareCall (CHI 2023, ~330 citations)** — national-scale LLM phone
companion for isolated elderly people. Reports reduced loneliness *and*
over-attachment, expectation gaps and unintended disclosure. Produces the bridge
thesis and the consent tools.

**Lazar et al. (2014, ~315 citations)** — systematic review of reminiscence
technology: works as a conversation catalyst, fails as a replacement for a
person.

**de Wynter (ACL 2025)** — engagement does not equal welfare.

**Zep / Graphiti (arXiv 2501.13956)** — bi-temporal knowledge graphs. Gives the
two clocks, and the finding that entity communities drift and need periodic
refresh.

**Mem0 (Chhikara et al., 2025, ~830 citations)** — the deployed reference for
memory updates, criticised because conflict resolution is *"LLM decides, not
principled."* Sampan narrows the question so the answer selects which clock
moves.

**MemoryBank (Zhong et al., AAAI 2024, ~1,250 citations)** — applies the
Ebbinghaus forgetting curve as memory decay. **Sampan deliberately does not
implement decay:** elderly users expect and reward indefinite memory, and a
policy that improves a benchmark can damage the relationship. Forgetting here is
something she asks for, never something a curve does to her.

**Pink et al. (2025)** — structured records lose sequence, context and affect.
Hence an index that always points back into her raw words.

**TrustGraph** — retrieval explainability. Every search stores its trace: what
was scored, what was returned, and what was passed over.
