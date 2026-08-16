# Literature Synthesis: Conversational Data → Structured, Queryable Memory for a Long-Running Companion Agent

**Compiled:** 2026-08-16.
**Method:** Scholar datasource (Google Scholar–style index) searches across 19 targeted queries; citation counts are as returned by that index on 2026-08-16. They will differ from Semantic Scholar / OpenAlex counts and are flagged where they look anomalous.
**Relevance filter applied:** voice companion for an elderly user; months of open-ended conversation; post-hoc extraction of life-story events, entity graphs, unfinished threads, interaction preferences; session-start "what do I know about this person?" retrieval.

---

## Area 1 — Long-term memory architectures for LLM agents

### Foundational, still cited

| Paper | Venue / Year | Citations | Contribution that matters | Stated limitation |
|---|---|---|---|---|
| Park et al., "Generative Agents: Interactive Simulacra of Human Behavior" | UIST 2023 | ~7,300 | The memory stream: score by recency × relevance × importance, retrieve, and *reflect* to synthesize higher-level semantic memories from episodic ones. Still the reference architecture for episodic→semantic consolidation. | Evaluated only in a simulated sandbox with 25 agents over 2 days; reflection quality uncontrolled; no contradiction handling. |
| Packer et al., "MemGPT: Towards LLMs as Operating Systems" | arXiv 2023 (later ICLR 2024 workshop; now the Letta project) | ~1,400 | OS-style memory hierarchy (context = RAM, external stores = disk) with the model itself issuing function calls to page memory in/out. Established *agent-managed* memory. | Agent must learn when to call memory functions; evaluation narrow (multi-session chat, doc QA); function-call brittleness. |
| Zhong et al., "MemoryBank: Enhancing Large Language Models with Long-Term Memory" | AAAI 2024 | ~1,250 | First to import the **Ebbinghaus forgetting curve** as an explicit decay policy, plus daily personality-summary updates for a companion chatbot. The closest foundational work to your use case. | Decay hyperparameters are hand-set and psychologically loose; evaluation on synthetic/short-horizon dialogue. |
| Xu, Szlam & Weston, "Beyond Goldfish Memory: Long-Term Open-Domain Conversation" (MSC) | ACL 2022 | ~460–475 (two index entries) | The multi-session chat dataset + retrieval/summarization baselines that defined "remember earlier sessions" as a task before LLM agents. | Sessions are crowdworker-scripted persona chats, not spontaneous talk; memory = dialogue-history retrieval only. |
| Wang et al., "Augmenting Language Models with Long-Term Memory" (LongMem) | NeurIPS 2023 | ~460 | The parametric branch: cache attention states in a decoupled memory network instead of retrieving text. Alternative to everything else in this table. | Needs training integration; memories are opaque vectors, not queryable structured records — wrong shape for your needs. |

### Current state of the art (2024–2026)

