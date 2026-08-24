# Inside the memory — demo script

Three things you can do to a knowledge graph: **retrieve**, **create**, **update**.
This panel does all three through the same code the Companion calls mid-call,
with the working shown at every stage, and writes nothing.

Every number below was measured against the real archive by replaying this exact
sequence. If the screen disagrees with the page, trust the screen and fix the page.

**Setup:** load the page, let the map finish drawing, *then* click **Inside the
memory**. It opens on the right question already. The three suggestion pills are
the three beats, so the whole demo is five clicks and one typed sentence.

---

## Run sheet

| # | Beat | Action | Time |
|---|------|--------|------|
| 1 | Retrieve | nothing — it opens on the query | 30 s |
| 2 | The empty case | pill → `who is Ah Seng` | 20 s |
| 3 | Create | pill → back to the coffee shop, **Create**, type, Enter | 35 s |
| 4 | Update | pill → `who lived in Sungai Siput`, **Update**, click row 1 | 35 s |
| 5 | Close | Reset | 10 s |

**Total 2 min 10 s.** A 60-second cut is at the bottom.

---

## 1 · RETRIEVE — "it found him by his role"

**Do:** nothing. The panel opens on `what did her father do at the coffee shop`.

### Key point A — grounding is not string matching

Point at stages 1 and 2.

> Seven words kept, two thrown away. From those words it found two entities.
> `coffee shop` it found by name. But **Lim Ah Hock is her father, and she never
> says his name** — she says "my father." The graph knows who that is, so the
> question lands on him.

On screen: `7 terms kept · 2 ignored` — `2 named · 6 reached within 2 hops · 18
edges held` — `17 nodes · 16 edges`. The two amber dots at the centre are the
seeds; every ring outward is one more hop.

### Key point B — the graph changes the answer, and you can watch it

Point at rows 2 and 3.

| # | bm25 | hops | rrf | fact |
|---|------|------|-----|------|
| 1 | 4.47 | 0 | 0.0328 | Her father toasted buttered bread over a charcoal fire every morning at the coffee shop. |
| 2 | 3.83 | 0 | 0.0320 | Her father opened a coffee shop in Ipoh on Jalan Bandar in 1958. |
| 3 | **4.25** | **1** | 0.0315 | Her mother cooked food at the back of the coffee shop. |

> Row three scores **higher** on keywords than row two — 4.25 against 3.83. It
> still ranks below it, because row two sits on an entity the question named and
> row three is one hop away.
>
> **A keyword search would have put those in the other order.** That is the graph
> doing work, in numbers, on screen.

### Key point C — this is why the numbers are worth showing

> There is no model anywhere in this path. Type the same question again and every
> number is identical. That is the only reason I can put the working in front of
> you — a retrieval step that asks an LLM to pick the edges cannot promise that.

The rows marked `—` were scored and rejected. Say so: they are the more useful
half, because they show what the ranking weighed, not just what it picked.

---

## 2 · The empty case (do not skip this)

**Do:** click the pill **`who is Ah Seng`**.

Everything empties — `0 named · 0 scored`, no nodes. The rings stay drawn, so it
reads as a search that ran, not a panel that broke.

### Key point D — "found nothing" and "lost it" must look different

> The archive has never heard of Ah Seng. From outside, that looks exactly like a
> search that ran and dropped him — and that is the failure nobody forgives,
> because they cannot tell which one happened. Here you can.

### Key point E — the honorific problem

Point at the struck-through `ah`.

> This is why anything under three letters is thrown away. An archive full of Ah
> Chwee and Ah Fatt and Ah Gong — keep "ah" and asking about **Ah Seng returns Ah
> Chwee**, confidently and wrongly.

---

## 3 · CREATE — an edge has to earn its rank

**Do:** click the pill **`what did her father do at the coffee shop`**. Click
**CREATE**. Type the sentence (it is the placeholder, so you can read it off the
screen) and press Enter:

```
Ah Fatt drank his kopi at the coffee shop every afternoon.
```

### Key point F — an invented fact lands on a real node

> I gave it one sentence. It found `coffee shop` inside it and hung the new edge
> there — the same lexical grounding the question uses. Scored went **16 → 17**,
> the drawing went **17 nodes → 18**, and the dashed edge is the new one.

### Key point G — no special treatment for being new

| # | bm25 | fact |
|---|------|------|
| 4 | 2.91 | Her father ran Ah Gong's shop until it closed in 1969. |
| **5** | **3.20** | **Ah Fatt drank his kopi at the coffee shop every afternoon.** |
| — | 2.05 | Her father toasted bread over charcoal every morning. |

