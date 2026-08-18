# Design brief — Sampan, second pass

**For Claude Design. Draw the UX/UI flow. Do not build it.**

The current app works and looks like a prototype. This brief asks for a visual
and structural redesign in the manner of **chngmkr.com**, whose aesthetic the
client has chosen as the reference.

---

## 1. What the product is

**Sampan** is a voice companion that telephones an elderly woman, listens to her
life stories, and turns them into an archive her family can walk through.

It has **two audiences with opposite needs**, and that tension is the central
design problem:

| | **She** (Lim Siew Khim, 80, Ipoh) | **They** (her son 55, granddaughter 19) |
|---|---|---|
| Device | Android phone, held close, poor eyesight, deaf in one ear | Phone or laptop, browsing at night |
| Session | 10 minutes, voice, one decision at a time | 3 minutes, scrolling, exploring |
| Needs | Enormous targets, plain words, almost nothing on screen | Density, beauty, discovery |

**The elder side must not inherit the reference aesthetic wholesale.** More on
this in §5 — read it before drawing her screens.

The thesis the design must carry: *the agent is a bridge to her family, not a
substitute for them.* Every time the app shows something a family member asked,
it says who asked. The agent never takes credit.

---

## 2. The reference: chngmkr.com

Investigated directly. These are its actual tokens, not an approximation.

### Colour

```
--cream        #FCFBF9    page ground
--ink          #1A1A1A    primary text
--ink-2        #0E0F0C    near-black, for dark surfaces
--body         #3A3530    body copy
--muted        #9A9588    secondary text, metadata
--accent       #E7FE54    lime — the only saturated colour
--accent-press #D6ED44
--klein        #002FA7    Klein blue, used sparingly
--line         rgba(26,26,26,0.12)
```

Near-white paper, near-black ink, **one** electric lime accent, and a great deal
of restraint. Colour is an event, not a decoration.

### Type

| Role | Face | Treatment |
|---|---|---|
| Labels, nav, metadata | **DM Mono** | 10.5px, UPPERCASE, letter-spacing ~1.5px |
| Titles, UI, buttons | **GT America** (or a grotesque with a condensed bold) | Tight, confident, often uppercase |
| Body, quotes | **Georgia / Times** | Serif, generous line-height, for reading |

The mono-uppercase-letterspaced label is the signature move. It appears
everywhere: nav items, tags, section headings, entry counts, keyboard hints.

### Shape and surface

- Buttons and tags are **fully round** (`border-radius: 999px`)
- Cards are softly rounded, roughly 24px
- Hairline borders at 12% ink, never heavy
- Generous negative space; the page is not afraid to be empty

### Two mechanics worth stealing

1. **Photography is black and white until it is active**, then it blooms into
   colour. Applied to the grid, this makes browsing feel alive without any
   motion.
2. **Full-bleed grid, no gutters.** Tiles touch. Titles sit *on* the image,
   bottom-left, with a small tag pill beneath.

### The detail card (study this closely)

Its anatomy is almost exactly what a Sampan story wants:

```
┌──────────────────────────────────────────┐
│  ♡                                    ×  │
│           [ hero image, colour ]         │
│                                          │
│  DHAKA · BANGLADESH        ← mono eyebrow│
│  SOLshare                  ← large title │
├──────────────────────────────────────────┤
│  (tag) (tag) (tag)            ( ↗ SHARE )│
│                                          │
│  ⊙  ┌────────────────────────────────┐   │
│     │ "Letting neighbors share their │   │
│     │  solar power…"                 │   │
│     └────────────────────────────────┘   │
│     CURATED BY FLORIAN GUILLAUME         │
│                                          │
│  [   ENGAGE   ]  (  MEET SOLSHARE →  )   │
│                                          │
│  DESCRIPTION               ← mono label  │
│  The world's first peer-to-peer solar…   │
└──────────────────────────────────────────┘
```

A filled lime primary and an outlined secondary, side by side. A pull quote in a
bordered box with the attributed person's face beside it. Tiny mono section
labels. Serif body.

---

## 3. What this maps onto

The story card writes itself:

| chngmkr | Sampan |
|---|---|
| `DHAKA · BANGLADESH` | `JALAN BANDAR, IPOH · 1958–1969` |
| `SOLshare` | *The last cup of Milo* |
| tag pills | the subject, and how certain the place is |
| pull quote + curator face | **her sensory detail, in her own words**, with her face |
| `CURATED BY FLORIAN GUILLAUME` | `TOLD BY LIM SIEW KHIM · CALL 4` |
| `ENGAGE` / `MEET SOLSHARE →` | `ASK HER ABOUT THIS` / `SEE ON THE MAP →` |
| `DESCRIPTION` | `HER WORDS` |

