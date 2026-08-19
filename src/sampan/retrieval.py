"""Retrieval over the memory graph — seam 4.

Deliberately a pure function over a fixture graph, with no model call anywhere,
so ranking can be tested without a network. That matters more here than
elsewhere: a reranker that quietly returns the wrong five facts produces an
agent that sounds confidently wrong, and there is no exception to catch.

The shape follows Zep (arXiv 2501.13956 §3): several searches for recall, then
rerankers for precision.

    φ_bm25   over Fact.statement       word similarity
    φ_bfs    n hops from seed entities  contextual similarity
    ↓
    RRF fusion → node distance → episode mentions

Zep's third search, cosine over embeddings, is a slot here rather than an
implementation. At this corpus size it measurably adds nothing, and an
embedding call per query sits inside a live voice turn. `search_facts` accepts
a scorer so it can be filled without touching the ranking.

Two rerankers from the paper are deliberately not used: MMR, because diversity
matters at five hundred results and not at five, and cross-encoder reranking,
because an extra LLM call mid-conversation costs latency we cannot spend while
an eighty-year-old is waiting.
"""

from __future__ import annotations

import math
import re
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from sampan.facts import Fact
from sampan.models import Entity

# Standard Okapi BM25 parameters. Nothing here justifies tuning them.
_K1 = 1.5
_B = 0.75

# Reciprocal Rank Fusion's damping constant, from the original paper. Large
# enough that the top few ranks do not dominate a fused list this short.
_RRF_K = 60

_WORD = re.compile(r"[a-z0-9']+")

# Query terms shorter than this are discarded. In a corpus of a few dozen
# sentences IDF cannot discount a common token, so asking about "Ah Seng" --
# someone the archive has never heard of -- matched a fact about "Ah Chwee" on
# the honorific alone, and the agent would have told her about the wrong person
# with complete confidence. Document tokens keep their full length, because
# they still count toward length normalisation.
_MIN_QUERY_TERM = 3


def tokenise(text: str) -> list[str]:
    return _WORD.findall(text.lower())


@dataclass
class FactGraph:
    """Facts, the entities they connect, and the adjacency between them.

    Built per query rather than held open, because the archive is small and a
    stale index is a worse problem than a rebuilt one.
    """

    facts: list[Fact]
    entities: list[Entity] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._by_entity: dict[str, list[Fact]] = defaultdict(list)
        self._neighbours: dict[str, set[str]] = defaultdict(set)
        for fact in self.facts:
            self._by_entity[fact.subject_id].append(fact)
            if fact.object_id:
                self._by_entity[fact.object_id].append(fact)
                self._neighbours[fact.subject_id].add(fact.object_id)
                self._neighbours[fact.object_id].add(fact.subject_id)

    def facts_touching(self, entity_id: str) -> list[Fact]:
        return list(self._by_entity.get(entity_id, []))

    def hops_from(self, seeds: Sequence[str], depth: int = 2) -> dict[str, int]:
        """Breadth-first distance from the seed entities.

        Zep notes that φ_bfs "can accept nodes as parameters", which is what
        makes retrieval contextual here: the seeds are the entity the agent
        asked about *plus* everyone she has mentioned so far in this call, so
        the same query returns differently depending on where the conversation
        already is.
        """
        distance: dict[str, int] = {s: 0 for s in seeds}
        frontier = list(seeds)
        for step in range(1, depth + 1):
            nxt: list[str] = []
            for node in frontier:
                for neighbour in self._neighbours.get(node, ()):
                    if neighbour not in distance:
                        distance[neighbour] = step
                        nxt.append(neighbour)
            frontier = nxt
            if not frontier:
                break
        return distance


