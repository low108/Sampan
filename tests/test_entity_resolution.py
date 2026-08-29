"""Entity resolution — deterministic, no model call.

The behaviour that matters: she refers to one person three different ways
across three sessions, and the archive must hold one person.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sampan.entities import Tiebreaker, resolve_mentions
from sampan.models import Entity, EntityMention, EntityType, kin_role, normalise

INTAKE = Path(__file__).resolve().parents[1] / "seeds" / "intake.json"


@pytest.fixture(scope="module")
def intake() -> list[Entity]:
    raw = json.loads(INTAKE.read_text(encoding="utf-8"))
    return [Entity.model_validate(e) for e in raw["entities"]]


def person(surface: str, role: str | None = None, detail: str = "") -> EntityMention:
    return EntityMention(
        surface_form=surface, type=EntityType.PERSON, role=role, detail=detail
    )


def place(surface: str, detail: str = "") -> EntityMention:
    return EntityMention(surface_form=surface, type=EntityType.PLACE, detail=detail)


class TestNormalisation:
    @pytest.mark.parametrize(
        ("surface", "expected"),
        [
            ("my sister", "sister"),
            ("sister", "sister"),
            ("My Sister", "sister"),
            ("my sister's", "sister"),
            ("the shop", "shop"),
            ("that shop", "shop"),
        ],
    )
    def test_strips_possessives_and_padding(self, surface: str, expected: str) -> None:
        assert normalise(surface) == expected

    def test_leaves_a_bare_name_alone(self) -> None:
        assert normalise("Lim Siew Choo") == "lim siew choo"

    def test_collapses_stray_whitespace(self) -> None:
        assert normalise("  my   elder  sister ") == "elder sister"

    def test_does_not_strip_a_name_down_to_nothing(self) -> None:
        assert normalise("my") == "my"


class TestKinTerms:
    @pytest.mark.parametrize(
        ("surface", "role"),
        [
            ("my mother", "mother"),
            ("Mum", "mother"),
            ("my father", "father"),
            ("Ah Pa", "father"),
            ("my sister", "sister"),
            ("my elder sister", "sister"),
            ("Ah Gong", "grandfather"),
        ],
    )
    def test_maps_kin_terms_to_roles(self, surface: str, role: str) -> None:
        assert kin_role(surface) == role

    def test_a_name_is_not_a_kin_term(self) -> None:
        assert kin_role("Ah Chwee") is None


class TestResolvingAgainstIntake:
    def test_resolves_a_kin_term_to_the_person_the_family_named(
        self, intake: list[Entity]
    ) -> None:
        """She says "my sister"; the family already told us that is Siew Choo."""
        result = resolve_mentions([person("my sister")], intake)

        assert result.resolutions[0].entity_id == "ent_sister"
        assert result.resolutions[0].created is False

    def test_resolves_an_alias_the_family_supplied(self, intake: list[Entity]) -> None:
        result = resolve_mentions([person("Ah Fatt")], intake)

        assert result.resolutions[0].entity_id == "ent_husband"
        assert result.resolutions[0].matched_by == "alias"

    def test_three_ways_of_saying_one_person_stay_one_person(
        self, intake: list[Entity]
    ) -> None:
        """The behaviour the whole module exists for."""
        result = resolve_mentions(
            [person("my sister"), person("Ah Choo"), person("Lim Siew Choo")], intake
        )

        assert {r.entity_id for r in result.resolutions} == {"ent_sister"}
        assert not result.created

    def test_a_new_name_becomes_a_provisional_entity(
        self, intake: list[Entity]
    ) -> None:
        """Ah Chwee the neighbour is not in the intake, so he is created and
        flagged for the family to confirm."""
        result = resolve_mentions([person("Ah Chwee", role="neighbour")], intake)

        assert result.resolutions[0].created is True
        created = result.created[0]
        assert created.canonical_name == "Ah Chwee"
        assert created.role == "neighbour"
        assert created in result.needs_confirmation

    def test_an_unknown_form_is_not_guessed_onto_someone(
        self, intake: list[Entity]
    ) -> None:
        result = resolve_mentions([person("the old lady next door")], intake)

        assert result.resolutions[0].created is True

    def test_records_new_detail_on_a_person(self, intake: list[Entity]) -> None:
        result = resolve_mentions(
            [person("Ah Chwee", detail="next door, walks with a stick now")], intake
        )

        assert "stick" in result.created[0].detail


class TestPlaces:
    def test_matches_a_place_by_containment(self, intake: list[Entity]) -> None:
        """Jalan Bandar, Ipoh is in Ipoh."""
        result = resolve_mentions([place("Jalan Bandar, Ipoh")], intake)

        assert result.resolutions[0].entity_id == "ent_ipoh"
        assert result.resolutions[0].matched_by == "containment"

    def test_matches_an_alias(self, intake: list[Entity]) -> None:
        result = resolve_mentions([place("Ipoh town")], intake)

        assert result.resolutions[0].entity_id == "ent_ipoh"

    def test_an_unknown_place_is_created(self, intake: list[Entity]) -> None:
        result = resolve_mentions([place("Penang harbour")], intake)

        assert result.resolutions[0].created is True


class TestAmbiguity:
    def test_a_kin_term_with_two_candidates_does_not_guess(self) -> None:
        """Two sisters means "my sister" is genuinely ambiguous. Splitting is
        recoverable by a family merge; a wrong merge corrupts the archive
        silently."""
        two_sisters = [
            Entity(
                entity_id=f"ent_sister_{i}",
                type=EntityType.PERSON,
                canonical_name=name,
                role="sister",
                provisional=False,
            )
            for i, name in enumerate(["Lim Siew Choo", "Lim Siew Lan"])
        ]

        result = resolve_mentions([person("my sister")], two_sisters)

        assert result.resolutions[0].created is True

    def test_a_tiebreaker_can_resolve_what_the_cheap_signals_cannot(self) -> None:
        class AlwaysFirst(Tiebreaker):
            def choose(
                self, mention: EntityMention, candidates: list[Entity]
            ) -> str | None:
                return candidates[0].entity_id

        pool = [
            Entity(
                entity_id="ent_a",
                type=EntityType.PERSON,
                canonical_name="Lim Siew Choo",
                role="sister",
                provisional=False,
            )
        ]

        result = resolve_mentions(
            [person("that older lady")], pool, tiebreaker=AlwaysFirst()
        )

        assert result.resolutions[0].entity_id == "ent_a"
        assert result.resolutions[0].matched_by == "tiebreaker"


class TestCounting:
    def test_counts_mentions_across_a_conversation(self, intake: list[Entity]) -> None:
        result = resolve_mentions([person("my mother"), person("mother")], intake)

        mother = next(e for e in result.entities if e.entity_id == "ent_mother")
        assert mother.mention_count == 2

    def test_does_not_mutate_the_graph_it_was_given(self, intake: list[Entity]) -> None:
        before = intake[0].mention_count

        resolve_mentions([person("my father")], intake)

        assert intake[0].mention_count == before


class TestTheNarratorIsInHerOwnGraph:
    """She was not, and it cost her every fact about herself.

    `seeds/intake.json` names her father, mother, sister, husband, son,
    daughter, granddaughter, grandfather and two towns -- and not her. Fact
    extraction refuses any fact whose subject is unknown, so until some mention
    happened to invent her, no fact could be recorded about the person the
    product is about. Her real archive recovered by luck: something resolved
    her from a mention, and that entity now carries more facts than any other
    subject. Luck is not a design.
    """

    def test_a_narrator_with_no_graph_still_gets_herself(self) -> None:
        from sampan.entities import ensure_self

        entities = ensure_self(
            [], narrator_id="ah_khim", display_name="Lim Siew Khim"
        )

        assert len(entities) == 1
        assert entities[0].entity_id == "ent_self_ah_khim"
        assert entities[0].canonical_name == "Lim Siew Khim"
        # The given name too, because that is what her family call her and what
        # extraction will see in a transcript.
        assert "Siew Khim" in entities[0].aliases

    def test_she_is_not_provisional(self) -> None:
        """Provisional means "resolved from a mention, please confirm". Nobody
        guessed she exists."""
        from sampan.entities import ensure_self

        (me,) = ensure_self([], narrator_id="ah_khim", display_name="Lim Siew Khim")

        assert me.provisional is False
        assert me.confirmed_by_family is True

    def test_calling_it_twice_does_not_produce_two_of_her(self) -> None:
        from sampan.entities import ensure_self

        once = ensure_self([], narrator_id="ah_khim", display_name="Lim Siew Khim")
        twice = ensure_self(
            once, narrator_id="ah_khim", display_name="Lim Siew Khim"
        )

        assert len(twice) == 1

    def test_a_narrator_already_resolved_from_a_mention_is_not_duplicated(
        self,
    ) -> None:
        """The real archive resolved her before this existed, under a generated
        id. Adding a second her would split her facts across two subjects and
        silently break every comparison between them."""
        from sampan.entities import ensure_self
        from sampan.models import Entity, EntityType

        existing = [
            Entity(
                entity_id="ent_9ac4367c28b3",
                type=EntityType.PERSON,
                canonical_name="Ah Khim",
                aliases=["Lim Siew Khim"],
            )
        ]

        result = ensure_self(
            existing, narrator_id="ah_khim", display_name="Lim Siew Khim"
        )

        assert len(result) == 1
        assert result[0].entity_id == "ent_9ac4367c28b3"

    def test_someone_elses_entity_does_not_count_as_her(self) -> None:
        from sampan.entities import ensure_self
        from sampan.models import Entity, EntityType

        existing = [
            Entity(
                entity_id="ent_father",
                type=EntityType.PERSON,
                canonical_name="Lim Ah Hock",
            )
        ]

        result = ensure_self(
            existing, narrator_id="ah_khim", display_name="Lim Siew Khim"
        )

        assert {e.entity_id for e in result} == {"ent_father", "ent_self_ah_khim"}

    def test_an_unnamed_narrator_still_gets_an_entity(self) -> None:
        """Better a node called `ah_khim` than no node: without one, nothing
        about her can be recorded at all."""
        from sampan.entities import ensure_self

        (me,) = ensure_self([], narrator_id="ah_khim", display_name="")

        assert me.entity_id == "ent_self_ah_khim"
        assert me.canonical_name == "ah_khim"
