from __future__ import annotations

import itertools

from datetime import timedelta

from django.db import models
from django.db.models.functions import ExtractDay
from django.utils import timezone

from radiofeed.podcasts.models import Podcast
from radiofeed.podcasts.tasks import feed_update


def schedule(limit: int) -> None:
    feed_update.map(
        itertools.islice(get_scheduled_feeds().values_list("pk").distinct(), limit)
    )


def get_scheduled_feeds() -> models.QuerySet[Podcast]:
    now = timezone.now()

    return (
        Podcast.objects.annotate(
            subscribers=models.Count("subscription"),
            days_since_last_pub_date=ExtractDay(now - models.F("pub_date")),
        )
        .filter(
            models.Q(
                parsed__isnull=True,
            )
            | models.Q(
                pub_date__isnull=True,
            )
            | models.Q(
                days_since_last_pub_date__lt=1,
                parsed__lt=now - timedelta(hours=1),
            )
            | models.Q(
                days_since_last_pub_date__gt=24,
                parsed__lt=now - timedelta(hours=24),
            )
            | models.Q(
                days_since_last_pub_date__range=(1, 24),
                parsed__lt=now
                - timedelta(hours=1) * models.F("days_since_last_pub_date"),
            ),
            active=True,
        )
        .order_by(
            models.F("subscribers").desc(),
            models.F("promoted").desc(),
            models.F("parsed").asc(nulls_first=True),
            models.F("pub_date").desc(nulls_first=True),
        )
    )
