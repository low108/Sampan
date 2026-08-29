"""Family corrections — the other half of feedback capture.

The agent learns from her silently. It cannot learn that "my sister" is called
Lim Siew Choo unless her son says so, and he is the one reading the archive.
"""

from __future__ import annotations

import pytest

from sampan.corrections import (
    Correction,
    CorrectionKind,
    apply_correction,
    duplicate_candidates,
    needs_confirmation,
)
from sampan.models import Entity, EntityType
from sampan.repository import Repository
from sampan.store import InMemoryDocumentStore

NARRATOR = "ah_khim"


def person(
    entity_id: str,
    name: str,
    *,
    role: str | None = None,
    detail: str = "",
    provisional: bool = True,
) -> Entity:
    return Entity(
        entity_id=entity_id,
        type=EntityType.PERSON,
        canonical_name=name,
        role=role,
        detail=detail,
        provisional=provisional,
    )


@pytest.fixture
def repository() -> Repository:
    repo = Repository(InMemoryDocumentStore())
    repo.save_entities(
        NARRATOR,
        [
            person(
                "e_sister", "my sister", role="sister", detail="cooks it more like hers"
            ),
            person("e_ahsui", "Ah Chwee", role="neighbour", provisional=True),
            person("e_ahsui2", "Ong Ah Chwee", role="neighbour", provisional=True),
            Entity(
                entity_id="e_father",
                type=EntityType.PERSON,
                canonical_name="Lim Ah Hock",
                role="father",
                provisional=False,
                confirmed_by_family=True,
            ),
        ],
    )
    return repo


def entities_by_id(repository: Repository) -> dict[str, Entity]:
    return {e.entity_id: e for e in repository.load_entities(NARRATOR)}


class TestRenaming:
    def test_a_corrected_name_replaces_the_canonical_one(
        self, repository: Repository
    ) -> None:
        apply_correction(
            repository,
            NARRATOR,
            Correction(
                kind=CorrectionKind.ENTITY_NAME,
                target="e_sister",
                value="Lim Siew Choo",
            ),
        )

        assert entities_by_id(repository)["e_sister"].canonical_name == "Lim Siew Choo"

    def test_the_name_she_uses_survives_as_an_alias(
        self, repository: Repository
    ) -> None:
        """She will go on saying "my sister". The archive must keep resolving it."""
        apply_correction(
            repository,
            NARRATOR,
            Correction(
                kind=CorrectionKind.ENTITY_NAME,
                target="e_sister",
                value="Lim Siew Choo",
            ),
        )

        assert entities_by_id(repository)["e_sister"].knows("my sister")

    def test_a_correction_confirms_the_entity(self, repository: Repository) -> None:
        apply_correction(
            repository,
            NARRATOR,
            Correction(
                kind=CorrectionKind.ENTITY_NAME, target="e_ahsui", value="Ong Ah Chwee"
            ),
        )

        corrected = entities_by_id(repository)["e_ahsui"]
        assert corrected.confirmed_by_family
        assert not corrected.provisional

    def test_correcting_something_that_does_not_exist_fails_cleanly(
        self, repository: Repository
    ) -> None:
        result = apply_correction(
            repository,
            NARRATOR,
            Correction(kind=CorrectionKind.ENTITY_NAME, target="nope", value="x"),
        )

        assert result.applied is False


