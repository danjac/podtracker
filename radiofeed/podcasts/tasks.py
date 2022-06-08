from __future__ import annotations

import multiprocessing

from datetime import timedelta

from huey import crontab
from huey.contrib.djhuey import db_periodic_task, db_task

from radiofeed.podcasts import emails, recommender, scheduler
from radiofeed.podcasts.models import Podcast
from radiofeed.podcasts.parsers import feed_parser
from radiofeed.users.models import User


@db_periodic_task(crontab(minute="*/6"))
def parse_podcast_feeds(interval: timedelta = timedelta(minutes=6)) -> None:
    """Parse podcast RSS feeds.

    Runs every 6 minutes.
    """

    # assume avg 10s per feed and 1 worker/CPU
    # e.g. 360 second interval / 10 = 36, x 3 CPUs = 108.

    limit = round(multiprocessing.cpu_count() * (interval.total_seconds() / 10))

    parse_podcast_feed.map(
        scheduler.schedule_podcast_feeds().values_list("pk").distinct()[:limit]
    )


@db_periodic_task(crontab(hour=3, minute=20))
def recommend() -> None:
    """
    Generates podcast recommendations

    Runs 03:20 UTC every day
    """
    recommender.recommend()


@db_periodic_task(crontab(hour=9, minute=12, day_of_week=1))
def send_recommendations_emails() -> None:
    """
    Sends recommended podcasts to users

    Runs at 09:12 UTC every Monday
    """
    send_recommendations_email.map(
        User.objects.filter(
            send_email_notifications=True,
            is_active=True,
        ).values_list("pk")
    )


@db_task()
def parse_podcast_feed(podcast_id: int) -> None:
    feed_parser.parse_podcast_feed(Podcast.objects.get(pk=podcast_id))


@db_task()
def send_recommendations_email(user_id: int) -> None:
    emails.send_recommendations_email(User.objects.get(pk=user_id))
