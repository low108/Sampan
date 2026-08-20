"""Screening the transcript before it reaches the database.

The rule under test is the ordering: the screen runs before the first write,
and the *screened* text is what everything downstream reads. Extracting from
the original while storing the redacted copy would make `build_facts` refuse
exactly the quotes that had something worth protecting in them, so the archive
would quietly lose the sentences the screen was there to make safe.
"""

from __future__ import annotations

import pytest

from sampan.armor import AllowAll, Finding, Screened, build_screen, screen
from sampan.callflow import finish_call, prepare_call
from sampan.config import Settings
from sampan.repository import Repository
from sampan.store import InMemoryDocumentStore
from tests.test_callflow import FULL, NARRATOR, StubExtractor, conversation


@pytest.fixture
def repository() -> Repository:
    return Repository(InMemoryDocumentStore())


@pytest.fixture
def settings() -> Settings:
    return Settings(GOOGLE_CLOUD_PROJECT="", SAMPAN_API_KEY="k")


class Redacts:
    """Stands in for Model Armor finding an identifier."""

    def __init__(self, replacement: str) -> None:
        self.replacement = replacement
        self.seen: list[str] = []

    def sanitize(self, text: str) -> Screened:
        self.seen.append(text)
        return Screened(
            text=self.replacement,
            findings=[Finding(filter="sdp", detail="PHONE_NUMBER")],
        )


class Breaks:
    def sanitize(self, text: str) -> Screened:
        raise RuntimeError("model armor unreachable")


class TestTheScreenRunsFirst:
    def test_the_stored_transcript_is_the_screened_one(
        self, repository: Repository, settings: Settings
    ) -> None:
        screener = Redacts("K: call me on [REDACTED]")
        prepared = prepare_call(repository, settings, narrator_id=NARRATOR)

        finish_call(
            repository,
            StubExtractor(FULL),
            prepared,
            conversation(),
            narrator_id=NARRATOR,
            screener=screener,
        )

        stored = repository._store.get(  # noqa: SLF001
            f"conversations__{NARRATOR}", prepared.conversation_id
        )
        assert stored is not None
        assert stored["transcript"] == "K: call me on [REDACTED]"
        assert stored["screened"] == [{"filter": "sdp", "detail": "PHONE_NUMBER"}]

    def test_extraction_reads_the_screened_text_not_the_original(
        self, repository: Repository, settings: Settings
    ) -> None:
        """Otherwise a quote containing a redaction is no longer present in the
        stored transcript, and every fact resting on it is refused."""
        screener = Redacts("K: redacted line")
        extractor = StubExtractor(FULL)
        prepared = prepare_call(repository, settings, narrator_id=NARRATOR)

        finish_call(
            repository,
            extractor,
            prepared,
            conversation(),
            narrator_id=NARRATOR,
            screener=screener,
        )

        assert extractor.seen == ["K: redacted line"]

    def test_the_screen_sees_the_whole_transcript(
        self, repository: Repository, settings: Settings
    ) -> None:
        screener = Redacts("clean")
        prepared = prepare_call(repository, settings, narrator_id=NARRATOR)
        spoken = conversation()

        finish_call(
            repository,
            StubExtractor(FULL),
            prepared,
            spoken,
            narrator_id=NARRATOR,
            screener=screener,
        )

        assert screener.seen == [spoken.render()]


class TestFailingClosed:
    def test_a_broken_screen_stores_no_transcript(
        self, repository: Repository, settings: Settings
    ) -> None:
        """A control that degrades to "store it anyway" is not a control."""
        prepared = prepare_call(repository, settings, narrator_id=NARRATOR)

        finish_call(
            repository,
            StubExtractor(FULL),
            prepared,
            conversation(),
            narrator_id=NARRATOR,
            screener=Breaks(),
        )

        stored = repository._store.get(  # noqa: SLF001
            f"conversations__{NARRATOR}", prepared.conversation_id
        )
        assert stored is not None
        assert stored["transcript"] == ""

    def test_the_absence_says_why(
        self, repository: Repository, settings: Settings
    ) -> None:
        """A call that vanished silently is indistinguishable from one that
        never happened."""
        prepared = prepare_call(repository, settings, narrator_id=NARRATOR)

        finish_call(
            repository,
            StubExtractor(FULL),
            prepared,
            conversation(),
            narrator_id=NARRATOR,
            screener=Breaks(),
        )

        stored = repository._store.get(  # noqa: SLF001
            f"conversations__{NARRATOR}", prepared.conversation_id
        )
        assert stored is not None
        assert "screening failed" in stored["withheld"]
        assert stored["turns"] > 0

    def test_nothing_derived_is_stored_either(
        self, repository: Repository, settings: Settings
    ) -> None:
        """Stories are extracted from the transcript. Refusing to store the
        transcript and then storing what was extracted from it would leak the
        very thing the refusal was protecting."""
        prepared = prepare_call(repository, settings, narrator_id=NARRATOR)

        finish_call(
            repository,
            StubExtractor(FULL),
            prepared,
            conversation(),
            narrator_id=NARRATOR,
            screener=Breaks(),
        )

        assert repository.load_stories(NARRATOR) == []


class TestWhenUnconfigured:
    def test_no_screener_stores_the_transcript_unchanged(self) -> None:
        result = screen("K: something she said", None)

        assert result.stored is True
        assert result.text == "K: something she said"

    def test_an_unconfigured_deployment_has_no_screen(self) -> None:
        assert build_screen(Settings(GOOGLE_CLOUD_PROJECT="")) is None
        assert build_screen(Settings(GOOGLE_CLOUD_PROJECT="p")) is None

    def test_a_configured_template_builds_one(self) -> None:
        built = build_screen(
            Settings(GOOGLE_CLOUD_PROJECT="p", SAMPAN_ARMOR_TEMPLATE="t")
        )

        assert built is not None

    def test_allow_all_is_a_pass_through(self) -> None:
        result = AllowAll().sanitize("verbatim")

        assert result.text == "verbatim"
        assert result.findings == []
