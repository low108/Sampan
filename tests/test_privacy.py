"""Privacy — the promises the agent makes out loud, kept.

The agent says "I won't write that down" when she asks for something to stay off the
family's view. Before this, that sentence appended to a list that was discarded
when the call ended.
"""

from __future__ import annotations

import pytest

from sampan.family import build_cards
from sampan.household import cards_for
from sampan.repository import Repository
from sampan.store import InMemoryDocumentStore
from sampan.tools import CallMemory, build_tools

NARRATOR = "ah_khim"


def story(story_id: str, title: str, narrative: str = "") -> dict:
    return {
        "story_id": story_id,
        "candidate": {
            "title": title,
            "narrative": narrative or title,
            "when": {"raw_phrase": "in the old days"},
            "where": {"raw_name": "Jalan Bandar"},
            "who": [],
            "sensitivity": "routine",
        },
        "status": "pinnable",
        "missing_fields": [],
    }


@pytest.fixture
def repository() -> Repository:
    return Repository(InMemoryDocumentStore())


class TestMarkingPrivate:
    def test_what_she_marks_survives_the_call(self, repository: Repository) -> None:
        repository.mark_private(NARRATOR, "the quarrel with my sister")

        assert "the quarrel with my sister" in repository.private_subjects(NARRATOR)

    def test_blank_is_not_recorded(self, repository: Repository) -> None:
        repository.mark_private(NARRATOR, "   ")

        assert repository.private_subjects(NARRATOR) == []

    def test_the_tool_still_answers_her_the_same_way(self) -> None:
        memory = CallMemory()
        tool = next(t for t in build_tools(memory) if t.__name__ == "mark_private")

        result = tool("the quarrel with my sister")

        assert "won't write that down" in result["tell_her"]
        assert memory.private_marks == ["the quarrel with my sister"]


class TestFamilyCannotSeeIt:
    def test_a_private_story_is_withheld(self, repository: Repository) -> None:
        cards = build_cards(
            [story("s1", "the coffee shop"), story("s2", "the quarrel with my sister")],
            ["the quarrel with my sister"],
        )

        assert [c.story_id for c in cards] == ["s1"]

    def test_it_is_matched_in_the_narrative_too(self) -> None:
        """She names a subject, not a title. The story about it may be called
        something else entirely."""
        cards = build_cards(
            [story("s1", "that year", narrative="My sister and I stopped speaking")],
            ["sister"],
        )

        assert cards == []

    def test_nothing_is_withheld_when_she_marked_nothing(self) -> None:
        assert len(build_cards([story("s1", "the coffee shop")], [])) == 1

    def test_the_household_view_respects_it(self, repository: Repository) -> None:
        """cards_for is what the map, the chat agent and the feed all read."""
        repository.save_stories(NARRATOR, "conv_1", [])
        repository._store.put(  # noqa: SLF001
            f"stories__{NARRATOR}", "s2", story("s2", "the quarrel with my sister")
        )
        repository.mark_private(NARRATOR, "the quarrel with my sister")

        assert cards_for(repository, NARRATOR) == []


class TestPlaceLinkEvidence:
    """A link must be justified by something she said, not by the model's own
    reasoning about where the place probably is."""

    def test_a_real_quote_is_accepted(self) -> None:
        from sampan.places import _is_quoted

        transcript = (
            "K: Later he saved a bit of money, nineteen fifty-eight he opened "
            "a coffee shop in Ipoh, at Jalan Bandar."
        )

        assert _is_quoted(
            "nineteen fifty-eight he opened a coffee shop in Ipoh, at Jalan Bandar",
            transcript,
        )

    def test_the_models_own_reasoning_is_rejected(self) -> None:
        """These are real values it produced: they read like justification and
        prove nothing."""
        from sampan.places import _is_quoted

        transcript = "K: I grew up in the rubber estate, Sungai Siput side."

        assert not _is_quoted(
            "Identified as being in the vicinity of Sungai Siput", transcript
        )
        assert not _is_quoted("Specific street in Ipoh", transcript)

    def test_a_fragment_too_short_to_mean_anything_is_rejected(self) -> None:
        from sampan.places import _is_quoted

        assert not _is_quoted("the shop", "K: we lived above the shop for years")

    def test_punctuation_and_case_do_not_matter(self) -> None:
        from sampan.places import _is_quoted

        transcript = "K: That house is one long row, one room one room."

        assert _is_quoted("that house is one long row  ONE ROOM one room", transcript)


class TestResolverCannotForgeALink:
    """Geocoding and linking are separate powers. A pin may only claim it was
    placed by something she said if the linker checked that she said it."""

    def test_the_resolver_schema_hides_the_link_fields(self) -> None:
        """The leak was invisible from outside: handed a schema containing
        them, the model filled `linked_evidence` with its own reasoning, and
        that reached the map without passing the evidence check."""
        from sampan.places import _Geocoded

        assert "linked_from" not in _Geocoded.model_fields
        assert "linked_evidence" not in _Geocoded.model_fields

    def test_a_resolved_place_starts_with_no_link(self) -> None:
        from sampan.places import Place, _Geocoded

        place = Place(**_Geocoded(raw_name="Sungai Siput", confidence=0.9).model_dump())

        assert place.linked_from == ""
        assert place.linked_evidence == ""