class TestMerging:
    def test_merging_keeps_both_names(self, repository: Repository) -> None:
        """The resolver splits rather than guesses; merging is the family's
        half of that bargain."""
        apply_correction(
            repository,
            NARRATOR,
            Correction(
                kind=CorrectionKind.MERGE, target="e_ahsui2", merge_into="e_ahsui"
            ),
        )

        survivor = entities_by_id(repository)["e_ahsui"]
        assert survivor.knows("Ah Chwee")
        assert survivor.knows("Ong Ah Chwee")

    def test_the_duplicate_is_tombstoned_not_deleted(
        self, repository: Repository
    ) -> None:
        """Old stories still reference it, and the merge stays reversible."""
        apply_correction(
            repository,
            NARRATOR,
            Correction(
                kind=CorrectionKind.MERGE, target="e_ahsui2", merge_into="e_ahsui"
            ),
        )

        assert entities_by_id(repository)["e_ahsui2"].merged_into == "e_ahsui"

    def test_mention_counts_are_combined(self, repository: Repository) -> None:
        apply_correction(
            repository,
            NARRATOR,
            Correction(
                kind=CorrectionKind.MERGE, target="e_ahsui2", merge_into="e_ahsui"
            ),
        )

        assert entities_by_id(repository)["e_ahsui"].mention_count >= 0

    def test_an_entity_cannot_be_merged_into_itself(
        self, repository: Repository
    ) -> None:
        result = apply_correction(
            repository,
            NARRATOR,
            Correction(
                kind=CorrectionKind.MERGE, target="e_ahsui", merge_into="e_ahsui"
            ),
        )

        assert result.applied is False


class TestWhatNeedsAttention:
    def test_only_unconfirmed_entities_are_offered(
        self, repository: Repository
    ) -> None:
        pending = needs_confirmation(repository.load_entities(NARRATOR))

        names = {e.canonical_name for e in pending}
        assert "Lim Ah Hock" not in names
        assert "Ah Chwee" in names

    def test_a_merged_entity_stops_being_offered(self, repository: Repository) -> None:
        apply_correction(
            repository,
            NARRATOR,
            Correction(
                kind=CorrectionKind.MERGE, target="e_ahsui2", merge_into="e_ahsui"
            ),
        )

        pending = needs_confirmation(repository.load_entities(NARRATOR))
        assert "Ong Ah Chwee" not in {e.canonical_name for e in pending}

    def test_two_people_with_one_role_are_surfaced_not_merged(
        self, repository: Repository
    ) -> None:
        """A wrong merge is unrecoverable; a wrong split is one click. So the
        pair is shown, never resolved automatically."""
        pairs = duplicate_candidates(repository.load_entities(NARRATOR))

        assert any(
            {a.entity_id, b.entity_id} == {"e_ahsui", "e_ahsui2"} for a, b in pairs
        )


class TestPlaces:
    def confirm(self, repository: Repository) -> dict:
        apply_correction(
            repository,
            NARRATOR,
            Correction(
                kind=CorrectionKind.PLACE,
                target="Sungai Siput",
                value="Sungai Siput, Perak",
                by="Wei Lun",
            ),
        )
        return repository._store.get("_places", "Sungai Siput")  # noqa: SLF001

    def test_a_confirmed_place_is_trusted_afterwards(
        self, repository: Repository
    ) -> None:
        """Sungai Siput resolved to the wrong town. Once her son fixes it, the map
        should stop guessing."""
        repository._store.put(  # noqa: SLF001
            "_places",
            "Sungai Siput",
            {
                "raw_name": "Sungai Siput",
                "lat": 4.8,
                "lng": 101.07,
                "precision": "town",
                "confidence": 0.6,
            },
        )

        cached = self.confirm(repository)

        assert cached["precision"] == "exact"
        assert "Wei Lun" in cached["note"]

    def test_confirming_keeps_the_coordinates(self, repository: Repository) -> None:
        """Confirming used to write a fresh record and drop lat/lng, and a place
        with no coordinates is not locatable -- so confirming a pin removed it
        from the map, and `_resolve_places` never retries a cached name."""
        repository._store.put(  # noqa: SLF001
            "_places",
            "Sungai Siput",
            {
                "raw_name": "Sungai Siput",
                "lat": 4.8,
                "lng": 101.07,
                "precision": "town",
                "confidence": 0.6,
            },
        )

        cached = self.confirm(repository)

        assert (cached["lat"], cached["lng"]) == (4.8, 101.07)

    def test_confirming_something_never_located_is_not_called_exact(
        self, repository: Repository
    ) -> None:
        """No coordinates, no exactness. Claiming it would freeze the place in
        the cache as trusted-and-unmappable; left unknown, the better name the
        family just supplied gets resolved on the next look."""
        cached = self.confirm(repository)

        assert cached["precision"] == "unknown"
        assert cached["display_name"] == "Sungai Siput, Perak"


