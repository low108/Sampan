"""Ticket 1 — the walking skeleton, asserted at the HTTP boundary."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from sampan.app import SMOKE_COLLECTION, create_app, get_store
from sampan.auth import API_KEY_HEADER
from sampan.config import Settings, get_settings
from sampan.store import InMemoryDocumentStore, build_store

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
        response = client.get("/health")

        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_reports_whether_cloud_is_configured(self, client: TestClient) -> None:
        assert client.get("/health").json()["configured"] is False


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

    def test_rejects_a_non_ascii_key_without_erroring(self, client: TestClient) -> None:
        """Starlette decodes headers as latin-1, so a high byte on the wire
        reaches us as a non-ASCII str — and compare_digest raises TypeError on
        those. That must be a 401, never an unhandled 500."""
        response = client.post(
            "/debug/smoke",
            json={"note": "hi"},
            headers={API_KEY_HEADER: b"k\xe9y-\xfc"},  # type: ignore[dict-item]
        )

        assert response.status_code == 401


class TestSmokeRoundTrip:
    def test_writes_a_document_and_reads_it_back(self, client: TestClient) -> None:
        response = client.post(
            "/debug/smoke",
            json={"note": "the coffee shop on Jalan Bandar"},
            headers={API_KEY_HEADER: GOOD_KEY},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["round_trip_ok"] is True
        assert body["read_back"]["note"] == "the coffee shop on Jalan Bandar"

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

    def test_names_the_backend_so_a_pass_cannot_be_misread(
        self, client: TestClient
    ) -> None:
        """round_trip_ok alone doesn't say what it round-tripped to."""
        body = client.post(
            "/debug/smoke", json={"note": "hi"}, headers={API_KEY_HEADER: GOOD_KEY}
        ).json()

        assert body["backend"] == "memory"
        assert client.get("/health").json()["backend"] == "memory"


class TestStoreSelection:
    def test_uses_firestore_when_a_project_is_configured(self) -> None:
        store = build_store(
            Settings(GOOGLE_CLOUD_PROJECT="a-project", SAMPAN_API_KEY=GOOD_KEY)
        )

        assert store.backend == "firestore"

    def test_refuses_to_fall_back_silently_when_unconfigured(self) -> None:
        """A deployed revision that lost its project id must fail loudly
        rather than accept stories into a dictionary and report success."""
        with pytest.raises(RuntimeError, match="GOOGLE_CLOUD_PROJECT"):
            build_store(Settings(GOOGLE_CLOUD_PROJECT="", SAMPAN_API_KEY=GOOD_KEY))

    def test_falls_back_only_on_explicit_opt_in(self) -> None:
        store = build_store(
            Settings(
                GOOGLE_CLOUD_PROJECT="",
                SAMPAN_API_KEY=GOOD_KEY,
                SAMPAN_ALLOW_IN_MEMORY_STORE=True,
            )
        )

        assert store.backend == "memory"


class TestStaticPages:
    """The pages 404'd on Cloud Run while every API route kept working, because
    the path was resolved relative to the installed package and the image never
    copied them. Both failures are invisible from a local checkout."""

    def test_the_pages_are_found(self) -> None:
        from sampan.app import find_static_dir

        found = find_static_dir()

        assert found is not None
        assert (found / "index.html").is_file()

    def test_the_image_copies_them(self) -> None:
        from pathlib import Path

        dockerfile = (Path(__file__).resolve().parents[1] / "Dockerfile").read_text(
            encoding="utf-8"
        )

        # Built in the image from web/ rather than copied from the working
        # tree, so a stale local build cannot ship.
        assert "COPY --from=web /static ./static" in dockerfile
        assert "npm run build" in dockerfile

    def test_every_asset_the_page_references_exists(self) -> None:
        """A missing script or stylesheet fails silently in the browser.

        The referenced names are read out of index.html rather than listed
        here, because the bundler content-hashes them: a hardcoded list goes
        stale on the next build and starts testing the wrong thing.
        """
        import re

        from sampan.app import find_static_dir

        static = find_static_dir()
        assert static is not None
        index = (static / "index.html").read_text(encoding="utf-8")

        referenced = re.findall(r'(?:src|href)="(/[^"]+)"', index)
        assert referenced, "index.html references nothing at all"
        for ref in referenced:
            assert (static / ref.lstrip("/")).is_file(), ref

    def test_the_audio_worklet_is_present(self) -> None:
        """Loaded by URL at the moment she taps record, not from index.html, so
        nothing references it until the microphone is already open."""
        from sampan.app import find_static_dir

        static = find_static_dir()
        assert static is not None
        assert (static / "worklet.js").is_file()


