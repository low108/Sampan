"""Privacy — the promises the agent makes out loud, kept.

The agent says 「好,这个我不写进去」 when she asks for something to stay off the
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
            "when": {"raw_phrase": "以前"},
            "where": {"raw_name": "板底街"},
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
        repository.mark_private(NARRATOR, "跟姐姐吵架的事")

        assert "跟姐姐吵架的事" in repository.private_subjects(NARRATOR)

    def test_blank_is_not_recorded(self, repository: Repository) -> None:
        repository.mark_private(NARRATOR, "   ")

        assert repository.private_subjects(NARRATOR) == []

    def test_the_tool_still_answers_her_the_same_way(self) -> None:
        memory = CallMemory()
        tool = next(t for t in build_tools(memory) if t.__name__ == "mark_private")

        result = tool("跟姐姐吵架的事")

        assert "不写进去" in result["tell_her"]
        assert memory.private_marks == ["跟姐姐吵架的事"]


class TestFamilyCannotSeeIt:
    def test_a_private_story_is_withheld(self, repository: Repository) -> None:
        cards = build_cards(
            [story("s1", "咖啡店"), story("s2", "跟姐姐吵架的事")],
            ["跟姐姐吵架的事"],
        )

        assert [c.story_id for c in cards] == ["s1"]

    def test_it_is_matched_in_the_narrative_too(self) -> None:
        """She names a subject, not a title. The story about it may be called
        something else entirely."""
        cards = build_cards(
            [story("s1", "那一年", narrative="我跟姐姐吵架,到她走都没讲话")],
            ["跟姐姐吵架"],
        )

        assert cards == []

    def test_nothing_is_withheld_when_she_marked_nothing(self) -> None:
        assert len(build_cards([story("s1", "咖啡店")], [])) == 1

    def test_the_household_view_respects_it(self, repository: Repository) -> None:
        """cards_for is what the map, the chat agent and the feed all read."""
        repository.save_stories(NARRATOR, "conv_1", [])
        repository._store.put(  # noqa: SLF001
            f"stories__{NARRATOR}", "s2", story("s2", "跟姐姐吵架的事")
        )
        repository.mark_private(NARRATOR, "跟姐姐吵架的事")

        assert cards_for(repository, NARRATOR) == []
