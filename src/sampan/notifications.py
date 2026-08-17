"""The bell.

Derived, not stored. A notification is a *view* of something that already
exists — a question waiting, a story that arrived, a concern raised — so
computing it on read means it can never disagree with the thing it describes.
Only "seen" is written down.

The one that matters is "Wei Lun asked you something". Tapping it starts a
recording with
his question already loaded, so the distance between *someone was thinking of
you* and *she starts talking* is a single tap.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from sampan.household import Member
from sampan.repository import Repository

SEEN = "seen"


class NotificationKind(StrEnum):
    ASKED_YOU = "asked_you"
    NEW_STORY = "new_story"
    CONCERN = "concern"


class Notification(BaseModel):
    id: str
    kind: NotificationKind
    title: str = Field(description="Chinese, leading")
    subtitle: str = Field(default="", description="English, carrying")
    from_name: str = ""
    at: str = ""
    seen: bool = False
    # Where tapping it goes.
    opens: str = Field(default="", description="record | story | member")
    target: str = ""
    covers: list[str] = Field(
        default_factory=list,
        description="Ids this one stands for, all settled when it is seen",
    )

    @property
    def starts_recording(self) -> bool:
        return self.opens == "record"


def _seen_ids(repository: Repository, viewer_id: str) -> set[str]:
    raw = repository._store.get(SEEN, viewer_id)  # noqa: SLF001
    return set(raw.get("ids", [])) if raw else set()


def mark_seen(repository: Repository, viewer_id: str, ids: list[str]) -> None:
    current = _seen_ids(repository, viewer_id)
    current.update(ids)
    repository._store.put(  # noqa: SLF001
        SEEN,
        viewer_id,
        {"ids": sorted(current), "updated_at": datetime.now(UTC).isoformat()},
    )


def notifications_for(
    repository: Repository, viewer_id: str, members: list[Member]
) -> list[Notification]:
    """What this person should see when they open the bell.

    Two audiences, one bell. She gets "someone asked you"; her family get her new
    stories. Nobody gets told about their own recordings.
    """
    seen = _seen_ids(repository, viewer_id)
    by_id = {m.narrator_id: m for m in members}
    out: list[Notification] = []

    # Someone left her a question. This is the one that leads to a recording.
    ask = repository.pending_ask(viewer_id)
    if ask is not None:
        out.append(
            Notification(
                id=f"ask:{ask.ask_id}",
                kind=NotificationKind.ASKED_YOU,
                title=f"{ask.from_name} asked you something",
                subtitle=f"{ask.from_name} left you a question",
                from_name=ask.from_name,
                at=ask.created_at or "",
                opens="record",
                target=ask.ask_id,
                seen=f"ask:{ask.ask_id}" in seen,
            )
        )

    # Stories other people told. Never your own — you were there.
    #
    # Grouped per person rather than one row each: eleven rows is an inbox, and
    # an inbox is a chore. One line saying she has been talking is a nudge to
    # go and read her, which is the point.
    for member in members:
        if member.narrator_id == viewer_id:
            continue
        stories = [
            raw
            for raw in repository.load_stories(member.narrator_id)
            if raw.get("story_id") and (raw.get("candidate") or {}).get("title")
        ]
        fresh = [s for s in stories if f"story:{s['story_id']}" not in seen]
        if not stories:
            continue

        given = member.display_name.split()[0]
        newest = max(stories, key=lambda s: s.get("occurred_at", "") or s["story_id"])
        if len(fresh) > 1:
            title = f"{given} told {len(fresh)} new stories"
            subtitle = f"{len(fresh)} new stories from {member.display_name}"
        elif len(fresh) == 1:
            told = (fresh[0].get("candidate") or {}).get("title", "")
            title = f"{given} told: {told}"
            subtitle = f"a new story from {member.display_name}"
        else:
            told = (newest.get("candidate") or {}).get("title", "")
            title = f"{given} told: {told}"
            subtitle = f"from {member.display_name}"

        out.append(
            Notification(
                id=f"stories:{member.narrator_id}:{len(stories)}",
                kind=NotificationKind.NEW_STORY,
                title=title,
                subtitle=subtitle,
                from_name=member.display_name,
                at=newest.get("occurred_at", "") or newest["story_id"],
                opens="member",
                target=member.narrator_id,
                seen=not fresh,
                # Marking the group seen has to settle every story in it, or
                # the badge comes back the moment the page reloads.
                covers=[f"story:{s['story_id']}" for s in stories],
            )
        )

    # Care concerns go to the family, never back to the person they are about.
    for member in members:
        if member.narrator_id == viewer_id:
            continue
        for raw in repository.open_concerns(member.narrator_id):
            out.append(
                Notification(
                    id=f"care:{raw['concern_id']}",
                    kind=NotificationKind.CONCERN,
                    title=(
                        f"{by_id[member.narrator_id].display_name.split()[0]} "
                        f"mentioned {raw['kind']}"
                    ),
                    subtitle=raw.get("detail", ""),
                    at=raw.get("raised_at", ""),
                    opens="member",
                    target=member.narrator_id,
                    seen=f"care:{raw['concern_id']}" in seen,
                )
            )

    # Unseen first, then newest. A concern outranks everything regardless.
    def rank(n: Notification) -> tuple[int, int, str]:
        urgent = 0 if n.kind is NotificationKind.CONCERN else 1
        return (urgent, 0 if not n.seen else 1, n.at)

    return sorted(out, key=rank, reverse=False)[:30]


def unseen_count(notifications: list[Notification]) -> int:
    return sum(1 for n in notifications if not n.seen)
