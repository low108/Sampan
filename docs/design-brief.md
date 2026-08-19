# Design brief — Sampan

*Paste this whole file into Claude Design (or hand it to a designer). It is written to be
used as a single prompt.*

---

Design the UI/UX for **Sampan** — a voice companion that collects a family's life stories and
puts them on a shared map.

## Who uses it — and this is the central design tension

The same app is used by an **80-year-old grandmother** in Ipoh, Malaysia and by her
**19-year-old granddaughter**.

Ah Khim will not read small text, will not navigate nested menus, and has never used an app
that isn't WhatsApp. Xin Yi expects a modern app and does not read Chinese. Both must feel it
was built for them.

**One app, one navigation, for both.** No mode switch, no "senior mode" toggle. The same
screens must work for an eighty-year-old and a teenager. This is the hardest problem in the
brief and the thing to solve first.

Everything is bilingual Chinese/English — Chinese leading for her, English legible for the
grandchildren.

## What it does

An AI companion called **Xiao Chuan** ("little boat") talks with family elders and listens to their
life stories. Afterwards it turns each story into a record with a place, a time, the people in
it, and one concrete sensory detail — then pins it to a shared family map.

Family members can leave a short voice message asking about something. The agent raises it on
the next call, always crediting who asked: *"Wei Lun was asking about…"*

The tone is warm, unhurried, domestic. Not clinical, not a productivity app, and **not** a
"memories" app with sepia and film grain. Think a kitchen table.

---

## Information architecture — build exactly this

### Main app: three tabs, left to right, plus a notification bell top right

**1. MAP** *(default)*
An interactive map — pan, zoom, real tiles — showing story pins from every family member.
Tapping a pin opens a story card. Filtering by person is a later phase: design for it, don't
foreground it.

**2. RECORD**
One large button. Anyone can record at any time, not only when asked. This is the screen Ah
Khim will live on, and it must work as a standalone destination rather than a feature buried
inside a map app.

**3. FAMILY**
Family member profiles as a browsable list. Tapping a member opens their page, which itself
has three tabs:

- **CHAT** — an agent that knows this person and answers questions about them
  (*"where did Ah Ma grow up?"*, *"what did her father do?"*)
- **MAP** — only that person's stories, same map component, scoped
- **ASK** — leave them a short voice message or question

### Notification bell (top right, global)

Shows when someone has left a message for you, or when new stories arrive. Tapping a
*"someone asked you something"* notification **starts a recording session with that question
already loaded as context**.

### Timeline — on demand only

There is no permanent timeline tab. A chronological view of one person's life is generated
when a family member asks for it from that person's page. Design how it is requested and how
it arrives.

---

## Real data to design against

Do not invent prettier data. This is one grandmother, four conversations, eleven stories.

```
"The coffee shop on Jalan Bandar"          1958
sensory detail : bread toasted over charcoal, with butter
place          : Jalan Bandar, Ipoh  (street precision)
people         : my father
still missing  : why it mattered

"The last cup of Milo"                     1969
sensory detail : the day he closed, he gave me a cup of Milo
place          : father's shop -> linked to Jalan Bandar
people         : my father

"White rice with soy sauce in the line house"   1952-1956
sensory detail : white rice with soy sauce
place          : line house -> linked to the estate, Sungai Siput  (town precision, provisional)
people         : my mother, my sister

"Mother's black Singer sewing machine"     no year known
sensory detail : the clatter of it
place          : home  (cannot be located at all)
people         : my mother

"Grandfather came south by boat to Penang" no year known
place          : Yongchun, Fujian  (region precision, provisional)
```

Sensory details are in her own words, verbatim. Years are often a range,
and frequently have only one open end — *"before I married"* means *sometime before 1968*.

---

## The map problems you must solve

These are measured from the real data, not hypothetical.

**Scale.** One pin sits in Fujian, China. Six sit in Perak, Malaysia — 2,300 km away. A single
view containing both makes the Malaysian cluster a single dot.

**Density.** Three of those Perak pins — the coffee shop, the room above it, and the railway
station where the wedding photo was taken — are within a few hundred metres of each other. At
any usable zoom they overlap.

**Certainty.** Places carry a precision: `exact`, `street`, `town`, `region`, `unknown`. A
town-level pin is often **wrong** — *Sungai Siput* resolved to a town ninety kilometres from the
one she meant. A plausible wrong pin is worse than a visibly uncertain one, because **nobody
corrects what looks right.** Design a visual language for certain / provisional / unplaceable.

**Linked places.** Some pins were placed by joining a relational name to somewhere she named
in a *different* conversation — *"my father's shop"* sits on Jalan Bandar because she said so
six weeks earlier. These carry the sentence that placed them:

> "Later he saved a bit of money, nineteen fifty-eight he opened a coffee shop in Ipoh, at
> Jalan Bandar."

A pin that can show *why it is there, in her own words* is a nicer artifact than a coordinate.
Design for it.

---

## Absence — smaller than it looks, not solvable by hiding

Two of eleven stories have no place at all: *"Mother's salted fish fried rice"* and *"Mother's
black Singer sewing machine"*, both located only as *home*. She never said which house, across
four conversations, and the system deliberately refuses to guess.

Both score 6/6 on completeness. The sewing machine's sensory detail is *the clatter of it* — the
sound of her mother sewing for money at night, which she fell asleep to. It is one of the best
things in the archive and it cannot go on a map.

**Update, after the archive was rebuilt in English.** Both of these now *do* get placed. She
described the house itself in an earlier session — "that house is one long row, one room one
room, they call it line house" — and the linker joined *home* to the line house on the strength
of that sentence. The refusal to guess is intact; there simply turned out to be evidence.

So the unplaceable state currently has no story in it. **Design it anyway.** It is not
hypothetical: it is one sentence away, it is the state that keeps the map honest, and an
archive that never shows it is an archive quietly pretending it knows everything. The empty
tray is a fact about this grandmother, not a property of the system.

Design where it lives. It must be **fully present on the person's page**, and the map should
**acknowledge it rather than omit it**. Do not place it approximately. The family correcting
it later is a feature, not a fallback.

---

## What not to include

**No corrections or admin tab in the main navigation.** Fixing a wrong name or a wrong place
should be possible from the thing itself — inside a story card, inside a pin — never as a
chore list someone has to work through.

---

## Constraints

- Mobile first, Android, portrait.
- **Elder floor:** body text ≥22pt, tap targets ≥64pt, WCAG AAA contrast, no nested
  navigation, no modals that can trap, no horizontal scrolling.
- The record button must be reachable one-handed with a thumb.
- Bilingual throughout: Chinese leading, English legible.

---

## Deliver

1. The three main tabs, at phone width.
2. The member page with its three tabs (chat, map, ask).
3. **Map states:** default, a cluster expanded, a pin's story card open, a provisional pin, a
   linked pin showing its evidence, and however unplaceable stories are acknowledged.
4. **Notification bell:** list state, and the *"someone asked you"* → record flow.
5. **Record screen:** idle, recording, and with an incoming question loaded.
6. A short written note on how the same screens serve an 80-year-old and a 19-year-old.

---

## Background, if useful

The product's thesis is that the agent is **not a substitute for family** — it is a ferry
between two generations who cannot reach each other at the same hour. The son feels a pang of
missing his mother at 2pm and cannot call; she is asleep by the time he is free. Every family
question is attributed by name, and the archive exists to give the family something to ask her
about in person.

This matters for the design: the app should feel like it is *bringing people closer*, not like
a place to go instead of calling.
