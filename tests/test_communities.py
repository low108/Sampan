"""Communities — the chapters of her life. Clustering only, no model call."""

from __future__ import annotations

from datetime import UTC, datetime

from sampan.communities import (
    Community,
    CommunitySummary,
    build_communities,
    detect,
    extend,
    hub_entities,
)
from sampan.facts import Fact, Predicate
from sampan.models import Entity, EntityType


def entity(entity_id: str, name: str, merged: str | None = None) -> Entity:
    return Entity(
        entity_id=entity_id,
        type=EntityType.PERSON,
        canonical_name=name,
        provisional=False,
        merged_into=merged,
    )


def fact(fact_id: str, subject: str, obj: str | None, *, expired: bool = False) -> Fact:
    return Fact(
        fact_id=fact_id,
        subject_id=subject,
        predicate=Predicate.WORKED_AT,
        object_id=obj,
        object_literal="" if obj else "somewhere",
        statement=f"{subject} is connected to {obj}",
        episode_id="conv_001",
        quote="a sentence long enough to satisfy the quote check comfortably",
        confidence=0.8,
        t_expired=datetime.now(UTC) if expired else None,
    )


# Two clusters that never touch: the shop years, and the estate childhood.
ENTITIES = [
    entity("father", "Lim Ah Hock"),
    entity("shop", "Jalan Bandar"),
    entity("husband", "Tan Eng Huat"),
    entity("mother", "Tan Ah Tai"),
    entity("estate", "Sungai Siput"),
    entity("chwee", "Ong Ah Chwee"),
]

FACTS = [
    fact("f1", "father", "shop"),
    fact("f2", "husband", "shop"),
    fact("f3", "mother", "estate"),
    fact("f4", "chwee", "estate"),
]


class TestDetect:
    def test_it_finds_the_clusters_that_are_there(self) -> None:
        clusters = detect(ENTITIES, FACTS)

        assert len(clusters) == 2
        assert sorted(len(c) for c in clusters) == [3, 3]

    def test_things_that_belong_together_end_up_together(self) -> None:
        clusters = {frozenset(c) for c in detect(ENTITIES, FACTS)}

        assert frozenset({"father", "shop", "husband"}) in clusters
        assert frozenset({"mother", "estate", "chwee"}) in clusters

    def test_a_lone_entity_is_not_a_chapter(self) -> None:
        clusters = detect([*ENTITIES, entity("stranger", "Someone")], FACTS)

        assert all("stranger" not in c for c in clusters)

    def test_a_merged_entity_is_left_out(self) -> None:
        clusters = detect(
            [*ENTITIES, entity("dupe", "Lim Ah Hock", merged="father")], FACTS
        )

        assert all("dupe" not in c for c in clusters)

    def test_a_retired_fact_stops_holding_people_together(self) -> None:
        """She has since said otherwise. It should not go on binding a chapter."""
        clusters = detect(
            ENTITIES, [*FACTS, fact("f_gone", "chwee", "shop", expired=True)]
        )

        assert len(clusters) == 2

    def test_the_result_is_stable_between_runs(self) -> None:
        """Label propagation is normally randomised. A chapter list that
        reshuffles every night is unreadable to a family watching it settle."""
        assert detect(ENTITIES, FACTS) == detect(ENTITIES, FACTS)

    def test_an_archive_with_no_facts_has_no_chapters(self) -> None:
        assert detect(ENTITIES, []) == []


class TestExtend:
    """Zep's dynamic step: cheap enough to run as each call folds in."""

    def _existing(self) -> list[Community]:
        return [
            Community(community_id="com_00", member_ids=["father", "shop", "husband"]),
            Community(community_id="com_01", member_ids=["mother", "estate", "chwee"]),
        ]

    def test_a_new_entity_joins_the_plurality_of_its_neighbours(self) -> None:
        facts = [*FACTS, fact("f5", "milo", "shop")]

        updated = extend("milo", self._existing(), facts)

        joined = next(c for c in updated if "milo" in c.member_ids)
        assert joined.community_id == "com_00"

    def test_an_entity_with_no_connections_joins_nothing(self) -> None:
        updated = extend("stranger", self._existing(), FACTS)

        assert all("stranger" not in c.member_ids for c in updated)

    def test_the_other_chapters_are_untouched(self) -> None:
        facts = [*FACTS, fact("f5", "milo", "shop")]

        updated = extend("milo", self._existing(), facts)

        estate = next(c for c in updated if c.community_id == "com_01")
        assert estate.member_ids == ["mother", "estate", "chwee"]

    def test_it_drifts_from_a_full_run_which_is_why_refresh_exists(self) -> None:
        """The paper is explicit that dynamic updates diverge and "periodic
        community refreshes remain necessary". This records the divergence
        rather than pretending the cheap path is equivalent.

        Milo belongs to both the shop and the estate. The dynamic step sees
        only its immediate neighbours and puts it with the shop; a full run,
        which can see that the estate side pulls harder once every label has
        settled, puts it with the estate. Same entity, two answers — and the
        cheap one is the one the family sees until the refresh runs.
        """
        facts = [*FACTS, fact("f5", "milo", "shop"), fact("f6", "milo", "estate")]

        extended = extend("milo", self._existing(), facts)
        full = detect([*ENTITIES, entity("milo", "Milo")], facts)

        dynamic_home = next(c.member_ids for c in extended if "milo" in c.member_ids)
        refreshed_home = next(c for c in full if "milo" in c)

        assert "shop" in dynamic_home
        assert "estate" in refreshed_home
        assert set(dynamic_home) != set(refreshed_home)

    def test_a_bridging_entity_does_not_collapse_two_chapters(self) -> None:
        """One shared thing between the shop years and the estate childhood is
        not enough to make them one part of her life."""
        facts = [*FACTS, fact("f5", "milo", "shop"), fact("f6", "milo", "estate")]

        assert len(detect([*ENTITIES, entity("milo", "Milo")], facts)) == 2