class TestPendingAsk:
    """What the bell is for.

    "Wei Lun asked you something" is the notification the whole product is
    built around: she taps it and the recording opens with his question
    already loaded. The endpoint behind it had no test, and shipped without
    ever sending the question.
    """

    def _leave_a_question(self, client: TestClient) -> None:
        client.post(
            "/api/family/ah_khim/ask",
            headers={API_KEY_HEADER: GOOD_KEY},
            json={
                "from_name": "Wei Lun",
                "question": "Did Ah Gong leave anything behind?",
            },
        )

    def _pending(self, client: TestClient) -> dict:
        return client.get(
            "/api/talk/ah_khim/pending", headers={API_KEY_HEADER: GOOD_KEY}
        ).json()

    def test_nothing_waiting_when_nobody_has_asked(self, client: TestClient) -> None:
        assert self._pending(client)["waiting"] is False

    def test_it_carries_the_question_itself(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Her name for him and his question. Without the question she is told
        that someone was thinking of her and not what they wanted to know."""
        monkeypatch.setattr("sampan.app.is_quiet", lambda _settings: False)
        self._leave_a_question(client)

        body = self._pending(client)

        assert body["waiting"] is True
        assert body["from_name"] == "Wei Lun"
        assert body["question"] == "Did Ah Gong leave anything behind?"

    def test_a_question_waits_until_morning(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Queued instantly, delivered when she is awake. The app has to be able
        to say why it is holding one, or tapping the bell looks broken."""
        monkeypatch.setattr("sampan.app.is_quiet", lambda _settings: True)
        self._leave_a_question(client)

        body = self._pending(client)

        assert body["waiting"] is False
        assert body["quiet_hours"] is True


class TestExtractionIsFullyWired:
    """The memory-v2 pass has to actually run on a real call.

    `finish_call` takes `fact_extractor` and `judge` as optional keywords so the
    seam can be exercised with fakes. The WebSocket handler passed neither, so
    on every real call the entire fact pass was skipped -- no fact extraction,
    no contradiction reconciliation, no edges written. Nothing raised and no
    test failed; the graph only grew when someone ran scripts/backfill_facts.py
    by hand, which is why the facts in Firestore looked convincing.

    Optional dependencies that default to doing nothing cannot be checked by
    the seam tests, because the seam is what gets the fakes. They have to be
    checked where they are assembled.
    """

    def test_production_builds_all_three_extractors(self) -> None:
        from sampan.app import build_extraction_stack
        from sampan.archivist import GeminiStoryExtractor
        from sampan.contradiction import GeminiContradictionJudge
        from sampan.fact_extraction import GeminiFactExtractor

        stack = build_extraction_stack(Settings(GOOGLE_CLOUD_PROJECT="p"))

        assert isinstance(stack.stories, GeminiStoryExtractor)
        assert isinstance(stack.facts, GeminiFactExtractor)
        assert isinstance(stack.judge, GeminiContradictionJudge)

    def test_the_call_handler_passes_the_facts_pass_to_finish_call(self) -> None:
        """Reads the handler rather than driving it: opening a real WebSocket
        needs a live model. It cannot prove the wiring works; it can prove
        nobody quietly dropped it again."""
        import inspect

        from sampan import app as app_module

        source = inspect.getsource(app_module)
        handler = source[source.index("async def talk(") :]

        assert "fact_extractor=stack.facts" in handler
        assert "judge=stack.judge" in handler

    def test_a_stack_with_a_judge_reconciles_rather_than_appends(self) -> None:
        """The judge's whole job: a later telling retires an earlier assertion
        instead of the archive holding both as current."""
        from sampan.contradiction import Disagreement, Judgement, reconcile
        from sampan.facts import Fact, Predicate

        held = [
            Fact(
                fact_id="f1",
                subject_id="e_shop",
                predicate=Predicate.OWNED,
                object_id="e_father",
                statement="her father owned the shop",
                quote="My father owned the shop until 1969.",
                episode_id="conv_1",
            )
        ]
        newer = [
            Fact(
                fact_id="f2",
                subject_id="e_shop",
                predicate=Predicate.OWNED,
                object_id="e_father",
                statement="her uncle owned the shop",
                quote="Actually my uncle took it over before it closed.",
                episode_id="conv_2",
            )
        ]

        class Says:
            def __init__(self, verdict: Disagreement) -> None:
                self.verdict = verdict

            def judge(self, new: Fact, old: Fact) -> Judgement:
                return Judgement(kind=self.verdict, reason="a later telling")

        changed, questions = reconcile(
            newer, held, Says(Disagreement.CONFLICTING_TESTIMONY)
        )

        # The older telling is retired in transaction time, not deleted, and
        # its valid time is untouched -- she is not being corrected.
        retired = [f for f in changed if f.fact_id == "f1"]
        assert len(retired) == 1
        assert retired[0].t_expired is not None
        assert retired[0].superseded_by == "f2"
        assert retired[0].valid_from == held[0].valid_from
        assert retired[0].valid_to == held[0].valid_to
        # And the disagreement comes back as a question for her, not a silent
        # decision by the archive.
        assert questions == ["a later telling"]
