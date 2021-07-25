from __future__ import annotations

from celery import shared_task
from celery.utils.log import get_task_logger
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.utils import timezone

from jcasts.podcasts import itunes
from jcasts.podcasts.emails import send_recommendations_email
from jcasts.podcasts.feed_parser import parse_feed
from jcasts.podcasts.models import Podcast
from jcasts.podcasts.recommender import recommend

logger = get_task_logger(__name__)


@shared_task(name="jcasts.podcasts.crawl_itunes")
def crawl_itunes(limit: int = 300) -> None:
    itunes.crawl_itunes(limit)


@shared_task(name="jcasts.podcasts.send_recommendation_emails")
def send_recommendation_emails() -> None:
    for user in get_user_model().objects.filter(
        send_recommendations_email=True, is_active=True
    ):
        send_recommendations_email(user)


@shared_task(name="jcasts.podcasts.sync_podcast_feeds")
def sync_podcast_feeds(last_updated: int = 24, last_checked: int = 2) -> None:
    """Sync podcasts with RSS feeds. Fetch any without a pub date or
    pub_date > given period."""

    # in Dokku or other managed environment long-running tasks are
    # cancelled. We need to be able to resume from a last checkpoint
    # without re-running the entire queryset.

    qs = (
        Podcast.objects.for_feed_sync(last_updated, last_checked)
        .order_by("-pub_date")
        .values_list("id", "rss")
    )

    processed = 0

    paginator = Paginator(qs, per_page=100, allow_empty_first_page=True)
    logger.info(f"Syncing {paginator.count} podcasts")

    for page_obj in paginator:
        podcast_ids = set()

        for podcast_id, rss in page_obj.object_list:
            processed += 1
            sync_podcast_feed.delay(rss, total=paginator.count, processed=processed)
            podcast_ids.add(podcast_id)

        Podcast.objects.filter(pk__in=podcast_ids).update(last_checked=timezone.now())


@shared_task(name="jcasts.podcasts.create_podcast_recommendations")
def create_podcast_recommendations() -> None:
    recommend()


@shared_task(name="jcasts.podcasts.sync_podcast_feed")
def sync_podcast_feed(
    rss: str, *, force_update: bool = False, total: int = None, processed: int = None
) -> None:
    try:
        podcast = Podcast.objects.get(rss=rss, active=True)
        if parse_feed(podcast, force_update=force_update):
            logger.info(f"Podcast {podcast} updated")
        if total and processed:
            logger.info(f"{processed}/{total} done")

    except Podcast.DoesNotExist:
        logger.debug(f"No podcast found for RSS {rss}")
