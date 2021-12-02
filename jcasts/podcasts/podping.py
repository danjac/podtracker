from __future__ import annotations

import itertools
import json

from datetime import timedelta
from typing import Generator, Iterable

import beem

from beem.account import Account
from beem.blockchain import Blockchain
from django.db.models import Q
from django.utils import timezone

from jcasts.podcasts import feed_parser
from jcasts.podcasts.models import Podcast

WATCHED_OPERATION_IDS = ["podping"]
HIVE_NODE = "https://api.hive.blog"
ACCOUNT_NAME = "podping"


def get_updates(
    from_minutes_ago: int = 15, batch_size=30
) -> Generator[str, None, None]:

    for urls in grouper(get_stream(from_minutes_ago), batch_size):
        yield from batch_updates(urls, from_minutes_ago)


def grouper(
    iterable: Iterable[str], chunk_size: int
) -> Generator[set[str], None, None]:
    it = iter(iterable)
    while True:
        chunk = set(itertools.islice(it, chunk_size))
        if not chunk:
            return
        yield chunk


def batch_updates(urls: set[str], from_minutes_ago: int) -> Generator[str, None, None]:
    """Processes batch of RSS feeds. Parse feeds of any URLs
    in the database that have not already been updated within the timeframe.
    """

    podcast_ids: set[int] = set()
    now = timezone.now()

    for podcast_id, rss in (
        Podcast.objects.active()
        .unqueued()
        .filter(
            Q(parsed__isnull=True)
            | Q(parsed__lt=now - timedelta(minutes=from_minutes_ago)),
            rss__in=urls,
        )
        .values_list("pk", "rss")
        .distinct()
    ):
        podcast_ids.add(podcast_id)
        yield rss

    if not podcast_ids:
        return

    Podcast.objects.filter(pk__in=podcast_ids).update(queued=now, podping=True)

    for podcast_id in podcast_ids:
        feed_parser.parse_podcast_feed.delay(podcast_id)


def get_stream(from_minutes_ago: int) -> Generator[str, None, None]:
    """Outputs URLs one by one as they appear on the Hive Podping stream"""

    allowed_accounts = set(
        Account(
            ACCOUNT_NAME,
            blockchain_instance=beem.Hive(node=HIVE_NODE),
            lazy=True,
        ).get_following()
    )

    blockchain = Blockchain(mode="head", blockchain_instance=beem.Hive())

    for post in blockchain.stream(
        opNames=["custom_json"],
        raw_ops=False,
        threading=False,
        start=blockchain.get_estimated_block_num(
            timezone.now() - timedelta(minutes=from_minutes_ago)
        ),
    ):
        if (
            post["id"] in WATCHED_OPERATION_IDS
            and set(post["required_posting_auths"]) & allowed_accounts
        ):
            yield from parse_urls(post.get("json"))


def parse_urls(payload: str) -> Generator[str, None, None]:
    data = json.loads(payload)
    if url := data.get("url"):
        yield url
    elif urls := data.get("urls"):
        yield from urls
