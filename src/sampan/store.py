"""Document storage.

A narrow protocol over Firestore so the pipeline can be exercised without a
cloud project. The real implementation is constructed lazily, because importing
the app must not require credentials.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Protocol, runtime_checkable

from sampan.config import Settings, get_settings

Document = dict[str, Any]


@runtime_checkable
class DocumentStore(Protocol):
    """The only storage surface the rest of the application knows about."""

    @property
    def backend(self) -> str:
        """Name of the backing store, surfaced so a green smoke test cannot be
        mistaken for a Firestore round trip."""
        ...

    def put(self, collection: str, doc_id: str, data: Document) -> None: ...

    def get(self, collection: str, doc_id: str) -> Document | None: ...

    def list(self, collection: str) -> list[Document]: ...


class InMemoryDocumentStore:
    """Test double, and the local-development store when explicitly enabled."""

    backend = "memory"

    def __init__(self) -> None:
        self._data: dict[str, dict[str, Document]] = {}

    def put(self, collection: str, doc_id: str, data: Document) -> None:
        self._data.setdefault(collection, {})[doc_id] = dict(data)

    def get(self, collection: str, doc_id: str) -> Document | None:
        found = self._data.get(collection, {}).get(doc_id)
        return dict(found) if found is not None else None

    def list(self, collection: str) -> list[Document]:
        return [dict(d) for d in self._data.get(collection, {}).values()]


class FirestoreDocumentStore:
    """Firestore-backed store.

    The client is built on first use, not on construction: opening a gRPC
    channel and refreshing credentials is expensive, and deciding *which* store
    to use should not require credentials.
    """

    backend = "firestore"

    def __init__(self, project_id: str, database: str) -> None:
        self._project_id = project_id
        self._database = database
        self._cached_client: Any | None = None

    @property
    def _client(self) -> Any:
        if self._cached_client is None:
            from google.cloud import firestore

            self._cached_client = firestore.Client(
                project=self._project_id, database=self._database
            )
        return self._cached_client

    def put(self, collection: str, doc_id: str, data: Document) -> None:
        self._client.collection(collection).document(doc_id).set(data)

    def get(self, collection: str, doc_id: str) -> Document | None:
        snapshot = self._client.collection(collection).document(doc_id).get()
        return snapshot.to_dict() if snapshot.exists else None

    def list(self, collection: str) -> list[Document]:
        return [d.to_dict() or {} for d in self._client.collection(collection).stream()]


def build_store(settings: Settings) -> DocumentStore:
    """Firestore when a project is configured; in-memory only on explicit opt-in.

    The fallback is not automatic. A deployed revision that lost its project id
    must fail loudly rather than accept stories into a dictionary and report
    success — the same fail-closed posture as the API key check.
    """
    if settings.configured:
        return FirestoreDocumentStore(settings.project_id, settings.firestore_database)
    if settings.allow_in_memory_store:
        return InMemoryDocumentStore()
    raise RuntimeError(
        "No GOOGLE_CLOUD_PROJECT configured. Set it, or set "
        "SAMPAN_ALLOW_IN_MEMORY_STORE=true for local development."
    )


@lru_cache(maxsize=1)
def get_document_store() -> DocumentStore:
    """Process-wide store.

    Cached because constructing a Firestore client opens a gRPC channel and
    refreshes credentials; doing that per request leaks channels and threads
    under concurrency.
    """
    return build_store(get_settings())