> It came in at **rank 5**. It was not put at the top for being new — it competed
> with everything she actually said. And look at the row below it: adding this
> fact **pushed a real one out of the top five**. That is a live ranking, not a
> list with an insert.

---

## 4 · UPDATE — two clocks

**Do:** click the pill **`who lived in Sungai Siput`**. Click **UPDATE**.
Rank 1 is `Ah Chwee lives in Sungai Siput.` (bm25 5.20). **Click that row.**

> Say she tells us next month that Ah Chwee moved to her daughter's place in Ipoh.
> The old telling does not get deleted.

**On screen:** scored **9 → 8**, edges held **19 → 18**. The row leaves the
ranking; `She grew up on a rubber estate in Sungai Siput` takes rank 1. The
retired statement reappears at the bottom under **4 · NO LONGER ASSERTED**, and
the edge is still in the drawing, greyed and dashed.

### Key point H — valid time and transaction time are different clocks

> It moved in **transaction time** — the archive stopped asserting it. Her own
> dates are untouched, because **valid time** is what *she* said, and she was not
> wrong. She was right in 1952 and she is right now.

### Key point I — this is why the archive can hold a person changing

> A flat index cannot tell you what it stopped believing. This is the only reason
> the archive can hold thirty years of someone's memory shifting without quietly
> overwriting them — and without ever recording that she made a mistake.

---

## 5 · Close — nothing here is written

**Do:** point at **RESET · 2 CHANGES**, then at the subtitle top-left:
*Siew Khim's graph · nothing here is written.* Click Reset. Everything returns.

### Key point J — the rule the whole product rests on

> Nothing I just did touched her archive. The sandbox rides on the request and
> dies with it. That is deliberate: **the family may correct the system, and never
> her.** A demo that let a stranger write sentences into an eighty-year-old's
> memory would break the exact promise the thing is built on.

---

## The 60-second cut

Keep **B** and **H**. They are the two claims nothing else in the project makes.

1. **(30 s)** It opens on the coffee shop question. Rows 2 and 3: higher keyword
   score, lower rank, because of graph distance. Then: no model in this path,
   same numbers every time.
2. **(30 s)** Pill → `who lived in Sungai Siput` → **Update** → click row 1. It
   leaves the ranking; it does not leave the archive. Transaction time moved, her
   dates did not. Land on *nothing here is written*.

---

## Key points, condensed

| | The line |
|---|---|
| A | It found her father by his role, not his name |
| B | Higher keyword score, lower rank — the graph reordered it |
| C | No model in this path, so the numbers are identical every run |
| D | "Never heard of him" must not look like "lost him" |
| E | Under three letters is dropped, or Ah Seng returns Ah Chwee |
| F | An invented edge lands on a real node |
| G | It entered at rank 5 and pushed a real fact out of the top five |
| H | Transaction time moved; her valid time did not |
| I | A flat index cannot report what it stopped believing |
| J | The family may correct the system, and never her |

---

## If you have longer

`what happened at Ah Gong's shop in Ipoh` finds **three** entities in one
sentence — the shop, Lim Cheong Hin (Ah Gong himself), and Ipoh — and its rank 1
scores 1.23 on BM25 against rank 2's 3.46. A starker version of key point B, but
a busier drawing, so it is the alternate rather than the opener.

---

## Questions to expect

**"Is the ranking an LLM?"**
No. BM25 for lexical match, breadth-first hops for structure, reciprocal rank
fusion to combine them. Deterministic end to end — which is why the numbers are
on screen at all.

**"Did the BM25 scores just change?"**
Yes, and that is a good catch — 5.07 became 5.20 after the create. Adding a
document changes the corpus statistics BM25 is computed from. The scores are
recomputed, not stored.

**"What happens when it gets it wrong?"**
Two answers. The rejected rows are visible, so you can see what it weighed. And
the family can retire a fact — that is beat 4. The correction path is part of the
product, not an admin screen.

**"Why not embeddings?"**
Nothing forbids them; RRF takes another ranking happily. These two come first
because they are inspectable, and on a few hundred facts about one family, a name
matching a name is a strong signal.

**"Can I break it by typing anything?"**
Please do. A sentence naming nobody invents a node instead of attaching itself to
a real one, so it floats unconnected — the honest picture. And none of it is
written down.

---

## If something goes wrong live

- **The panel does not open on the first click.** Click again. Load the page and
  let the map settle before you start.
- **A number does not match this page.** Say the number on the screen. The claim
  is the *relationship* between the numbers, not their absolute value.
- **You lose your place in the sandbox.** Reset, top right. It always returns to
  her archive as it actually is.
