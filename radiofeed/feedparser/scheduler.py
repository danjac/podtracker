import itertools
from datetime import datetime, timedelta
from typing import Final

from django.db.models import Count, F, Q, QuerySet
from django.utils import timezone

from radiofeed.feedparser.models import Feed
from radiofeed.podcasts.models import Podcast

_DEFAULT_FREQUENCY: Final = timedelta(hours=24)
_MIN_FREQUENCY: Final = timedelta(hours=3)
_MAX_FREQUENCY: Final = timedelta(days=15)


def next_scheduled_update(podcast: Podcast) -> datetime:
    """Returns estimated next update."""
    now = timezone.now()

    if podcast.pub_date is None or podcast.parsed is None:
        return now

    return max(
        min(
            podcast.parsed + _MAX_FREQUENCY,
            max(
                podcast.pub_date + podcast.frequency,
                podcast.parsed + _MIN_FREQUENCY,
            ),
        ),
        now,
    )


def get_podcasts_for_update() -> QuerySet[Podcast]:
    """Returns all active podcasts scheduled for feed update.

    1) Any newly added feeds
    2) Any not checked for at least 15 days
    3) Any with last pub date since their `frequency` value
    4) Any queued podcasts

    Results are ordered by their last checked date and prioritized
    if subscribed or promoted.

    Podcasts which are subscribed to a websub hub should not be scheduled
    unless marked queued.
    """
    now = timezone.now()

    return (
        Podcast.objects.alias(subscribers=Count("subscriptions"))
        .filter(
            Q(
                Q(parsed__isnull=True)
                | Q(pub_date__isnull=True)
                | Q(parsed__lt=now - _MAX_FREQUENCY)
                | Q(
                    pub_date__lt=now - F("frequency"),
                    parsed__lt=now - _MIN_FREQUENCY,
                ),
            )
            | Q(queued__isnull=False),
            active=True,
        )
        .exclude(
            websub_mode="subscribe",
            websub_expires__gt=now,
            queued__isnull=True,
        )
        .order_by(
            F("queued").desc(nulls_last=True),
            F("subscribers").desc(),
            F("promoted").desc(),
            F("parsed").asc(nulls_first=True),
            F("pub_date").desc(nulls_first=True),
            F("created").desc(),
        )
    )


def schedule(feed: Feed) -> timedelta:
    """Estimates frequency of episodes in feed, based on the minimum of time intervals
    between individual episodes."""
    try:
        frequency = min(
            a - b
            for a, b in itertools.pairwise(
                sorted(
                    [item.pub_date for item in feed.items],
                    reverse=True,
                )
            )
        )

    except ValueError:
        frequency = _DEFAULT_FREQUENCY

    # increment until pub date + freq > current time

    return reschedule(feed.pub_date, frequency)


def reschedule(pub_date: datetime | None, frequency: timedelta) -> timedelta:
    """Increments update frequency until next scheduled date > current time."""
    if pub_date is None:
        return _DEFAULT_FREQUENCY

    # ensure we don't try to increment zero frequency

    frequency = frequency or _MIN_FREQUENCY

    now = timezone.now()

    while now > pub_date + frequency:
        frequency += frequency * 0.05

    # ensure result falls within bounds

    return max(frequency, _MIN_FREQUENCY)
