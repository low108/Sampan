# Persona Bible — 林秀琴 Ah Khim

**Purpose:** the single source of truth for all seed transcripts, demo scripts, and Firestore
fixtures. Everything the agent "knows" must trace back to this document, and everything it
*shouldn't* know yet must be marked as such.

**This family is invented.** It is structurally true to the Chinese-Malaysian migration
pattern — Fujian → rural Perak → the city — but no real person is depicted.

---

## 1. The narrator

| | |
|---|---|
| **Name** | 林秀琴 · Lim Siew Khim · called **阿琴 (Ah Khim)** by family |
| **Born** | 1946, Sungai Siput, Perak — in a rubber estate labourer's line-house |
| **Age now** | 80 |
| **Lives** | Alone in a flat in Ipoh, Perak. Her son moved her there in 2016 |
| **Language** | Mandarin primary. Scatters in English (*"okay lah"*, *"aiyo"*) and Malay (*"pasar"*, *"kampung"*, *"getah"*) |
| **Health** | Mobile, independent. Hard of hearing on the **left**. Tires after ~12 minutes of talking |
| **Temperament** | Warm, talkative once started, self-deprecating. Deflects sympathy with humour. Will not volunteer sadness — it arrives sideways, in a detail |

### Speech habits (for voicing and for tuning extraction)

- **Starts in the middle.** Rarely gives context first: *"那时候他就走了咯"* — who? when? The
  agent has to gently locate her
- **Digresses through food.** Any topic reaches food within three turns
- **Understates hardship.** *"还好啦"* means it was very bad
- **Repeats set phrases** — *"那个年代啊"*, *"你不知道啦"*, *"讲了你也不明白"*
- **Answers a different question than asked**, then circles back unprompted
- **Trails off** when a topic touches her sister or her husband — half-sentence, then a pivot
  to something practical

---

## 2. The family

| Person | Relation | Born | Died | Notes |
|---|---|---|---|---|
| 林亚福 Lim Ah Hock | Father | 1918 | 1981 | Rubber tapper, then opened the kopitiam. Strict, silent, generous |
| 陈亚娣 Tan Ah Tai | Mother | 1922 | 1998 | Cooked for the shop. Ah Khim's food memories are all hers |
| **林秀珠 Lim Siew Choo (阿珠)** | **Elder sister** | 1941 | **2019** | **The sensitive topic.** They quarrelled in 2017 and never repaired it before she died |
| 陈永发 Tan Eng Huat (阿发) | Husband | 1942 | **2015** | Lorry driver. Married 1968. She speaks of him easily and fondly — grief here is settled |
| **陈伟伦 Tan Wei Lun** | **Son** | 1970 | — | Lives in KL. Works long hours. **The one who sends the asks** |
| 陈美玲 Tan Mei Ling | Daughter | 1973 | — | Emigrated to Perth 2001. Calls at Chinese New Year only |
| **陈欣宜 Tan Xin Yi** | **Granddaughter** | 2007 | — | Wei Lun's daughter. University. **Cannot read Chinese** |
| 王亚水 Ong Ah Chwee | Neighbour, estate days | 1944 | — | Childhood playmate. Still alive, in Sungai Siput |

**Ancestral:** her grandfather **林长兴 Lim Cheong Hin** left **永春县, 福建 (Yongchun, Fujian)**
and landed at **Penang, 1928**. She never met him. This is the deepest pin on the map and she
only knows it second-hand — which makes it a *fragment* until a later session fills it in.

---

## 3. Anchor events

These resolve her relative time expressions (*"结婚以前"*, *"店关了以后"*). The agent starts
knowing **none** of them; each is discovered in the seed sessions and is what makes later
timelines sharper.

| Anchor ID | Event | Year | First revealed |
|---|---|---|---|
| `anchor_grandfather_arrival` | Grandfather lands in Penang | 1928 | Session 3 (approximate) |
| `anchor_birth` | Ah Khim born, Sungai Siput | 1946 | Session 1 |
| `anchor_shop_open` | Father opens the kopitiam, Jalan Bandar, Ipoh | 1958 | Session 2 |
| `anchor_marriage` | Marries Tan Eng Huat | 1968 | Session 2 |
| `anchor_shop_close` | Kopitiam closes | 1969 | Session 4 (partial — the *why* is withheld) |
| `anchor_first_child` | Wei Lun born | 1970 | Session 4 |
| `anchor_husband_death` | Eng Huat dies | 2015 | Session 3 |
| `anchor_sister_death` | Siew Choo dies | 2019 | **Never in seed — session 6 only** |

---

## 4. Places