| Paper | Venue / Year | Citations | Contribution | Limitation |
|---|---|---|---|---|
| Xu et al., "A-MEM: Agentic Memory for LLM Agents" | NeurIPS 2025 | ~990 | Zettelkasten-style notes with LLM-generated attributes, keywords and *dynamic links*; memories evolve and re-link as new ones arrive. Currently the most-cited successor to the MemGPT line. | Link/note quality entirely delegated to the LLM; noise compounds over long horizons; cost of LLM-processing every memory. |
| Chhikara et al., "Mem0: Building Production-Ready AI Agents with Scalable Long-Term Memory" | arXiv 2025 | ~830 | The deployed-system reference: LLM extracts candidate facts, then applies **ADD / UPDATE / DELETE / NOOP** operations against retrieved existing memories; graph variant (Mem0ᵍ) stores entity triples. Directly implements contradiction-as-update. | Extraction faithfulness inherited from the base LLM; conflict resolution is "LLM decides", not principled; LoCoMo evaluation only. |
| Rasmussen et al., "Zep: A Temporal Knowledge Graph Architecture for Agent Memory" (Graphiti) | arXiv 2025 | ~360 | **Bi-temporal** entity/edge model (valid-time vs transaction-time); new facts *invalidate* old edges rather than overwriting, preserving history — the best-fit published model for self-contradicting dialogue over months. | Everything rides on entity-resolution quality; temporal reasoning still shallow (interval algebra absent). |
| Kang et al., "Memory OS of AI Agent" (MemoryOS) | EMNLP 2025 | ~220 | OS-inspired tiered storage (short/mid/long-term) with "heat"-based page updates; strong LoCoMo results at low token cost. | Heat metric is a recency/frequency heuristic; elderly-user relevance ≠ frequency. |
| Tan et al., "In Prospect and Retrospect: Reflective Memory Management for Long-term Personalized Dialogue" | EMNLP 2025 | ~115 | Separates *prospective* (what to store) from *retrospective* (merge/demote) reflection; shows managed summary memory can beat full-history retrieval at long horizons. | Adds two LLM passes per turn; reflective merge errors are irreversible. |
| Xiong et al., "How Memory Management Impacts LLM Agents: An Empirical Study of Experience-Following Behavior" | ACL 2026 | ~94 | Empirical evidence that agents **over-trust stale/irrelevant memories** — experience-following bias. The key cautionary result for retrieval-time selection. | Studied in task agents, not companions; remedy space unexplored. |
| Pink et al., "Position: Episodic Memory Is the Missing Piece for Long-Term LLM Agents" | arXiv 2025 | ~39 | Argues semanticized summaries destroy exactly what episodic memory keeps (context, sequence, affect) — a direct theoretical challenge to extract-and-summarize pipelines. | Position paper; no system. |
| Surveys: Hu et al., "Memory in the Age of AI Agents" (2025, ~83 cit); Du, "Memory for Autonomous LLM Agents" (2026, ~60 cit); Hatalis et al., AAAI-SS 2023 (~151 cit) | — | — | Taxonomies of episodic/semantic/procedural splits, consolidation, retrieval-time selection. | Surveys; age fast in this field. |
| Forgetting/decay, current: "SF-AMS: Strategic Forgetting for Structured Memory" (2026, ~2 cit); "Adaptive Memory Admission Control" (2026, ~14 cit); SimpleMem (2026, ~21 cit); hierarchical lines: H-Mem / HiMem / EverMemOS (2026, ~20/12/29 cit) | mostly arXiv/ACL 2026 | low | Active but immature sub-literature on admission control and forgetting beyond Ebbinghaus. | No consensus policy; all evaluated on synthetic benchmarks. |

**Verdict for your system:** the field has converged on *extract → dedupe/conflict-check → store as structured record or graph edge with temporal validity → retrieve with recency/relevance/importance scoring*. Zep's bi-temporal invalidation and Mem0's UPDATE/DELETE ops are the current reference designs for self-contradicting input. Nothing published handles "unfinished conversational threads" as a first-class memory type — that is an open design space.

---

## Area 2 — Knowledge-graph / triple extraction from dialogue

| Paper | Venue / Year | Citations | Contribution | Limitation |
|---|---|---|---|---|
| Yu, Sun, Cardie & Yu, "Dialogue-Based Relation Extraction" (DialogRE) | ACL 2020 | ~192 | **The** foundational dialogue-RE dataset: relations whose arguments are scattered across turns; showed document-RE models degrade badly on dialogue. | 36 fixed relations, English TV transcripts, entities pre-identified; no speaker-relative semantics. |
| Chen, Zhou & Choi, "Robust Coreference Resolution and Entity Linking on Dialogues: Character Identification" | CoNLL 2017 | ~50 | Multiparty-dialogue entity handling; mentions are short, elliptical, speaker-dependent. | Fictional characters, not real users; single-session. |
| Liu, Shi & Chen, "Coreference-Aware Dialogue Summarization" | SIGDIAL 2021 | ~84 | Showed summaries of dialogue inherit coreference errors; coupling extraction to coref is necessary. | Summarization framing, not KG construction. |
| Zhong et al., "A Comprehensive Survey on Automatic Knowledge Graph Construction" | ACM Computing Surveys 2023 | ~590 | Reference survey — but its pipeline assumptions (documents, explicit entities) are exactly what dialogue violates. | Document-centric. |
| Zhu et al., "LLMs for Knowledge Graph Construction and Reasoning" | World Wide Web Journal 2024 | ~560 | Maps LLM-based KG construction; notes zero/few-shot relation extraction remains weak. | Again document-centric; dialogue called out as future work. |
| Trajanoska et al., "Enhancing KG Construction Using LLMs" | arXiv 2023 | ~174 | Early demonstration of LLM triple extraction vs OpenIE. | Document input. |
| Dialogue-specific recent: Rook, "Open Knowledge Extraction from Dialogue Using In-Context Learning" (ISWC 2025 demo, 0 cit); Maoliniyazi et al., "PROM: Personal KG Construction with LLMs" (2025, ~2 cit); Ntanavaras, conversational triple extraction for diabetes (2024, ~2 cit) | workshops/demos | 0–2 | The thin edge of work that actually does KG extraction *from dialogue*. | All preliminary, unbenchmarked. |
| Kejriwal, "Named Entity Resolution in Personal Knowledge Graphs" | arXiv 2023 | ~6 | Treats the personal-KG setting (your "graph of people and places") and its entity-resolution oddities explicitly. | Opinion/experimental essay, small-scale. |

