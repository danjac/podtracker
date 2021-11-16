from __future__ import annotations

import statistics

from datetime import datetime, timedelta

from django.conf import settings
from django.utils import timezone

from jcasts.shared.typedefs import ComparableT

DEFAULT_MODIFIER = 0.05
DEFAULT_FREQUENCY = timedelta(days=1)
MIN_FREQUENCY = timedelta(hours=3)
MAX_FREQUENCY = timedelta(days=30)

MAX_PUB_DATES = 12


def schedule(
    pub_date: datetime | None,
    frequency: timedelta | None,
    pub_dates: list[datetime],
) -> tuple[datetime | None, timedelta | None, float | None]:
    """Return a new scheduled time and modifier."""

    if pub_date is None:
        return None, None, None

    now = timezone.now()

    if pub_date < now - MAX_FREQUENCY:
        return now + MAX_FREQUENCY, MAX_FREQUENCY, DEFAULT_MODIFIER

    frequency = (
        frequency_within_bounds(frequency) if frequency else get_frequency(pub_dates)
    )

    scheduled = pub_date + frequency

    while scheduled < now:
        scheduled += frequency

    return (
        within_bounds(
            scheduled,
            now + MIN_FREQUENCY,
            now + MAX_FREQUENCY,
        ),
        frequency,
        DEFAULT_MODIFIER,
    )


def reschedule(
    frequency: timedelta | None, modifier: float | None
) -> tuple[datetime, timedelta, float]:
    """Increment scheduled time if no new updates
    and increment the schedule modifier.
    """

    now = timezone.now()

    frequency = frequency_within_bounds(frequency or DEFAULT_FREQUENCY)
    modifier = modifier or DEFAULT_MODIFIER

    return (
        within_bounds(
            now + timedelta(seconds=frequency.total_seconds() * modifier),
            now + MIN_FREQUENCY,
            now + MAX_FREQUENCY,
        ),
        frequency,
        within_bounds(modifier * 1.2, DEFAULT_MODIFIER, 1.0),
    )


def get_frequency(pub_dates: list[datetime]) -> timedelta:
    """Calculate the frequency based on mean interval between pub dates
    of individual episodes."""

    now = timezone.now()

    # ignore any < 90 days

    earliest = now - settings.FRESHNESS_THRESHOLD
    pub_dates = [pub_date for pub_date in pub_dates if pub_date > earliest]

    # assume default if not enough available dates

    if len(pub_dates) in (0, 1):
        return DEFAULT_FREQUENCY

    latest, *pub_dates = sorted(pub_dates, reverse=True)[:MAX_PUB_DATES]

    # calculate mean interval between dates

    intervals: list[float] = []

    for pub_date in pub_dates:
        intervals.append((latest - pub_date).total_seconds())
        latest = pub_date

    return frequency_within_bounds(timedelta(seconds=statistics.mean(intervals)))


def frequency_within_bounds(frequency: timedelta) -> timedelta:
    return within_bounds(frequency, MIN_FREQUENCY, MAX_FREQUENCY)


def within_bounds(
    value: ComparableT, min_value: ComparableT, max_value: ComparableT
) -> ComparableT:
    return max(min(value, max_value), min_value)