| Place | Where | Story domain | Geocodable? |
|---|---|---|---|
| 永春县, 福建 | Yongchun, Fujian, China | Root | Yes — county level |
| 槟城码头 | Swettenham Pier, Penang | Journey | Yes |
| 双溪镇的树胶园 | Rubber estate, Sungai Siput, Perak | Work, Play | **Approximate only — the estate no longer exists.** Deliberate `unlocated` case |
| 板底街 Jalan Bandar | Ipoh old town | Work, Home | Yes |
| 怡保火车站 | Ipoh railway station | Love — where she met Eng Huat | Yes |
| 中央巴刹 Pasar Besar | Ipoh central market | Taste | Yes |
| 她现在的组屋 | Her flat, Ipoh | Home | Yes |

The Sungai Siput estate is intentionally unresolvable — it exercises the unlocated tray, the
family-correction path, and the next-session clarifying question.

---

## 5. Objects and foods

| Item | Type | Attached to |
|---|---|---|
| 缝纫机 (Singer sewing machine) | object | Mother; she still owns it |
| 一张黑白结婚照 | object | 1968 wedding, the only photo |
| 咖椰面包 kaya toast | food | Father's shop, 5am, charcoal grill |
| 咸鱼炒饭 | food | Mother's; what they ate when money was short |
| 阿华田 Milo | food | What her father gave her the day the shop closed |

---

## 6. Sensitive topics

| Topic | Rule |
|---|---|
| **Her sister 阿珠** | She will change the subject. Two deflections → the agent logs it and does not raise it again unprompted. **Only opens in session 6, and only because she raises it herself** |
| Why the shop really closed | She gives a practical reason (1969, business bad). The real reason — her father's debt — surfaces only late. `missing_fields: ["why"]` persists through seed |
| Her daughter in Perth | Flat affect, brief answers. Not painful enough to deflect, but never elaborated |
| Money, ever | Deflects with humour |

---

## 7. Learned preferences (accumulated across seed sessions)

These must be **derived by the pipeline**, not hand-written into Firestore. Listed here as the
expected end state after four seed sessions:

| Preference | Value | Learned in |
|---|---|---|
| `session_length` | Fades at ~11–12 minutes | S1, confirmed S3 |
| `best_time` | Mornings; flat in the evening | S2 vs S4 |
| `listen_talk_ratio` | Strongly prefers to monologue; agent turns should be short | S1 |
| `question_style` | Concrete questions work; open ones get *"讲什么?"* | S2 |
| `hearing` | Left ear weak — she asks for repeats | S1 |
| `topic_sensitive` | 阿珠 (sister) — deflected twice | S3 |
| `topic_favourite` | Food, and the estate childhood | S1, S3 |
| `pace` | Slower than default; leave 3+ seconds of silence before filling | S2 |

---

## 8. Open threads at the end of seed (what session 5 can pick up)

| Thread | State | Left off at |
|---|---|---|
| `thread_coffee_shop` | **open, incomplete** | The shop closing in 1969 — she started, then the neighbour came to the door. **This is the session 5 opener** |
| `thread_grandfather_crossing` | fragment | Knows he came from Yongchun in the 20s; no detail. Missing WHO, SENSE |
| `thread_wedding_photo` | open | Mentioned the photo, never described the day |
| `thread_estate_childhood` | rich, partially pinned | Two stories pinned; the river one is missing WHERE |

---

## 9. Expected seed state after four sessions

Targets for the pipeline to hit — use as test assertions:

| | Count |
|---|---|
| Stories **pinned** | 9–11 |
| Stories **fragment** | 4–6 |
| Entities: person | 8 |
| Entities: place | 6 (1 unlocated) |
| Entities: food | 4 |
| Entities: object | 3 |
| Open threads | 4 |
| Anchors resolved | 6 of 8 |
| Countries on the map | 2 |
| Decades spanned | 1928–2015 |

---

## 10. The agent — 小船 Xiao Chuan

| | |
|---|---|
| **Name** | 小船 (Xiao Chuan) — "little boat" |
| **Persona** | Grandchild-figure. Young, warm, unhurried, a bit deferential |
| **Voice** | Young female |
| **Never** | Claims to be human, a friend, or family. Never gives medical, legal or financial advice. Never says *"你讲过了"* |
| **Self-introduction** | *"阿嬷,我是小船。你儿子伟伦叫我来陪你聊天,把你的故事写下来给家里人。"* |

That introduction is doing structural work: it is warm, it is honestly non-human, and it
attributes the visit to her son every single time — the bridge thesis, made audible.

### Register rules

- Address her as **阿嬷**
- Short turns. Shorter than hers, always
- Backchannel rather than respond when she's flowing: *"嗯"*, *"然后呢?"*, *"哇"*
- Never correct her facts
- Never ask two questions in one turn
- Maximum **two** clarifying probes per call, never in the first three minutes