**Verdict:** dialogue-specific KG extraction is genuinely underdeveloped. DialogRE remains the anchor citation; almost everything since extracts from documents. The elliptical, speaker-relative, self-contradicting properties you care about are named as motivations in several papers but operationalized in none with real users.

---

## Area 3 — Coreference & entity resolution across long, multi-session conversations

| Paper | Venue / Year | Citations | Contribution | Limitation |
|---|---|---|---|---|
| Lee et al., "End-to-End Neural Coreference Resolution" | EMNLP 2017 | ~1,360 | Span-ranking architecture underlying most modern coref. | Document setting; assumes one consistent world per document. |
| Lee et al., "Deterministic Coreference… Entity-Centric, Precision-Ranked Rules" (Stanford sieve) | Computational Linguistics 2013 | ~640 | The rule-based baseline; still relevant as interpretable fallback. | — |
| Joshi et al., "BERT for Coreference Resolution"; Wu et al., "CorefQA" | EMNLP 2019 / ACL 2020 | ~505 / ~259 | Neural-era coref quality step-change. | Document setting. |
| Xu & Choi, "Online Coreference Resolution for Dialogue Processing" | LREC 2022 | ~8 | Streaming mention-linking for dialogue in real time — closest to a voice pipeline. | Single session; TV transcripts. |
| Bai et al., "Joint Coreference Resolution and Character Linking for Multiparty Conversation" | EACL 2021 | ~12 | Joint coref+linking in multi-speaker settings. | Character identification framing. |
| Lin et al., "Personalized Entity Resolution with Dynamic Heterogeneous KG Representations" | EMNLP 2021 | ~12 | Entity resolution conditioned on a *personal* context. | Recommendation domain, not conversation. |

**The gap is stark:** no benchmark or method found addresses *cross-session* coreference where the same surface form ("my sister", "my doctor") resolves to different entities **per speaker and per life period**. Kinship-term resolution per speaker appears nowhere as an explicit task. Practically, the field implicitly delegates this to the memory system's entity-resolution layer (Zep/Mem0ᵍ) rather than to coreference models — with no published evaluation of how well that works.

---

## Area 4 — Temporal grounding of vague & relative time expressions