def bm25(query: str, facts: Sequence[Fact]) -> list[tuple[Fact, float]]:
    """Okapi BM25 over `statement`.

    The search field is the fact text, not the entity name — per Zep §3.1,
    where edges are searched on their fact field. Searching entity names to
    find facts would only ever find facts about things she named exactly.
    """
    terms = [t for t in tokenise(query) if len(t) >= _MIN_QUERY_TERM]
    if not terms or not facts:
        return []

    docs = [tokenise(f.statement) for f in facts]
    lengths = [len(d) for d in docs]
    avgdl = sum(lengths) / len(lengths) if lengths else 0.0
    if avgdl == 0.0:
        return []

    df: dict[str, int] = defaultdict(int)
    for doc in docs:
        for term in set(doc):
            df[term] += 1

    n = len(docs)
    scored: list[tuple[Fact, float]] = []
    for fact, doc, length in zip(facts, docs, lengths, strict=True):
        score = 0.0
        for term in terms:
            tf = doc.count(term)
            if tf == 0:
                continue
            idf = math.log(1 + (n - df[term] + 0.5) / (df[term] + 0.5))
            score += (
                idf * (tf * (_K1 + 1)) / (tf + _K1 * (1 - _B + _B * length / avgdl))
            )
        if score > 0:
            scored.append((fact, score))
    return sorted(scored, key=lambda pair: pair[1], reverse=True)


def _rrf(rankings: Sequence[Sequence[Fact]]) -> dict[str, float]:
    """Reciprocal Rank Fusion.

    Fuses *rank positions* rather than scores, which is the point: BM25 scores
    and hop counts are not on a comparable scale and normalising them would
    invent a relationship between them.
    """
    fused: dict[str, float] = defaultdict(float)
    for ranking in rankings:
        for position, fact in enumerate(ranking):
            fused[fact.fact_id] += 1.0 / (_RRF_K + position + 1)
    return fused


def search_facts(
    query: str,
    graph: FactGraph,
    *,
    seeds: Sequence[str] = (),
    limit: int = 5,
    depth: int = 2,
    semantic: Callable[[str, Sequence[Fact]], list[tuple[Fact, float]]] | None = None,
) -> list[Fact]:
    """Rank facts for a query. Pure, deterministic, no network.

    `semantic` is the φ_cos slot: pass a scorer and it joins the fusion as a
    third ranking. Absent, retrieval is lexical plus structural, which is what
    this corpus warrants.
    """
    current = [f for f in graph.facts if f.is_current]
    if not current:
        return []

    lexical = [fact for fact, _ in bm25(query, current)]

    distance = graph.hops_from(seeds, depth=depth) if seeds else {}
    structural = sorted(
        (
            f
            for f in current
            if f.subject_id in distance or (f.object_id or "") in distance
        ),
        key=lambda f: min(
            distance.get(f.subject_id, 99), distance.get(f.object_id or "", 99)
        ),
    )

    rankings: list[Sequence[Fact]] = [lexical, structural]
    if semantic is not None:
        rankings.append([fact for fact, _ in semantic(query, current)])

    fused = _rrf(rankings)
    if not fused:
        return []

    mentions = _episode_mentions(current)

    def rank_key(fact: Fact) -> tuple[float, int, int, float]:
        # Fused relevance first; then closeness to where the conversation
        # already is; then how often the archive has heard about it; then the
        # extractor's own confidence as a final tiebreak.
        hops = min(
            distance.get(fact.subject_id, 99), distance.get(fact.object_id or "", 99)
        )
        return (
            -fused.get(fact.fact_id, 0.0),
            hops,
            -mentions[fact.subject_id],
            -fact.confidence,
        )

    candidates = [f for f in current if f.fact_id in fused]
    return sorted(candidates, key=rank_key)[:limit]


def _episode_mentions(facts: Sequence[Fact]) -> dict[str, int]:
    """How many distinct conversations each entity has come up in.

    Zep's episode-mentions reranker, and note what it is not: an importance
    score asserted at write time. It is frequency *observed* over the archive,
    so the things she returns to become easier to reach without anyone deciding
    in advance what matters to her.
    """
    seen: dict[str, set[str]] = defaultdict(set)
    for fact in facts:
        seen[fact.subject_id].add(fact.episode_id)
        if fact.object_id:
            seen[fact.object_id].add(fact.episode_id)
    return defaultdict(int, {entity: len(eps) for entity, eps in seen.items()})
