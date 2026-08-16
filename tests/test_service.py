"""Ticket 1 — the walking skeleton, asserted at the HTTP boundary."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from sampan.app import SMOKE_COLLECTION, create_app, get_store
from sampan.auth import API_KEY_HEADER
from sampan.config import Settings, get_settings
from sampan.store import InMemoryDocumentStore

GOOD_KEY = "test-key-do-not-use-in-anger"


@pytest.fixture
def store() -> InMemoryDocumentStore:
    return InMemoryDocumentStore()


def build_client(
    store: InMemoryDocumentStore, *, api_key: str = GOOD_KEY
) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        GOOGLE_CLOUD_PROJECT="", SAMPAN_API_KEY=api_key
    )
    app.dependency_overrides[get_store] = lambda: store
    with TestClient(app) as client:
        yield client


@pytest.fixture
def client(store: InMemoryDocumentStore) -> Iterator[TestClient]:
    yield from build_client(store)


@pytest.fixture
def keyless_client(store: InMemoryDocumentStore) -> Iterator[TestClient]:
    yield from build_client(store, api_key="")


class TestHealth:
    def test_is_public(self, client: TestClient) -> None:
        response = client.get("/healthz")

        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_reports_whether_cloud_is_configured(self, client: TestClient) -> None:
        assert client.get("/healthz").json()["configured"] is False


class TestSmokeAuth:
    def test_rejects_a_request_with_no_key(self, client: TestClient) -> None:
        response = client.post("/debug/smoke", json={"note": "hi"})

        assert response.status_code == 401

    def test_rejects_a_request_with_the_wrong_key(self, client: TestClient) -> None:
        response = client.post(
            "/debug/smoke", json={"note": "hi"}, headers={API_KEY_HEADER: "nope"}
        )

        assert response.status_code == 401

    def test_refuses_to_serve_when_no_key_is_configured(
        self, keyless_client: TestClient
    ) -> None:
        """A misconfigured deploy must fail closed, not serve an open endpoint."""
        response = keyless_client.post(
            "/debug/smoke", json={"note": "hi"}, headers={API_KEY_HEADER: "anything"}
        )

        assert response.status_code == 503


class TestSmokeRoundTrip:
    def test_writes_a_document_and_reads_it_back(self, client: TestClient) -> None:
        response = client.post(
            "/debug/smoke",
            json={"note": "板底街的咖啡店"},
            headers={API_KEY_HEADER: GOOD_KEY},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["round_trip_ok"] is True
        assert body["read_back"]["note"] == "板底街的咖啡店"

    def test_the_document_persists_beyond_the_request(
        self, client: TestClient, store: InMemoryDocumentStore
    ) -> None:
        doc_id = client.post(
            "/debug/smoke", json={"note": "hi"}, headers={API_KEY_HEADER: GOOD_KEY}
        ).json()["doc_id"]

        assert store.get(SMOKE_COLLECTION, doc_id) is not None

    def test_each_call_writes_a_new_document(
        self, client: TestClient, store: InMemoryDocumentStore
    ) -> None:
        for _ in range(3):
            client.post(
                "/debug/smoke", json={"note": "hi"}, headers={API_KEY_HEADER: GOOD_KEY}
            )

        assert len(store.list(SMOKE_COLLECTION)) == 3
