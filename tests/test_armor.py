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


class TestFailingOpen:
    """A screening outage costs the screen, not the call.

    The opposite of the posture the service takes on a missing project or key
    (D2), and deliberately: there, failing closed protects the archive from
    silent data loss. Here it would cause it. Losing an eighty-year-old's
    account of her own life because a screening API had a bad minute is worse
    than holding an unscreened transcript in a private database until someone
    reads the log line.
    """

    def test_a_broken_screen_still_stores_her_words(
        self, repository: Repository, settings: Settings
    ) -> None:
        prepared = prepare_call(repository, settings, narrator_id=NARRATOR)
        spoken = conversation()

        finish_call(
            repository,
            StubExtractor(FULL),
            prepared,
            spoken,
            narrator_id=NARRATOR,
            screener=Breaks(),
        )

        stored = repository._store.get(  # noqa: SLF001
            f"conversations__{NARRATOR}", prepared.conversation_id
        )
        assert stored is not None
        assert stored["transcript"] == spoken.render()

    def test_the_call_is_marked_as_never_screened(
        self, repository: Repository, settings: Settings
    ) -> None:
        """Not the same as "the screen found nothing". Which calls went through
        unchecked has to be answerable."""
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
        assert stored["unscreened"] is True
        assert "RuntimeError" in stored["screen_error"]

    def test_a_clean_screen_is_not_marked_unscreened(
        self, repository: Repository, settings: Settings
    ) -> None:
        prepared = prepare_call(repository, settings, narrator_id=NARRATOR)

        finish_call(
            repository,
            StubExtractor(FULL),
            prepared,
            conversation(),
            narrator_id=NARRATOR,
            screener=AllowAll(),
        )

        stored = repository._store.get(  # noqa: SLF001
            f"conversations__{NARRATOR}", prepared.conversation_id
        )
        assert stored is not None
        assert stored["unscreened"] is False

    def test_the_failure_is_logged_at_error(
        self, repository: Repository, settings: Settings, caplog
    ) -> None:
        """The log line is half the audit trail; the flag on the document is
        the other half."""
        prepared = prepare_call(repository, settings, narrator_id=NARRATOR)

        with caplog.at_level("ERROR", logger="sampan.armor"):
            finish_call(
                repository,
                StubExtractor(FULL),
                prepared,
                conversation(),
                narrator_id=NARRATOR,
                screener=Breaks(),
            )

        assert any("unscreened" in r.message for r in caplog.records)

    def test_the_stories_still_land(
        self, repository: Repository, settings: Settings
    ) -> None:
        """The call is not punished for the screen's outage."""
        prepared = prepare_call(repository, settings, narrator_id=NARRATOR)

        finish_call(
            repository,
            StubExtractor(FULL),
            prepared,
            conversation(),
            narrator_id=NARRATOR,
            screener=Breaks(),
        )

        assert len(repository.load_stories(NARRATOR)) == 1


class TestWhenUnconfigured:
    def test_no_screener_stores_the_transcript_unchanged(self) -> None:
        result = screen("K: something she said", None)

        assert result.stored is True
        assert result.text == "K: something she said"

    def test_an_unconfigured_deployment_has_no_screen(self) -> None:
        """A developer against an in-memory store has nothing to protect, and
        requiring a DLP template to run the app at all would be theatre."""
        assert build_screen(Settings(GOOGLE_CLOUD_PROJECT="")) is None
        assert build_screen(Settings(GOOGLE_CLOUD_PROJECT="p")) is None

    def test_dlp_is_the_default_backend(self) -> None:
        """One hop fewer to the same detection, and one silent failure mode
        fewer: Model Armor's SDP filter delegates to these very templates
        (R18)."""
        from sampan.armor import DlpScreen

        built = build_screen(
            Settings(
                GOOGLE_CLOUD_PROJECT="p",
                SAMPAN_DLP_INSPECT_TEMPLATE="i",
                SAMPAN_DLP_DEIDENTIFY_TEMPLATE="d",
            )
        )

        assert isinstance(built, DlpScreen)

    def test_dlp_needs_both_templates(self) -> None:
        """Inspecting without de-identifying finds the number and stores it
        anyway, which is worse than not looking."""
        assert (
            build_screen(
                Settings(GOOGLE_CLOUD_PROJECT="p", SAMPAN_DLP_INSPECT_TEMPLATE="i")
            )
            is None
        )

    def test_model_armor_is_opt_in(self) -> None:
        """Chosen for the filters DLP has no equivalent of, not for the
        redaction."""
        from sampan.armor import ModelArmorScreen

        built = build_screen(
            Settings(
                GOOGLE_CLOUD_PROJECT="p",
                SAMPAN_SCREEN_BACKEND="armor",
                SAMPAN_ARMOR_TEMPLATE="t",
            )
        )

        assert isinstance(built, ModelArmorScreen)

    def test_asking_for_armor_without_a_template_screens_nothing(self) -> None:
        built = build_screen(
            Settings(GOOGLE_CLOUD_PROJECT="p", SAMPAN_SCREEN_BACKEND="armor")
        )

        assert built is None

    def test_allow_all_is_a_pass_through(self) -> None:
        result = AllowAll().sanitize("verbatim")

        assert result.text == "verbatim"
        assert result.findings == []
