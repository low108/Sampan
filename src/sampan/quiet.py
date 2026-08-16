"""Quiet hours.

Her son's pang of missing her arrives mid-afternoon, when she is awake — which
is why a family question is delivered instantly rather than scheduled. The
timing problem the product exists to solve disappears on its own.

But a question left at eleven at night must not greet her at eleven at night,
so delivery is held until morning. The ask is queued the moment he sends it;
only the moment she *sees* it moves.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sampan.config import Settings


def local_now(settings: Settings, now: datetime | None = None) -> datetime:
    zone = ZoneInfo(settings.timezone)
    return now.astimezone(zone) if now is not None else datetime.now(zone)


def is_quiet(settings: Settings, now: datetime | None = None) -> bool:
    """Whether she should be left alone right now.

    The window crosses midnight, so this is a union rather than a range: 22:00
    to 08:00 means "at or after 22" or "before 8", not "between".
    """
    hour = local_now(settings, now).hour
    start, end = settings.quiet_from_hour, settings.quiet_until_hour
    if start == end:
        return False
    if start < end:
        return start <= hour < end
    return hour >= start or hour < end


def next_delivery(settings: Settings, now: datetime | None = None) -> datetime:
    """When a question left now would reach her.

    Now, if she is awake. Otherwise the next time quiet hours end — which is
    tomorrow morning if it is already late tonight, and this morning if it is
    the small hours.
    """
    current = local_now(settings, now)
    if not is_quiet(settings, current):
        return current

    morning = current.replace(
        hour=settings.quiet_until_hour, minute=0, second=0, microsecond=0
    )
    if morning <= current:
        morning += timedelta(days=1)
    return morning
