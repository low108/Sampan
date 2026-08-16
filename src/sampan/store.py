"""Document storage.

A narrow protocol over Firestore so the pipeline can be exercised without a
cloud project. The real implementation is constructed lazily, because importing
the app must not require credentials.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from sampan.config import Settings

Document = dict[str, Any]


@runtime_checkable
class DocumentStore(Protocol):
    """The only storage surface the rest of the application knows about."""

    def put(self, collection: str, doc_id: str, data: Document) -> None: ...

    def get(self, collection: str, doc_id: str) -> Document | None: ...

    def list(self, collection: str) -> list[Document]: ...


class InMemoryDocumentStore:
    """Test double. Also what the service falls back to when unconfigured."""

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
    """Firestore-backed store. Constructing this requires credentials."""

    def __init__(self, project_id: str, database: str) -> None:
        from google.cloud import firestore

        self._client = firestore.Client(project=project_id, database=database)

    def put(self, collection: str, doc_id: str, data: Document) -> None:
        self._client.collection(collection).document(doc_id).set(data)

    def get(self, collection: str, doc_id: str) -> Document | None:
        snapshot = self._client.collection(collection).document(doc_id).get()
        return snapshot.to_dict() if snapshot.exists else None

    def list(self, collection: str) -> list[Document]:
        return [d.to_dict() or {} for d in self._client.collection(collection).stream()]


def build_store(settings: Settings) -> DocumentStore:
    """Real store when a project is configured, in-memory otherwise.

    Falling back rather than raising keeps local development and the test suite
    runnable on a machine that has never seen a Google Cloud credential.
    """
    if not settings.configured:
        return InMemoryDocumentStore()
    return FirestoreDocumentStore(settings.project_id, settings.firestore_database)