class TestBuildCommunities:
    class Namer:
        def describe(self, members, facts):  # noqa: ANN001, ARG002
            return CommunitySummary(
                name=f"Chapter of {len(members)}", summary="what it was"
            )

    def test_chapters_are_named(self) -> None:
        built = build_communities(ENTITIES, FACTS, self.Namer())

        assert all(c.name for c in built)

    def test_the_biggest_chapter_comes_first(self) -> None:
        facts = [*FACTS, fact("f5", "milo", "shop")]
        entities = [*ENTITIES, entity("milo", "Milo")]

        built = build_communities(entities, facts, self.Namer())

        assert built[0].size >= built[-1].size

    def test_it_works_without_a_namer(self) -> None:
        """Clustering must not depend on a model being reachable."""
        built = build_communities(ENTITIES, FACTS)

        assert len(built) == 2
        assert all(c.name == "" for c in built)


class TestTheNarratorIsAHub:
    """She is the subject of most facts in her own archive."""

    def _hub_facts(self) -> list[Fact]:
        """A fact about her and nearly everyone else, as the real archive has."""
        return [
            fact(f"h{i}", "her", other)
            for i, other in enumerate(
                ["shop", "estate", "father", "mother", "husband", "chwee"]
            )
        ]

    def test_left_in_she_collapses_her_whole_life_into_one_chapter(self) -> None:
        """The estate childhood and the shop years share nothing but her — and
        connected to everyone, she is enough to join everything to everything."""
        entities = [*ENTITIES, entity("her", "Ah Khim")]

        clusters = detect(entities, [*FACTS, *self._hub_facts()])

        assert len(clusters) == 1
        assert len(clusters[0]) == 7

    def test_left_out_the_chapters_separate_again(self) -> None:
        entities = [*ENTITIES, entity("her", "Ah Khim")]

        clusters = detect(entities, [*FACTS, *self._hub_facts()], exclude={"her"})

        assert {frozenset(c) for c in clusters} == {
            frozenset({"father", "husband", "shop"}),
            frozenset({"mother", "estate", "chwee"}),
        }

    def test_she_appears_in_no_chapter_of_her_own_archive(self) -> None:
        """Not a loss: she belongs to all of them, which is exactly why she
        cannot be used to tell them apart."""
        entities = [*ENTITIES, entity("her", "Ah Khim")]

        clusters = detect(entities, [*FACTS, *self._hub_facts()], exclude={"her"})

        assert all("her" not in c for c in clusters)


class TestFindingTheHub:
    """Found by dominance, and structurally.

    A name match silently excluded nobody in the real archive -- the narrator
    entity is "Ah Khim" and the household record says "Lim Siew Khim" -- and a
    filter that quietly does nothing is worse than no filter, because the
    chapters look computed either way.
    """

    def test_the_outlier_is_found(self) -> None:
        entities = [*ENTITIES, entity("her", "Ah Khim")]
        hub = [
            fact(f"h{i}", "her", other)
            for i, other in enumerate(
                ["shop", "estate", "father", "mother", "husband", "chwee"]
            )
        ]

        assert hub_entities(entities, [*FACTS, *hub]) == {"her"}

    def test_a_merely_busy_node_is_left_alone(self) -> None:
        """The coffee shop connects three people and is still a chapter, not a
        hub. "At least half the graph" would have thrown it out."""
        assert hub_entities(ENTITIES, FACTS) == set()

    def test_a_graph_too_small_to_judge_is_left_alone(self) -> None:
        assert hub_entities(ENTITIES[:2], FACTS[:1]) == set()