| Paper | Venue / Year | Citations | Contribution | Limitation |
|---|---|---|---|---|
| Pustejovsky et al., "TimeML: Robust Specification of Event and Temporal Expressions in Text" | 2003 (AAAI symposium volume) | ~1,170 | The annotation standard: TIMEX3 with value/type (DATE, DURATION, SET), event anchoring, TLINKs. | Designed for news; assumes recoverable calendar dates. |
| Romary (ed.), "ISO-TimeML" | LREC 2010 | ~300 | ISO standardization of TimeML. | Same assumptions. |
| Strötgen & Gertz, "HeidelTime" | LREC 2010 workshop | ~540 | Rule-based extraction+normalization; still the strongest interpretable timex normalizer. | Needs a document-creation-time anchor; brittle on informal/vague language. |
| Chang & Manning, "SUTime" | LREC 2012 | ~605 | The de-facto library (Stanford CoreNLP) for timex normalization. | Same anchor-time dependence; "the year of the flood" is out of scope. |
| Angeli, Manning & Jurafsky, "Parsing Time: Learning to Interpret Time Expressions" | NAACL 2012 | ~80 *(flag: this index's count looks low for this paper; could not cross-verify)* | Learned compositional temporal interpretation against a reference time. | Reference time must be known/calendar-based. |
| Sun, Rumshisky & Uzuner, "Normalization of Relative and Incomplete Temporal Expressions in Clinical Narratives" | JAMIA 2015 | ~22 | Directly on your problem shape: relative/incomplete expressions normalized against clinical timeline events. | Clinical domain; small data. |
| Styler et al., "Temporal Annotation in the Clinical Domain" (THYME/TimeML) | TACL 2014 | ~260 | Clinical timeline construction; handles uncertainty and granularity better than news-TimeML. | Clinical. |
| Zhong & Cambria, "Time Expression Recognition and Normalization: A Survey" | AI Review 2023 | ~20 | Consolidates the pre-LLM pipeline literature. | Pre-LLM. |
| Lal et al., "EventTempEx: Interpreting Event-Anchored Temporal Expressions" | AACL-IJCNLP 2025 | 0 | Exactly "before I married" / "the year of the flood": expressions anchored to *events*, not dates. | Brand-new, unevaluated at scale; flagged low-confidence. |
| Chen et al., "DeFuzzRAG: Handling Fuzzy Time Expressions for Temporal Robustness in RAG" | AAAI 2026 | 0 | Fuzzy-time-aware retrieval — the retrieval-side answer to vague time. | New; narrow evaluation. |
| Agent-memory temporal work: Su et al., "Beyond Dialogue Time: Temporal Semantic Memory" (ACL Findings 2026, ~9 cit); Sen et al., "Chronos: Temporal-aware conversational agents" (2026, ~8 cit); Li et al., "TimeMem: Temporal-hierarchical memory consolidation" (ACL Findings 2026, ~16 cit) | 2026 | 0–16 | The current wave adding valid-time hierarchies to agent memory. | All benchmark-on-LoCoMo-style synthetic data. |

**Verdict:** standards and normalizers are mature for calendar-anchored text; *event-anchored* personal time ("after the divorce", "the year of the flood") has essentially one new tool (EventTempEx) and no benchmark. Interval representations with explicit uncertainty exist in annotation standards (THYME) but are absent from all current agent-memory systems — Zep stores valid-time edges, not uncertain intervals.

---

## Area 5 — User modelling & persona/preference induction

| Paper | Venue / Year | Citations | Contribution | Limitation |
|---|---|---|---|---|
| Xu et al., "Long Time No See! Open-Domain Conversation with Long-Term Persona Memory" (DuLeMon) | ACL Findings 2022 | ~200 | Explicit persona memory recalled and *managed* across sessions, for both interlocutors. Foundational for "what do I know about this person?". | Chinese dataset, short horizons, written chat. |
| MSC (Xu, Szlam & Weston 2022) — see Area 1 | ACL 2022 | ~460 | Session-summary personas as the memory representation. | Personas written by crowdworkers, not induced. |
| Li et al., "Hello Again! LLM-powered Personalized Agent for Long-Term Dialogue" | ACL 2025 | ~170 | Induces and updates user models from dialogue; strong recent reference. | Synthetic long dialogues. |
| Jiang et al., "Know Me, Respond to Me: Benchmarking LLMs for Dynamic User Profiling" | arXiv 2025 | ~148 | The benchmark for *dynamic* profiling: attributes arrive, **get revised and contradicted** over time; measures update fidelity at scale. | Simulated users; profiles are attribute lists, not rich life stories. |
| Jo et al., "Understanding the Impact of Long-Term Memory on Self-Disclosure with LLM-powered Chatbots" (CareCall follow-up) | CHI 2024 | ~123 | HCI evidence with real elderly users: visible long-term memory **increases self-disclosure** and raises expectations of being remembered — both the opportunity and the risk for your system. | Single deployment (Korean care-call service). |
| Jandaghi et al., "Faithful Persona-based Conversational Dataset Generation with LLMs" | EMNLP 2024 | ~108 | Defines *faithfulness* of persona portrayal — the generation-side counterpart of grounded extraction. | About synthetic data, not extraction. |
| Sun et al., "PersonaDB" (2025, ~55 cit); Zhong et al., "Evaluating LLM adaptation to sociodemographic factors: profile vs. dialogue history" (2025, ~7 cit) | ACL 2025 / arXiv | — | Profile stores vs. raw history as personalization input — feeds the Area-8 disagreement. | — |

**Verdict:** representation = flat attribute/persona lists in nearly all work; contradiction handling is measured (Know-Me benchmark, LongMemEval's knowledge-update split, Mem0's UPDATE op) but solutions are "LLM decides to overwrite." No published work represents *preference confidence, provenance, or drift over months*.

---

## Area 6 — Schema-constrained / structured generation & faithfulness

| Paper | Venue / Year | Citations | Contribution | Limitation |
|---|---|---|---|---|
| Geng et al., "JSONSchemaBench" | arXiv 2025 (also ES-FoMo workshop) | ~92 | The rigorous constrained-decoding benchmark (10K real schemas): measures coverage, efficiency — and finds **constraint–quality tradeoffs**: hard schema enforcement can degrade semantic content. | JSON tasks, not dialogue extraction. |
| Agarwal et al., "Think Inside the JSON: RL for Strict Schema Adherence" | arXiv 2025 | ~27 | RL post-training for schema adherence. | Schema validity, not grounding. |
| Niimi, "Distortion Instead of Hallucination: The Effect of Reasoning Under Strict Constraints" | arXiv 2026 | ~3 | Directly on your named failure: under strict output constraints, models **distort content to satisfy the schema** rather than omitting what they don't know. | Small-scale, early. |
| Hasan, "StructHallu-Drift: Structured Hallucinations Under Schema Evolution" | ACL workshop 2026 | ~1 | Hallucination measured when required fields have no grounded value. | Workshop paper. |
| Huang et al., "A Critical Assessment of Using ChatGPT for Extracting Structured Data from Clinical Notes" | npj Digital Medicine 2024 | ~334 | The flagship empirical extraction audit: documents fabricated/inconsistent values in schema-filling from unstructured text. | Clinical notes, zero-shot GPT-3.5/4 era. |
| Asgari et al., "A Framework to Assess Clinical Safety and Hallucination Rates of LLMs" | npj Digital Medicine 2025 | ~422 | Safety-graded hallucination framework for medical summarization/extraction. | Clinical. |
| Shah, "Accuracy, Consistency, and Hallucination of LLMs when Analyzing Unstructured Clinical Data" | JAMA Network Open 2024 | ~100 | Quantified run-to-run inconsistency of LLM extraction. | Clinical. |
| Xu et al., "Large Language Models for Generative Information Extraction: A Survey" | Frontiers of Computer Science 2024 | ~650 | Reference survey of LLM-IE: documents over-extraction and unfaithful generation as known failure classes. | Survey. |

**On your specific question** — *a model satisfying a required field with a paraphrase of its own prior output rather than a grounded value*: I found **no dedicated study** of this exact phenomenon. The closest evidence is (a) the clinical extraction audits above (fabricated field values measured), and (b) Niimi 2026 and StructHallu-Drift on constraint-induced content distortion. Treat this as a verified *gap*, with adjacent evidence that the failure is real and measurable. **Flagged.**

---

## Area 7 — Evaluation benchmarks for long-term conversational memory

| Paper | Venue / Year | Citations | What it measures | What it demonstrably fails to measure |
|---|---|---|---|---|
| Maharana et al., "Evaluating Very Long-Term Conversational Memory of LLM Agents" (**LoCoMo**) | ACL 2024 | ~835 | QA (single/multi-hop, temporal, open-domain), event summarization, dialogue response over ~35-session machine-generated dialogues. Key findings: long-context LLMs degrade with distance; RAG fails temporal reasoning; retrieval of multimodal/event structure poor. | Contradiction handling, abstention, user-model quality, privacy; dialogues are LLM-generated personas, not real months-long talk. |
| Wu et al., "LongMemEval: Benchmarking Chat Assistants on Long-Term Interactive Memory" | arXiv 2024 / ICLR 2025 | ~530 | 500 questions over curated chat histories; five abilities: information extraction, multi-session reasoning, **temporal reasoning, knowledge updates, abstention**. Showed ~30% accuracy drop vs. single-session; commercial assistants weak on temporal reasoning and abstention. | Still QA-centric; histories assembled, not organic; no entity-graph fidelity metric. |
| Li et al., "LoCoMo-Plus: Beyond-Factual Cognitive Memory Evaluation" | ACL 2026 | ~10 | Demonstrates LoCoMo is dominated by factual recall; adds cognitive/inferential memory probes. | Extension, not replacement. |
| Pakhomov et al., "ConvoMem Benchmark: Why Your First 150 Conversations Don't Need RAG" | arXiv 2025 | ~10 | Evidence that at moderate scale simple full-history methods match complex memory systems — calibrates when architecture is overkill. | 150-conversation ceiling is far below your months-long setting. |
| Hu, Wang & McAuley, "Evaluating Memory in LLM Agents via Incremental Multi-Turn Interactions" | ICLR 2026 | ~197 | Incremental-interaction memory evaluation protocol. | Task agents. |
| Others: MemTrack (2025, ~17 cit), Mem2ActBench (2026, ~17 cit), MemGym (2026, ~6 cit), AgentMemBench (2026, 0 cit) | — | low | Proliferating task-agent memory benchmarks. | None touch elderly-companion shape. |

**Verdict:** LoCoMo + LongMemEval are the two anchor evaluations; every current memory system reports on them. Both are synthetic, QA-centric, and English. **Nothing measures extraction faithfulness against ground-truth life facts, entity-merge correctness, unfinished-thread tracking, or harm-sensitive memory in an elderly population.**

---

## Area 8 — The critical literature (deliberately included)

### Documented extraction failure modes
- Huang et al., npj Digital Medicine 2024 (~334 cit) and Shah, JAMA Netw Open 2024 (~100 cit): fabricated and run-inconsistent field values in schema-filling from unstructured text.
- Sarmah et al., "Reducing Hallucination in Extracting Information from Financial Reports" (2023, ~46 cit): mitigation framing for IE hallucination.
- Xu et al., "Mitigating Hallucinations of LLMs in Medical Information Extraction via Contrastive Decoding" (Findings of EMNLP 2024, ~26 cit).
- Jiang et al., "On LLMs' Hallucination with Regard to Known Facts" (NAACL 2024, ~90 cit): hallucination tracks **entity frequency** — rare/ambiguous entities (your user's acquaintances) are worst-case.
- Kodikara & Verspoor, "Lesser the Shots, Higher the Hallucinations" (ALTA 2024, ~4 cit): few-shot IE degrades fast.
- Su et al., "Mitigating Entity-Level Hallucination in LLMs" (SIGIR-AP 2024, ~60 cit).
- Surveys: Huang et al., TOIS 2025 (~6,900 cit); Tonmoy et al. 2024 (~1,000 cit); Ye et al., "Cognitive Mirage" 2023 (~330 cit).
- Confidence calibration: surveyed within the above; **no memory-system paper reports calibrated extraction confidence** — flagged as absent rather than estimated.

### "Structured extraction is the wrong approach" — the evidence, both ways
- *For raw retrieval:* ConvoMem (2025, ~10 cit) — under ~150 conversations, simple full-context methods match memory architectures. LoCoMo's own results: RAG over raw history beats several structured memory baselines on factual single-hop QA. Zhou & Han, "A Simple Yet Strong Baseline for Long-Term Conversational Memory" (2025, ~13 cit).
- *Against raw retrieval:* LongMemEval shows raw-history assistants failing temporal reasoning, knowledge updates, and abstention; "In Prospect and Retrospect" (EMNLP 2025) shows managed summaries beating full history at long horizons; Pollertlam & Kornsuwannawit, "Beyond the Context Window" (2026, ~10 cit) — cost analysis favors fact-based memory as history grows; Pink et al. 2025 argue *episodic* raw traces must be kept — but alongside, not instead of, semantic memory.
- **Net:** the disagreement is real and unresolved; it decomposes by question type (facts → either; temporal/updates/abstention → structured wins; rich episodic recall → raw wins) and by horizon length. A hybrid (structured index *pointing into* raw transcripts) is what Zep/Mem0ᵍ/A-Mem all effectively implement.

### Entity merging: false merges vs. false splits
- Menestrina, Whang & Garcia-Molina, "Evaluating Entity Resolution Results" (VLDB 2010, ~120 cit): pairwise precision/recall metrics **mischaracterize** merge/split error structure; proposed cluster-aware alternatives. The canonical "your metric lies to you" paper.
- Christophides et al., "End-to-End Entity Resolution for Big Data: An Overview" (ACM CSUR 2020, ~380 cit); Paulheim, "Knowledge Graph Refinement: A Survey" (Semantic Web 2016, ~2,100 cit).
- Welch et al., "Fast and Accurate Incremental Entity Resolution" (CIKM 2012, ~28 cit): in incremental settings (yours), **false merges propagate and contaminate everything attached to the merged node** — arguing false merges cost more than false splits in growing graphs.
- **Flag:** a rigorous, quantified false-merge-vs-false-split cost comparison *for personal conversational graphs specifically* does not exist; the asymmetry claim rests on incremental-ER reasoning, not companion-memory experiments.

---

## Area 9 — Applied / HCI: reminiscence, life review, digital legacy with real elderly participants

| Paper | Venue / Year | Citations | What held up / what happened | Harms & cautions reported |
|---|---|---|---|---|
| Bickmore et al., "'It's Just Like You Talk to a Friend': Relational Agents for Older Adults" | Interacting with Computers 2005 | ~465 | Foundational: relational framing drives engagement with elderly users. | Small sample; novelty effects. |
| Vardoulakis et al., "Designing Relational Agents as Long-Term Social Companions for Older Adults" | IVA 2012 | ~240 | Longitudinal home deployment design patterns (remembering prior talk as relationship-building). | Lab-home hybrid. |
| Ring et al., "Social Support Agents for Older Adults: Longitudinal Affective Computing in the Home" | JMUI 2015 | ~130 | Multi-week in-home affective agent; engagement sustained when agent references personal history. | Small n. |
| Lazar, Thompson & Demiris, "A Systematic Review of the Use of Technology for Reminiscence Therapy" | Health Education & Behavior 2014 | ~315 | The reference review: technology works best as a **conversation catalyst**, not a therapist replacement. | Reviewed studies methodologically weak; few RCTs. |
| Subramaniam & Woods, "Therapeutic Use of ICT in Reminiscence Work for People with Dementia" | Int J Computers in Healthcare 2010 | ~56 | Digital life-story work feasible in dementia care. | — |
| Jo et al., "Understanding the Benefits and Challenges of Deploying Conversational AI Leveraging LLMs for Public Health" (CareCall) | CHI 2023 | ~330 | **The deployment study closest to your system**: LLM phone companion for socially isolated elderly at national scale. Held up: reduced loneliness, offload on care workers. Reported: users **over-attach**, expect memory the system lacks, disclose more than intended. | Over-attachment; expectation–capability gap on memory; operator oversight burden. |
| Jo et al., CHI 2024 (long-term memory & self-disclosure) | CHI 2024 | ~123 | Memory visibility ↑ disclosure — a double-edged finding for consent and extraction. | Users forget what they told the agent; "memory surprises" disturb some. |
| Broadbent et al., "ElliQ, an AI-Driven Social Robot to Alleviate Loneliness: Progress and Lessons Learned" | J Aging & Health 2024 | ~93 | Proactivity and personalization valued; usage decays without fresh, personally-relevant content — an argument *for* good memory. | Vendor-affiliated evaluation. |
| Irfan, Kuoppamäki & Skantze, "Recommendations for Designing Conversational Companion Robots with Older Adults" | Frontiers in Robotics & AI 2024 | ~90 | Co-design: elders explicitly ask for the robot to **remember past conversations and people**. | — |
| Loveys et al., "AI for Older People Receiving Long-Term Care: Systematic Review of Acceptability" | Lancet Healthy Longevity 2022 | ~120 | Acceptability evidence base. | Heterogeneous, short studies. |
| VR/multimedia reminiscence: Mao et al., JMIR 2024 (~55); Lu et al., JMIR Serious Games 2023 (~41); Ng et al., J Clinical Nursing 2026 (~41); Rios Rincon et al., digital storytelling review 2022 (~90) | — | — | Structured reminiscence with media prompts shows modest well-being effects, incl. MCI/dementia. | Effect sizes small; facilitator involvement confounds. |
| Hollanek & Nowaczyk-Basińska, "Griefbots, Deadbots, Postmortem Avatars" | Philosophy & Technology 2024 | ~230 | The harms framework for your digital-legacy dimension: consent of the deceased, dignity, grief interference; proposes safeguards. | Normative, not empirical. |
| Albers et al., "Dying, Death, and the Afterlife in HCI: A Scoping Review" | CHI 2023 | ~55 | Maps thanatosensitive design space. | — |
| de Wynter, "If Eleanor Rigby Had Met ChatGPT: Loneliness in a Post-LLM World" | ACL 2025 | ~6 | Critical analysis: LLM companionship vs. loneliness — engagement does not equal welfare. | Conceptual. |

**Verdict:** what held up with real elderly participants: (1) relational continuity — referencing past conversations — is the single most requested and most engaging feature; (2) technology as *prompt/catalyst* for human conversation beats technology as conversational endpoint; (3) proactivity works if personally relevant. Reported harms: over-attachment, memory-expectation gaps, unintended disclosure, and (for legacy features) consent/dignity issues around posthumous use. **No study evaluates the accuracy of what these systems remember** — the HCI and extraction literatures do not yet touch.

---

## Where the literature disagrees with itself

1. **Structured memory vs. raw-transcript retrieval.** Mem0/Zep/A-Mem papers report structured memory winning on LoCoMo/LongMemEval; ConvoMem and LoCoMo's own baselines show raw-history retrieval matching them on factual QA at moderate scale. The honest decomposition (by question type and horizon) is only visible when you read across papers; individual papers each claim generality.
2. **Is forgetting good?** MemoryBank's Ebbinghaus decay is widely cited as principled; the experience-following study (Xiong et al., ACL 2026) shows stale memories actively mislead agents, implying forgetting helps; the HCI literature (Jo et al., Irfan et al.) shows elderly users *expect and reward* indefinite memory. Decay policies that help benchmarks may harm the relationship.
3. **Parametric vs. non-parametric memory.** The LongMem line (memory in weights) vs. everything else (external stores). Parametric work claims efficiency; it cannot produce the queryable, auditable records a care context needs — a disagreement mostly conducted by ignoring each other.
4. **Constrained decoding: reliability or distortion?** Schema-adherence work (RL for JSON, SLOT) treats validity as the goal; JSONSchemaBench and Niimi show validity pressure degrades or distorts content. Both are right; the field has not reconciled them into practice guidance.
5. **What benchmarks measure.** LoCoMo's authors frame it as comprehensive memory evaluation; LoCoMo-Plus shows it is mostly factual recall; LongMemEval implicitly criticizes LoCoMo by adding abstention and knowledge-update splits. "State of the art on LoCoMo" is a weaker claim than it sounds.
6. **Episodic richness vs. semantic compression.** Generative-Agents-style reflection (compress to semantic) vs. Pink et al.'s position that compression destroys the retrievable episodic context — directly relevant to your "life-story events with sensory detail" requirement.

## What is genuinely unsolved

1. **Speaker-relative kinship and possessive resolution across sessions.** "My sister" resolving differently per speaker and per life period: no dataset, no method, no metric. Closest fragments: character identification (single-session fiction) and personal-KG entity resolution (non-conversational).
2. **Event-anchored personal time.** "Before I married," "the year of the flood": annotation standards (TimeML/THYME) support event anchoring and uncertain intervals on paper, but no working system normalizes such expressions against a *personal* event timeline, and no agent-memory system stores intervals-with-uncertainty.
3. **Faithful field-filling under schema pressure.** Whether models fill required fields with self-paraphrase rather than grounded values is unmeasured (adjacent clinical evidence suggests it happens). No memory benchmark scores extraction provenance at the field level.
4. **Contradiction semantics.** Update-vs-coexist decisions ("I hated gardening" 2024 vs. "I love my garden" 2026 — changed preference vs. different context) are delegated to LLM judgment everywhere; no principled representation (preference + valid-time + confidence) is evaluated.
5. **Quantified merge/split economics for personal graphs.** The false-merge > false-split cost asymmetry is argued, never measured, in conversational settings.
6. **Unfinished conversational threads as memory.** No system or benchmark represents open loops ("she never said how the dispute ended") — an obvious companion feature with no literature.
7. **Longitudinal evaluation with real elderly users of memory *accuracy*.** CareCall/ElliQ measure engagement and wellbeing; the memory literature measures synthetic QA. The intersection — does what the agent remembers about a real elderly person stay true over months — is unstudied.
8. **Forgetting/consent mechanics for companions.** No evaluated design lets a user inspect, correct, or delete what a companion remembers — despite HCI evidence that memory surprises disturb users.

## Verification flags (could not fully verify; not estimated)

- All citation counts come from the Scholar datasource (Google Scholar–style index) as of 2026-08-16; expect ±20–40% divergence from Semantic Scholar/OpenAlex and rapid growth for 2025–2026 papers.
- Angeli et al. 2012 "Parsing Time" returned ~80 citations, lower than expected for that paper's standing; the count could not be cross-verified in this session.
- Several 2026 items are workshop/demo/ISWC-poster venues (EventTempEx, Rook, StructHallu-Drift, AgentMemBench); venue prestige and peer-review depth are accordingly thin.
- MSC (Xu, Szlam & Weston) appears twice in the index (arXiv 2021, ACL 2022) with split counts (~12 and ~463); combined figure is approximate.
- "SF-AMS," "EverMemOS," and several 2026 arXiv systems have near-zero citation histories; their state-of-the-art claims rest on self-reported LoCoMo/LongMemEval numbers.