class TestTheResolverIsAskedOnce:
    """A cache that re-asks is not a cache.

    `_resolve_places` retried every cached entry with no coordinates, on the
    grounds that holding an unlocatable one would strand a story off the map
    forever. True for a place the family has renamed. False, and expensive, for
    "house" and "the shop": the resolver has already looked at those and there
    is nothing new to tell it, so the retry was permanent. Four such names in a
    real archive made the map view take six seconds against the feed's four
    hundred milliseconds -- on every load, for the whole life of the archive.

    Asserted by counting resolver calls, because the old behaviour was correct
    in every observable way except what it cost.
    """

    class CountingResolver:
        def __init__(self) -> None:
            self.asked: list[list[str]] = []

        def resolve(self, names: list[str]):
            self.asked.append(list(names))
            return []

    def _cards(self, *names: str):
        from sampan.family import StoryCard

        return [
            StoryCard(
                story_id=f"s{i}",
                title="t",
                domain="home",
                pin_type="place",
                narrative="n",
                sense_detail="",
                when_said="",
                where_said=name,
            )
            for i, name in enumerate(names)
        ]

    def _resolve(self, store, cards, resolver):
        import sampan.app as app_module
        from sampan.config import Settings

        settings = Settings(GOOGLE_CLOUD_PROJECT="p")
        original = app_module.GeminiPlaceResolver
        app_module.GeminiPlaceResolver = lambda _s: resolver
        try:
            return app_module._resolve_places(settings, store, cards)  # noqa: SLF001
        finally:
            app_module.GeminiPlaceResolver = original

    def test_a_name_already_found_unplaceable_is_not_asked_again(self) -> None:
        from sampan.store import InMemoryDocumentStore

        store = InMemoryDocumentStore()
        store.put(
            "_places",
            "the shop",
            {"raw_name": "the shop", "precision": "unknown", "note": "generic"},
        )
        resolver = self.CountingResolver()

        self._resolve(store, self._cards("the shop"), resolver)

        assert resolver.asked == []

    def test_a_name_the_family_renamed_is_asked_again(self) -> None:
        """The one case with new information in it."""
        from sampan.store import InMemoryDocumentStore

        store = InMemoryDocumentStore()
        store.put(
            "_places",
            "the shop",
            {
                "raw_name": "the shop",
                "precision": "unknown",
                "display_name": "Kedai Kopi Lam Kee, Ipoh",
                "needs_retry": True,
            },
        )
        resolver = self.CountingResolver()

        self._resolve(store, self._cards("the shop"), resolver)

        assert resolver.asked == [["Kedai Kopi Lam Kee, Ipoh"]]

    def test_an_uncached_name_is_still_asked(self) -> None:
        from sampan.store import InMemoryDocumentStore

        resolver = self.CountingResolver()

        self._resolve(InMemoryDocumentStore(), self._cards("Ipoh"), resolver)

        assert resolver.asked == [["Ipoh"]]

    def test_an_unplaceable_name_still_reaches_the_caller(self) -> None:
        """Kept rather than dropped: the story has to be able to say the place
        is one nobody could find, which is different from having no place."""
        from sampan.store import InMemoryDocumentStore

        store = InMemoryDocumentStore()
        store.put(
            "_places",
            "the shop",
            {"raw_name": "the shop", "precision": "unknown", "note": "generic"},
        )

        places = self._resolve(store, self._cards("the shop"), self.CountingResolver())

        assert [p.raw_name for p in places] == ["the shop"]
