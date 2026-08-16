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

An AI companion called **小船** ("little boat") talks with family elders and listens to their
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
「板底街的咖啡店」                          1958
sensory detail : 炭火烤的面包涂牛油的味道
place          : 板底街 Jalan Bandar, Ipoh  (street precision)
people         : 我爸爸
still missing  : why it mattered

「关店的原因」                              1969
sensory detail : 关店那天他给我一杯阿华田
place          : 爸爸的咖啡店 → linked to 板底街
people         : 我爸爸

「胶园工寮里的白饭配酱油」                   1952–1956
sensory detail : 白饭配酱油
place          : line house → linked to 双溪镇树胶园  (town precision, provisional)
people         : 我妈妈, 我姐姐

「妈妈的黑色Singer缝纫机」                   no year known
sensory detail : 咔嗒咔嗒的声音
place          : 家里  (cannot be located at all)
people         : 我妈妈

「阿公坐船南来槟城」                         no year known
place          : 福建永春 Yongchun, Fujian  (region precision, provisional)
```

Story titles are in Chinese. Sensory details are in her own words. Years are often a range,
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
town-level pin is often **wrong** — 「双溪镇」 resolved to a town ninety kilometres from the
one she meant. A plausible wrong pin is worse than a visibly uncertain one, because **nobody
corrects what looks right.** Design a visual language for certain / provisional / unplaceable.

**Linked places.** Some pins were placed by joining a relational name to somewhere she named
in a *different* conversation — 「爸爸的咖啡店」 sits on 板底街 because she said so six weeks
earlier. These carry the sentence that placed them:

> 「后来他存了一点钱,一九五八年在怡保开了一间咖啡店,在板底街。」

A pin that can show *why it is there, in her own words* is a nicer artifact than a coordinate.
Design for it.

---

## Absence — smaller than it looks, not solvable by hiding

Two of eleven stories have no place at all: 「妈妈的咸鱼炒饭」 and 「妈妈的黑色Singer缝纫机」,
both located only as 「家里」 — *home*. She never said which house, across four conversations,
and the system deliberately refuses to guess.

Both score 6/6 on completeness. The sewing machine's sensory detail is 「咔嗒咔嗒的声音」 — the
sound of her mother sewing for money at night, which she fell asleep to. It is one of the best
things in the archive and it cannot go on a map.

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