The pull quote is the most important element on the card. It is the one thing on
the screen that is hers, verbatim, and the whole product is arranged around
protecting it.

---

## 4. Screens to draw

### The family side — apply the reference fully

**A. Household** — who is in this family. Faces, names, relation, how much each
has told. The entry point.

**B. The map** — her stories placed geographically. Currently a Leaflet map with
clustered pins. The reference site's home screen is a dark globe with numeric
clusters and a mono instruction legend in the corner — that treatment would suit
this well. Pins carry a certainty state (see §6). A persistent bar shows stories
that have **no place at all**; it must never be hidden.

**C. Story card** — the detail modal above, opened from a pin.

**D. Cluster sheet** — several stories share one dot; list them so every one
stays reachable.

**E. Her chapters** — communities the system found in her archive, unwritten by
anyone: *Ah Gong's Jalan Bandar coffee shop*, *the Sungai Siput estate
childhood*, *Lim Cheong Hin's arrival at Penang*. Each opens down to the facts
inside it and then to her sentences. The full-bleed editorial grid is the right
home for these.

**F. Ask about her** — a conversational panel. Ask a question, get an answer
assembled only from things she said, with the option to turn any answer into a
question for her next call.

**G. Leave a question** — a short form. Emphasise that the agent will say who
asked.

**H. Notifications** — a bell. The one that matters reads *"Wei Lun asked you
something"*.

### Her side — the reference aesthetic does **not** apply

**I. Waiting** — almost empty. One enormous button. If someone has left her a
question, it is on screen in large plain type with their name.

**J. Recording** — she is talking. The screen should be quiet and show that it
is listening. Nothing to press except *that's enough*.

**K. A question arrives** — her son's face, his question in large type, one
action.

---

## 5. Constraints that override the reference

These are not preferences. Breaking them breaks the product.

1. **Nothing below 22px on her screens.** The reference's 10.5px letterspaced
   mono is beautiful and illegible to someone with presbyopia. Her screens use
   large plain type, and mono labels only as decoration she never needs to read.
2. **Touch targets on her screens are at least 64px.**
3. **No senior mode.** No grey-haired iconography, no patronising copy, no
   separate "accessible" theme. She gets the same product, sized for her.
4. **Uncertainty is drawn, never explained.** A place the system guessed looks
   different from a place she named. It must be obvious without reading.
5. **Absence is a place on the page.** Stories with no location get a permanent,
   tappable line — never a silent omission.
6. **Correction lives inside the thing.** Fixing a wrong pin happens on the story
   card. There is no settings screen.
7. **The family may correct the system, never her.** They can fix a geocoding
   error. They cannot edit what she said. Nothing in the UI should suggest
   otherwise.
8. **Say who asked.** Any family question shown to her carries their name.

---

## 6. States that need a visual language

Design these as a set, not one at a time:

| State | Where it appears |
|---|---|
| **She named this place** | confident pin, filled |
| **The system guessed this place** | provisional pin — hollow, dashed; a plausible wrong pin is worse than an obviously uncertain one, because nobody corrects what looks right |
| **No place at all** | the tray. Two of her best stories are here |
| **Year unknown** | *"year not yet told"* — never a guessed date |
| **She told it differently later** | both tellings kept; the older one visibly retired, not deleted |
| **Held back** | something she asked to keep private |
| **Unfinished** | a subject she started and did not finish; this is what the next call opens on |

---

## 7. Deliverables

1. **A flow diagram** of both journeys — hers and theirs — showing where they
   meet. They meet in exactly two places: a question she is asked, and a story
   they read.
2. **Screens A–K** as high-fidelity frames, phone-first, with desktop shown for
   the map and chapters.
3. **The state set from §6** drawn as a small visual language sheet.
4. **A type and colour sheet** adapting the reference tokens, including the
   larger scale used on her screens.

---

## 8. Two notes on tone

The reference site is about **changemakers** — outward-facing, ambitious, a
little cool. Sampan is about **an eighty-year-old woman remembering a coffee
shop that closed in 1969**. Borrow the reference's restraint, its typography and
its confidence with empty space. Do not borrow its swagger.

And the lime accent: on the reference it means *act, engage, join*. Here it
should mean **something of hers is new** — a story just arrived, a question is
waiting. Reserve it. If it appears on every screen it means nothing.
