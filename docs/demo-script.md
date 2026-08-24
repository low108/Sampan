# Inside the memory — demo script

Every number below was measured against the real archive on the day this was
written. If a number on screen disagrees with a number here, trust the screen
and fix this file.

**Setup:** open Sampan, click **Inside the memory**. It opens on the right
question already. Have nothing else to prepare — the three suggestion pills are
the three beats, so the demo is four clicks and one typed sentence.

**Total: 2 min 40 s.** A 60-second cut is at the bottom.

---

## Beat 1 · Grounding — "it found him by his role" (30 s)

**Do:** nothing. It opens on `what did her father do at the coffee shop`.

**Point at stage 1 and stage 2.**

> Seven words kept, two thrown away. And look at what it found from those
> words — two entities. `coffee shop` it found by name. But `Lim Ah Hock` is
> her father, and she never says his name. She says "my father." The graph
> knows who that is, so the question lands on him.

**Numbers on screen:** 7 terms kept · 2 ignored · **2 named** · 6 reached
within 2 hops · 18 edges held · 17 nodes.

The two amber dots at the centre of the drawing are those two entities. Every
ring outward is one hop further from the question.

---

## Beat 2 · Focus — the line that makes the whole case (40 s)

**Do:** point at rows 2 and 3 of the score table.

| # | bm25 | hops | rrf | fact |
|---|------|------|-----|------|
| 1 | 4.47 | 0 | 0.0328 | Her father toasted buttered bread over a charcoal fire every morning at the coffee shop. |
| 2 | 3.83 | 0 | 0.0320 | Her father opened a coffee shop in Ipoh on Jalan Bandar in 1958. |
| 3 | **4.25** | **1** | 0.0315 | Her mother cooked food at the back of the coffee shop. |

> Row three scores higher on keywords than row two — 4.25 against 3.83. It
> still ranks below it. Because row two is sitting on an entity the question
> named, and row three is one hop away.
>
> A keyword search would have put those in the other order. This is the graph
> changing the answer, and you can watch it happen.

**Then, the reason any of this is worth showing:**

> There is no model in this path. Type the same question again and every one of
> these numbers is identical. That is why I can show you the numbers at all — a
> retrieval step that asks an LLM to pick the edges cannot promise you that.

Rows marked `—` were scored and rejected. Say so — they are the more useful
half, because they show what the ranking weighed, not just what it picked.

---

## Beat 3 · The empty case (20 s)

**Do:** click the pill **`who is Ah Seng`**.

Everything empties. 0 named, 0 scored, nothing drawn.

> The archive has never heard of Ah Seng. From the outside that looks exactly
> like a search that ran and dropped him — which is the failure people don't
> forgive, because they can't tell the difference. Here you can.

**Then point at the dropped chip `ah`:**

> And this is why anything under three letters is thrown away. An archive this
> small, full of Ah Chwee and Ah Fatt and Ah Gong — keep "ah" and asking about
> Ah Seng returns Ah Chwee, confidently and wrongly.

---

## Beat 4 · Create — an edge has to earn its rank (35 s)

**Do:** click the pill **`what did her father do at the coffee shop`** to go
back. Click **CREATE**. Type into the sentence box (it is the placeholder, so
you can read it off the screen):

```
Ah Fatt drank his kopi at the coffee shop every afternoon.
```

Press Enter.

> I gave it a sentence. It found `coffee shop` inside it and hung the new edge
> there — same lexical grounding the question uses. Scored went 16 to 17, the
> drawing went 17 nodes to 18, and the dashed edge is the new one.

**Then the part that matters:**

> It came in at **rank 5**, on a BM25 of 3.20. It did not get put at the top for
> being new. It competed with everything she actually said, and that is where it
> landed.

---

## Beat 5 · Update — two clocks (35 s)

**Do:** click the pill **`who lived in Sungai Siput`**. Click **UPDATE**.
Rank 1 is `Ah Chwee lives in Sungai Siput.` Click that row.

> Say she tells us next month that Ah Chwee moved to her daughter's place in
> Ipoh. The old telling doesn't get deleted.

**What happens on screen:** scored 9 → 8. The row leaves the ranking. It
reappears at the bottom under **4 · NO LONGER ASSERTED**, and the edge is still
in the drawing, greyed.

> It moved in *transaction time* — the archive stopped asserting it. Her own
> dates are untouched, because *valid time* is what she said, and she was not
> wrong. She was right in 1952 and right again now.
>
> A flat index can't tell you what it stopped believing. This is the only reason
> the archive can hold thirty years of a person changing their mind without
> quietly overwriting them.

---

## Beat 6 · Close (10 s)

**Do:** point at **RESET · 2 CHANGES**, then the subtitle at the top left:
*Siew Khim's graph · nothing here is written.*

> Nothing I just did touched her archive. The sandbox rides on the request and
> dies with it. That is deliberate — the rule in this product is that the family
> may correct the system, and never her. A demo that let a stranger write
> sentences into an eighty-year-old's memory would be breaking the exact promise
> the thing is built on.

Click Reset. Everything returns.

---

## The 60-second cut

If you only get a minute, keep Beat 2 and Beat 5. They are the two claims
nothing else in the project makes.

1. **(30 s)** It opens on the coffee shop question. Point at rows 2 and 3:
   higher keyword score, lower rank, because of graph distance. Then: no model
   in this path, same numbers every time.
2. **(30 s)** Pill → `who lived in Sungai Siput` → UPDATE → click row 1. It
   leaves the ranking, it does not leave the archive. Transaction time moved,
   her dates did not. Finish on *nothing here is written*.

---

## If you have longer

`what happened at Ah Gong's shop in Ipoh` finds **three** entities in one
sentence — the shop, Lim Cheong Hin (Ah Gong himself), and Ipoh — and its rank
1 has a BM25 of 1.23 against rank 2's 3.46. An even starker version of Beat 2,
but a busier drawing, so it is the alternate rather than the opener.

## Questions you should expect

**"Is the ranking an LLM?"**
No. BM25 for lexical, breadth-first hops for structure, reciprocal rank fusion
to combine them. Deterministic end to end — that is why the numbers are on
screen.

**"What happens when it gets it wrong?"**
Two things. The rejected rows are visible, so you can see what it weighed. And
the family can retire a fact, which is Beat 5 — the correction path is a
first-class part of the product, not an admin screen.

**"Why not just use embeddings?"**
Nothing here forbids them; RRF takes another ranking happily. The reason to
start with these two is that they are inspectable, and on an archive of a few
hundred facts about one family, a name matching a name is a strong signal.

**"Could I break it by typing anything?"**
Please do. A sentence naming nobody invents a node rather than attaching itself
to a real one — it will float, unconnected, which is the honest picture. And
none of it is written down.
