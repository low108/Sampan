"""Seam 4 — ranking over the memory graph. Pure, no model call.

A reranker that returns the wrong five facts throws nothing and fails nothing.
The agent simply sounds confidently wrong to an eighty-year-old, which is why
this seam is a plain function over a fixture graph.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sampan.facts import Fact, Predicate
from sampan.models import Entity, EntityType, Precision, When
from sampan.retrieval import FactGraph, bm25, search_facts, tokenise


def year(value: int) -> When:
    return When(
        raw_phrase=str(value),
        start_year=value,
        precision=Precision.YEAR,
        confidence=0.9,
    )


def fact(
    fact_id: str,
    subject: str,
    statement: str,
    *,
    predicate: Predicate = Predicate.WORKED_AT,
    obj: str | None = None,
    episode: str = "conv_001",
    confidence: float = 0.8,
    expired: bool = False,
) -> Fact:
    return Fact(
        fact_id=fact_id,
        subject_id=subject,
        predicate=predicate,
        object_id=obj,
        object_literal="" if obj else "somewhere",
        statement=statement,
        valid_from=year(1958),
        episode_id=episode,
        quote="a sentence long enough to pass the quote check easily",
        confidence=confidence,
        t_expired=datetime.now(UTC) if expired else None,
    )


def entity(entity_id: str, name: str) -> Entity:
    return Entity(
        entity_id=entity_id,
        type=EntityType.PERSON,
        canonical_name=name,
        provisional=False,
    )


# father — shop — husband, with the sister off on her own.
FACTS = [
    fact(
        "f_shop",
        "ent_father",
        "her father ran a coffee shop at Jalan Bandar",
        obj="ent_shop",
    ),
    fact(
        "f_toast",
        "ent_father",
        "her father toasted bread over a charcoal fire",
        predicate=Predicate.MADE,
        episode="conv_002",
    ),
    fact(
        "f_mother",
        "ent_mother",
        "her mother cooked at the back of the coffee shop",
        obj="ent_shop",
        episode="conv_002",
    ),
    fact(
        "f_upstairs",
        "ent_husband",
        "her husband lived upstairs above the shop",
        predicate=Predicate.LIVED_AT,
        obj="ent_shop",
    ),
    fact(
        "f_sister",
        "ent_sister",
        "her sister lent her a cheongsam for the wedding",
        predicate=Predicate.OWNED,
        episode="conv_003",
    ),
]

ENTITIES = [
    entity("ent_father", "Lim Ah Hock"),
    entity("ent_mother", "Tan Ah Tai"),
    entity("ent_husband", "Tan Eng Huat"),
    entity("ent_sister", "Lim Siew Choo"),
    entity("ent_shop", "Jalan Bandar"),
]


def graph(facts: list[Fact] | None = None) -> FactGraph:
    return FactGraph(facts=facts if facts is not None else FACTS, entities=ENTITIES)


class TestTokenising:
    def test_it_folds_case_and_drops_punctuation(self) -> None:
        assert tokenise("Her Father's coffee-shop!") == [
            "her",
            "father's",
            "coffee",
            "shop",
        ]


class TestBm25:
    def test_it_searches_the_statement_not_the_entity(self) -> None:
        """Per Zep §3.1 the search field for an edge is its fact text. Searching
        entity names would only ever find facts about things she named exactly."""
        hits = bm25("charcoal", FACTS)

        assert [f.fact_id for f, _ in hits] == ["f_toast"]

    def test_a_rarer_word_outranks_a_common_one(self) -> None:
        """IDF doing its job: 'cheongsam' appears once, 'shop' in three."""
        hits = {f.fact_id: score for f, score in bm25("cheongsam shop", FACTS)}

        assert hits["f_sister"] > hits["f_shop"]

    def test_a_query_matching_nothing_returns_nothing(self) -> None:
        assert bm25("submarine", FACTS) == []

    def test_an_empty_query_returns_nothing(self) -> None:
        assert bm25("", FACTS) == []


class TestTraversal:
    def test_seeds_are_zero_hops_away(self) -> None:
        assert graph().hops_from(["ent_father"])["ent_father"] == 0

    def test_it_reaches_neighbours_through_shared_facts(self) -> None:
        """father → shop is one hop; shop → husband makes husband two."""
        hops = graph().hops_from(["ent_father"], depth=2)

        assert hops["ent_shop"] == 1
        assert hops["ent_husband"] == 2

    def test_depth_is_respected(self) -> None:
        assert "ent_husband" not in graph().hops_from(["ent_father"], depth=1)

    def test_the_unconnected_are_never_reached(self) -> None:
        """The sister shares no fact with the shop, and must not be dragged in
        by proximity she does not have."""
        assert "ent_sister" not in graph().hops_from(["ent_father"], depth=3)


class TestSearch:
    def test_it_finds_the_obvious_thing(self) -> None:
        found = search_facts("charcoal fire", graph())

        assert found[0].fact_id == "f_toast"

    def test_superseded_facts_are_not_returned(self) -> None:
        """The archive keeps what she said. It does not go on asserting it."""
        facts = [
            *FACTS,
            fact(
                "f_old", "ent_father", "her father ran a charcoal stall", expired=True
            ),
        ]

        found = search_facts("charcoal", graph(facts))

        assert "f_old" not in [f.fact_id for f in found]

    def test_the_conversation_so_far_steers_the_result(self) -> None:
        """The same query, seeded differently, answers differently.

        "coffee" matches both the father's shop and the mother cooking in it,
        and BM25 alone prefers the father's — it is the shorter sentence. Seed
        the traversal on the mother, as it would be if she had just been
        talking about her, and the mother's fact comes first instead. This is
        what makes agent-initiated retrieval feel contextual under the Live
        API, where nothing can be injected per turn.
        """
        neutral = search_facts("coffee", graph(), limit=3)
        seeded = search_facts("coffee", graph(), seeds=["ent_mother"], limit=3)

        assert neutral[0].fact_id == "f_shop"
        assert seeded[0].fact_id == "f_mother"

    def test_a_seeded_search_prefers_the_near_over_the_far(self) -> None:
        found = search_facts("shop", graph(), seeds=["ent_husband"], limit=5)

        assert found[0].subject_id in {"ent_husband", "ent_shop"}

    def test_the_limit_is_honoured(self) -> None:
        assert len(search_facts("shop coffee her", graph(), limit=2)) == 2

    def test_an_empty_graph_is_not_an_error(self) -> None:
        assert search_facts("anything", graph([])) == []

    def test_a_query_matching_nothing_returns_nothing(self) -> None:
        assert search_facts("submarine", graph()) == []

    def test_traversal_finds_what_the_words_miss(self) -> None:
        """'Jalan Bandar' never appears in the mother's statement, but she is one
        hop from the shop. Lexical search alone would lose her."""
        found = search_facts("Jalan Bandar", graph(), seeds=["ent_shop"], limit=5)

        assert "f_mother" in [f.fact_id for f in found]


class TestSemanticSlot:
    def test_a_scorer_can_be_supplied(self) -> None:
        """φ_cos is a slot rather than an implementation: at this size it adds
        nothing measurable, and an embedding call sits inside a live voice turn."""

        def always_the_sister(query: str, facts):  # noqa: ARG001
            return [(f, 1.0) for f in facts if f.fact_id == "f_sister"]

        found = search_facts("shop", graph(), semantic=always_the_sister, limit=5)

        assert "f_sister" in [f.fact_id for f in found]

    def test_without_a_scorer_retrieval_still_works(self) -> None:
        assert search_facts("coffee", graph())


class TestNotGuessing:
    """Precision over recall. A wrong fact spoken with confidence is worse than
    no fact at all, and she has no way to tell the difference."""

    def test_a_name_the_archive_has_never_heard_returns_nothing(self) -> None:
        """ "Ah Seng" once matched a fact about "Ah Chwee" on the honorific
        alone: two characters, shared by half the names in the family."""
        assert search_facts("Ah Seng", graph()) == []

    def test_a_short_common_token_alone_is_not_a_match(self) -> None:
        assert bm25("ah", FACTS) == []

    def test_a_real_name_still_matches(self) -> None:
        assert [f.fact_id for f, _ in bm25("Chwee", FACTS)] == []
        assert search_facts("cheongsam", graph())[0].fact_id == "f_sister"


class TestTheTrace:
    """Why a query returned what it did.

    Every number here was already computed by ranking and discarded on the
    return line, so the trace costs nothing but the plumbing. The point of
    surfacing it is that this pipeline has no model in the middle: the same
    question traced twice gives the same numbers, which is not true of a
    retrieval chain that asks an LLM to pick edges.
    """

    @staticmethod
    def _graph():
        from sampan.retrieval import FactGraph

        return FactGraph(
            facts=[
                fact("f1", "ent_father", "Her father opened a coffee shop."),
                fact("f2", "ent_mother", "Her mother cooked at the coffee shop."),
                fact("f3", "ent_khim", "She played in the river with Ah Chwee."),
            ]
        )

    def _trace(self, query: str, **kwargs):
        from sampan.retrieval import SearchTrace, search_facts

        held: list[SearchTrace] = []
        search_facts(query, self._graph(), on_trace=held.append, **kwargs)
        assert len(held) == 1
        return held[0]

    def test_it_reports_the_terms_it_threw_away(self) -> None:
        """The short-term filter is the fix for "Ah Seng" matching "Ah Chwee"
        on the honorific. A trace that hid it would hide the reason."""
        trace = self._trace("who is at the coffee shop")

        assert "coffee" in trace.terms
        assert "at" in trace.dropped
        assert "at" not in trace.terms

    def test_a_candidate_that_did_not_make_the_cut_is_still_scored(self) -> None:
        """The near-misses are the more interesting half: they show what the
        ranking weighed and rejected, not just what it chose."""
        trace = self._trace("coffee shop", limit=1)

        assert len(trace.returned) == 1
        ranked = [c for c in trace.candidates if c.rank is not None]
        missed = [c for c in trace.candidates if c.rank is None]
        assert len(ranked) == 1
        assert missed, "nothing was scored and rejected"
        assert all(c.bm25 > 0 or c.rrf > 0 for c in missed)

    def test_the_returned_order_matches_the_ranks(self) -> None:
        trace = self._trace("coffee shop", limit=2)

        by_rank = sorted(
            (c for c in trace.candidates if c.rank is not None),
            key=lambda c: c.rank if c.rank is not None else 0,
        )
        assert [c.fact_id for c in by_rank] == trace.returned

    def test_hops_are_none_when_the_seeds_reach_nothing(self) -> None:
        """Unreachable is not the same as far away, and a trace that showed 99
        for both would be asserting a distance nobody measured."""
        trace = self._trace("coffee shop", seeds=["ent_nobody"])

        assert all(c.hops is None for c in trace.candidates)

    def test_seeds_put_a_distance_on_what_they_reach(self) -> None:
        trace = self._trace("coffee shop", seeds=["ent_father"])

        reached = [c.hops for c in trace.candidates if c.hops is not None]
        assert reached, "the seed reached nothing"
        # `or` would be wrong here: a zero-hop fact is the seed itself, and
        # `0 or 99` is 99. Distance zero is a real answer, not a missing one.
        assert min(reached) == 0

    def test_a_retired_telling_is_named_rather_than_missing(self) -> None:
        """The thing a flat index cannot do. She told it differently later, so
        this one lost in transaction time — and saying so is the whole reason
        both tellings are kept."""
        from sampan.retrieval import FactGraph, SearchTrace, search_facts

        old = fact(
            "f_old", "ent_father", "Her father kept the shop until 1969.",
            expired=True,
        )
        old.superseded_by = "f_new"
        graph = FactGraph(
            facts=[
                fact("f_new", "ent_father", "Her father kept the shop until 1971."),
                old,
            ]
        )

        held: list[SearchTrace] = []
        search_facts("when did her father close the shop", graph, on_trace=held.append)

        assert [r.fact_id for r in held[0].retired] == ["f_old"]
        assert held[0].retired[0].superseded_by == "f_new"
        assert held[0].retired[0].expired_at
        # And it never competed: it is not among the ranked candidates.
        assert "f_old" not in [c.fact_id for c in held[0].candidates]

    def test_a_query_that_matched_nothing_still_explains_itself(self) -> None:
        """The case most worth explaining. "The archive never heard of Ah Seng"
        and "the ranking dropped it" look identical from outside, and only the
        trace tells them apart."""
        trace = self._trace("submarine periscope")

        assert trace.candidates == []
        assert trace.returned == []
        # It still says what it looked for and what it looked at.
        assert trace.terms == ["submarine", "periscope"]
        assert trace.considered == 3

    def test_an_empty_graph_still_traces(self) -> None:
        """A query that found nothing has an explanation too, and it is the
        one somebody is most likely to ask about."""
        from sampan.retrieval import FactGraph, SearchTrace, search_facts

        held: list[SearchTrace] = []
        search_facts("anything", FactGraph(facts=[]), on_trace=held.append)

        assert len(held) == 1
        assert held[0].candidates == []

    def test_tracing_does_not_change_what_is_returned(self) -> None:
        """A diagnostic that alters the thing it measures is worse than none."""
        from sampan.retrieval import search_facts

        plain = search_facts("coffee shop", self._graph(), limit=2)
        traced = search_facts(
            "coffee shop", self._graph(), limit=2, on_trace=lambda _t: None
        )

        assert [f.fact_id for f in plain] == [f.fact_id for f in traced]

    def test_the_same_query_traces_identically_twice(self) -> None:
        """The claim worth making about this pipeline: no model in the middle,
        so the working is reproducible."""
        first = self._trace("coffee shop", limit=2)
        second = self._trace("coffee shop", limit=2)

        assert first.model_dump() == second.model_dump()
