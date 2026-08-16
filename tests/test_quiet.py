"""Quiet hours — pure logic, no clock dependency."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from sampan.config import Settings
from sampan.quiet import is_quiet, next_delivery

KL = ZoneInfo("Asia/Kuala_Lumpur")


@pytest.fixture
def settings() -> Settings:
    return Settings(GOOGLE_CLOUD_PROJECT="", SAMPAN_API_KEY="k")


def at(hour: int, minute: int = 0, day: int = 16) -> datetime:
    return datetime(2026, 8, day, hour, minute, tzinfo=KL)


class TestWhenSheIsLeftAlone:
    @pytest.mark.parametrize("hour", [22, 23, 0, 3, 7])
    def test_night_is_quiet(self, settings: Settings, hour: int) -> None:
        assert is_quiet(settings, at(hour))

    @pytest.mark.parametrize("hour", [8, 12, 14, 18, 21])
    def test_daytime_is_not(self, settings: Settings, hour: int) -> None:
        """His pang arrives at 2pm and she is awake at 2pm. That is why
        delivery is instant rather than scheduled."""
        assert not is_quiet(settings, at(hour))

    def test_the_window_crosses_midnight(self, settings: Settings) -> None:
        """22:00-08:00 is a union, not a range. Getting this backwards would
        make it quiet all day and noisy all night."""
        assert is_quiet(settings, at(23))
        assert is_quiet(settings, at(1))
        assert not is_quiet(settings, at(12))

    def test_the_boundaries_belong_to_the_right_side(self, settings: Settings) -> None:
        assert is_quiet(settings, at(22, 0))
        assert not is_quiet(settings, at(8, 0))

    def test_an_empty_window_never_silences_anything(self) -> None:
        settings = Settings(SAMPAN_QUIET_FROM=0, SAMPAN_QUIET_UNTIL=0)

        assert not is_quiet(settings, at(3))


class TestWhenItReachesHer:
    def test_a_daytime_question_arrives_at_once(self, settings: Settings) -> None:
        now = at(14)

        assert next_delivery(settings, now) == now

    def test_a_late_night_question_waits_for_morning(self, settings: Settings) -> None:
        """He sends it at 23:00 from his desk. She hears it after breakfast."""
        delivery = next_delivery(settings, at(23, 30))

        assert delivery.hour == 8
        assert delivery.day == 17

    def test_a_small_hours_question_waits_for_the_same_morning(
        self, settings: Settings
    ) -> None:
        delivery = next_delivery(settings, at(3))

        assert delivery.hour == 8
        assert delivery.day == 16

    def test_delivery_is_never_in_the_past(self, settings: Settings) -> None:
        for hour in range(24):
            now = at(hour)
            assert next_delivery(settings, now) >= now
