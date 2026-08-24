"""The graph demo, asserted at the HTTP boundary.

Retrieve, create and retire, driven the way the panel drives them. The three
defects these cover were all found by clicking, not by the suite: a sentence
that named nobody returned 422, an invented edge was attached to whichever
node happened to be first, and a created edge that did not match the current
question was scored and then not drawn.

The sandbox assertion is the one that matters most. The product's rule is that
the family may correct the system and never her, so a demo that wrote into her
archive would break the promise the whole thing rests on.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from sampan.app import _short, create_app, get_store
from sampan.auth import API_KEY_HEADER
from sampan.config import Settings, get_settings
from sampan.entities import Entity, EntityType
from sampan.facts import Fact, Predicate
from sampan.repository import Repository
from sampan.store import InMemoryDocumentStore

GOOD_KEY = "test-key-do-not-use-in-anger"
NARRATOR = "siew_khim"


@pytest.fixture
def store() -> InMemoryDocumentStore:
    memory = InMemoryDocumentStore()
    repository = Repository(memory)
    repository.save_entities(
        NARRATOR,
        [
            Entity(
                entity_id="e_khim", canonical_name="Ah Khim", type=EntityType.PERSON
            ),
            Entity(
                entity_id="e_chwee",
                canonical_name="Ah Chwee",
                type=EntityType.PERSON,
                aliases=["Chwee"],
            ),
            Entity(
                entity_id="e_siput",
                canonical_name="Sungai Siput",
                type=EntityType.PLACE,
            ),
            Entity(
                entity_id="e_shop", canonical_name="coffee shop", type=EntityType.PLACE
            ),
            # Nothing connects to this one, so an edge hung on it is out of
            # reach of any question about Ah Chwee.
            Entity(
                entity_id="e_far", canonical_name="Jalan Bandar", type=EntityType.PLACE
            ),
        ],
    )
    repository.save_facts(
        NARRATOR,
        [
            Fact(
                fact_id="f_next_door",
                subject_id="e_chwee",
                predicate=Predicate.NEIGHBOUR_OF,
                object_id="e_khim",
                statement="Ah Chwee lived next door in the line houses.",
                quote="Ah Chwee lived next door.",
                episode_id="ep1",
            ),
            Fact(
                fact_id="f_siput",
                subject_id="e_chwee",
                predicate=Predicate.LIVED_AT,
                object_id="e_siput",
                statement="Ah Chwee lives in Sungai Siput.",
                quote="She is in Sungai Siput now.",
                episode_id="ep1",
            ),
            Fact(
                fact_id="f_shop",
                subject_id="e_khim",
                predicate=Predicate.WORKED_AT,
                object_id="e_shop",
                statement="She worked at the coffee shop.",
                quote="I worked at the shop.",
                episode_id="ep2",
            ),
        ],
    )
    return memory


@pytest.fixture
def client(store: InMemoryDocumentStore) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        GOOGLE_CLOUD_PROJECT="", SAMPAN_API_KEY=GOOD_KEY
    )
    app.dependency_overrides[get_store] = lambda: store
    with TestClient(app) as client:
        yield client


def search(client: TestClient, question: str, **sandbox: object) -> dict:
    response = client.post(
        f"/api/family/{NARRATOR}/search",
        json={"question": question, **sandbox},
        headers={API_KEY_HEADER: GOOD_KEY},
    )
    assert response.status_code == 200, response.text
    return response.json()


class TestRetrieve:
    def test_names_the_entity_the_question_mentions(self, client: TestClient) -> None:
        body = search(client, "who is Ah Chwee")

        assert body["trace"]["seeds"] == ["e_chwee"]

    def test_returns_the_facts_about_that_entity(self, client: TestClient) -> None:
        body = search(client, "who is Ah Chwee")

        ranked = [e["statement"] for e in body["edges"] if e["rank"] is not None]
        assert "Ah Chwee lived next door in the line houses." in ranked

    def test_shows_the_terms_it_dropped(self, client: TestClient) -> None:
        """Under three letters the index would match on the honorific alone."""
        body = search(client, "who is Ah Chwee")

        assert "ah" in body["trace"]["dropped"]
        assert "chwee" in body["trace"]["terms"]

    def test_the_same_question_twice_gives_the_same_numbers(
        self, client: TestClient
    ) -> None:
        """The only claim the panel makes. No model is in this path."""
        first = search(client, "who is Ah Chwee")
        second = search(client, "who is Ah Chwee")

        assert first["trace"]["candidates"] == second["trace"]["candidates"]

    def test_a_question_that_names_nobody_still_traces(
        self, client: TestClient
    ) -> None:
        """The case most worth explaining: nothing found, and why."""
        body = search(client, "who is Ah Seng")

        assert body["trace"]["seeds"] == []
        assert [e for e in body["edges"] if e["rank"] is not None] == []


class TestCreate:
    def test_an_invented_edge_lands_on_the_node_it_names(
        self, client: TestClient
    ) -> None:
        body = search(
            client,
            "who is Ah Chwee",
            added=[
                {
                    "subject_id": "e_chwee",
                    "predicate": "worked_at",
                    "statement": "Ah Chwee sold noodles at the morning market.",
                }
            ],
        )

        edge = next(e for e in body["edges"] if e["fact_id"] == "demo_0")
        assert edge["source"] == "e_chwee"

    def test_a_sentence_naming_nobody_invents_both_ends(
        self, client: TestClient
    ) -> None:
        """It used to 422, and before that it attached to an arbitrary node --
        drawing a relationship the sentence never claimed."""
        body = search(
            client,
            "who is Ah Chwee",
            added=[
                {
                    "subject_id": "",
                    "predicate": "worked_at",
                    "statement": "Someone new arrived from the village.",
                }
            ],
        )

        edge = next(e for e in body["edges"] if e["fact_id"] == "demo_0")
        invented = {n["id"] for n in body["nodes"] if n["invented"]}
        assert edge["source"] in invented
        assert edge["target"] in invented

    def test_a_created_edge_is_drawn_even_when_it_does_not_rank(
        self, client: TestClient
    ) -> None:
        """An edge that vanishes because it does not match the current question
        is indistinguishable from one that failed to be added at all."""
        body = search(
            client,
            "who is Ah Chwee",
            added=[
                {
                    "subject_id": "e_far",
                    "predicate": "ate",
                    "statement": "Durian season came late that year.",
                }
            ],
        )

        edge = next(e for e in body["edges"] if e["fact_id"] == "demo_0")
        assert edge["rank"] is None

    def test_it_competes_for_rank_with_no_special_treatment(
        self, client: TestClient
    ) -> None:
        body = search(
            client,
            "who is Ah Chwee",
            added=[
                {
                    "subject_id": "e_chwee",
                    "predicate": "worked_at",
                    "statement": "Ah Chwee sold noodles at the morning market.",
                }
            ],
        )

        scored = {c["fact_id"] for c in body["trace"]["candidates"]}
        assert "demo_0" in scored

    def test_the_invented_node_gets_a_label_that_fits(self, client: TestClient) -> None:
        """It was labelled with the whole sentence, which ran off the drawing."""
        body = search(
            client,
            "who is Ah Chwee",
            added=[
                {
                    "subject_id": "e_chwee",
                    "predicate": "worked_at",
                    "statement": "Ah Chwee sold noodles at the morning market in Ipoh.",
                }
            ],
        )

        label = next(n["name"] for n in body["nodes"] if n["id"] == "demo_node_0")
        assert len(label) <= 27
        assert label.endswith("…")

    def test_nothing_is_written_to_her_archive(
        self, client: TestClient, store: InMemoryDocumentStore
    ) -> None:
        """The family may correct the system and never her."""
        before = Repository(store).load_facts(NARRATOR, current_only=False)

        search(
            client,
            "who is Ah Chwee",
            added=[
                {
                    "subject_id": "e_chwee",
                    "predicate": "worked_at",
                    "statement": "Ah Chwee sold noodles at the morning market.",
                }
            ],
        )

        assert Repository(store).load_facts(NARRATOR, current_only=False) == before


class TestUpdate:
    def test_a_retired_fact_leaves_the_ranking(self, client: TestClient) -> None:
        body = search(client, "who is Ah Chwee", retired=["f_siput"])

        ranked = [e["statement"] for e in body["edges"] if e["rank"] is not None]
        assert "Ah Chwee lives in Sungai Siput." not in ranked

    def test_it_is_reported_as_no_longer_asserted(self, client: TestClient) -> None:
        """Stage four. Kept, and the archive stops standing behind it."""
        body = search(client, "who is Ah Chwee", retired=["f_siput"])

        retired = {r["fact_id"] for r in body["trace"]["retired"]}
        assert "f_siput" in retired

    def test_it_is_still_drawn(self, client: TestClient) -> None:
        body = search(client, "who is Ah Chwee", retired=["f_siput"])

        edge = next(e for e in body["edges"] if e["fact_id"] == "f_siput")
        assert edge["retired"] is True

    def test_it_moves_in_transaction_time_only(self, client: TestClient) -> None:
        """Valid time is what she said, and a demo does not get to imply she
        was wrong about her own life."""
        body = search(client, "who is Ah Chwee", retired=["f_siput"])

        edge = next(e for e in body["edges"] if e["fact_id"] == "f_siput")
        assert edge["superseded_by"] == "demo"

    def test_nothing_is_written_to_her_archive(
        self, client: TestClient, store: InMemoryDocumentStore
    ) -> None:
        search(client, "who is Ah Chwee", retired=["f_siput"])

        kept = Repository(store).load_facts(NARRATOR)
        assert "f_siput" in {f.fact_id for f in kept}


class TestShortLabel:
    def test_leaves_a_name_alone(self) -> None:
        assert _short("Sungai Siput") == "Sungai Siput"

    def test_cuts_a_clause_at_a_word_boundary(self) -> None:
        assert _short("Ah Chwee sold noodles at the market", 20) == "Ah Chwee sold…"

    def test_cuts_a_single_long_word_rather_than_returning_nothing(self) -> None:
        assert _short("a" * 40, 10) == "aaaaaaaaaa…"
