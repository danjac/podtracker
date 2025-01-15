import contextlib
import dataclasses
import itertools
from collections.abc import Iterator
from concurrent import futures
from typing import Optional

import httpx

from radiofeed.http_client import Client
from radiofeed.podcasts.models import Podcast


@dataclasses.dataclass(frozen=True)
class Feed:
    """Encapsulates iTunes API result.

    Attributes:
        rss: URL to RSS or Atom resource
        url: URL to website of podcast
        title: title of podcast
        image: URL to cover image
        podcast: matching Podcast instance in local database
    """

    rss: str
    url: str
    title: str = ""
    image: str = ""
    podcast: Podcast | None = None

    def __eq__(self, other) -> bool:
        """Compare two Feed instances."""
        return self.rss == other.rss

    @classmethod
    def from_result(cls, result: dict) -> Optional["Feed"]:
        """Returns instance from iTunes API result."""
        with contextlib.suppress(KeyError):
            return cls(
                rss=result["feedUrl"],
                url=result["collectionViewUrl"],
                title=result["collectionName"],
                image=result["artworkUrl100"],
            )
        return None


def search(client: Client, search_term: str, *, limit: int = 50) -> Iterator[Feed]:
    """Search iTunes podcast API."""
    return _Search(client).search(search_term, limit=limit)


def update_chart(client: Client) -> Iterator[Feed]:
    """Fetch top chart from iTunes podcast API."""
    return _ChartUpdater(client).update()


@dataclasses.dataclass(frozen=True)
class _Search:
    """Search iTunes podcast API."""

    client: Client

    search_url: str = "https://itunes.apple.com/search"

    def search(self, search_term: str, *, limit: int = 50) -> Iterator[Feed]:
        """Search iTunes podcast API."""
        return self._insert_search_results(
            self._fetch_search_results(
                search_term,
                limit,
            ),
        )

    def _fetch_search_results(self, search_term: str, limit: int) -> Iterator[Feed]:
        try:
            response = self.client.get(
                self.search_url,
                params={
                    "term": search_term,
                    "limit": limit,
                    "media": "podcast",
                },
                headers={
                    "Accept": "application/json",
                },
            )
            for result in response.json().get("results", []):
                if feed := Feed.from_result(result):
                    yield feed

        except httpx.HTTPError:
            return

    def _insert_search_results(self, feeds: Iterator[Feed]) -> Iterator[Feed]:
        # find or insert podcasts from local database into feeds
        feeds_for_podcasts, feeds = itertools.tee(feeds)

        podcasts = Podcast.objects.filter(
            rss__in={f.rss for f in feeds_for_podcasts}
        ).in_bulk(field_name="rss")

        # insert podcasts to feeds where we have a match

        feeds_for_insert, feeds = itertools.tee(
            [
                dataclasses.replace(feed, podcast=podcasts.get(feed.rss))
                for feed in feeds
            ],
        )

        # create new podcasts for feeds without a match

        Podcast.objects.bulk_create(
            [
                Podcast(title=feed.title, rss=feed.rss)
                for feed in set(feeds_for_insert)
                if feed.podcast is None
            ],
            ignore_conflicts=True,
        )

        yield from feeds


@dataclasses.dataclass(frozen=True)
class _ChartUpdater:
    """Fetch top chart from iTunes podcast API."""

    client: Client

    chart_url: str = (
        "https://rss.marketingtools.apple.com/api/v2/us/podcasts/top/10/podcasts.json"
    )

    podcast_url: str = "https://itunes.apple.com/lookup"

    def update(self) -> Iterator[Feed]:
        """Fetch top chart from iTunes podcast API."""
        return self._update_or_insert_chart_results(
            self._parse_chart_results(),
        )

    def _update_or_insert_chart_results(self, feeds: Iterator[Feed]) -> Iterator[Feed]:
        feeds_for_podcasts, feeds = itertools.tee(feeds)

        if podcasts := [
            Podcast(
                rss=feed.rss,
                promoted=True,
                itunes_ranking=ranking,
            )
            for ranking, feed in enumerate(feeds_for_podcasts, 1)
        ]:
            # Clear existing itunes rankings
            Podcast.objects.filter(itunes_ranking__isnull=False).update(
                itunes_ranking=None
            )

            Podcast.objects.bulk_create(
                podcasts,
                unique_fields=["rss"],
                update_fields=["promoted", "itunes_ranking"],
                update_conflicts=True,
            )

        yield from feeds

    def _parse_chart_results(self) -> Iterator[Feed]:
        with contextlib.suppress(httpx.HTTPError):
            response = self.client.get(self.chart_url)
            processes = []
            with futures.ThreadPoolExecutor() as executor:
                for result in response.json().get("feed", {}).get("results", []):
                    processes.append(executor.submit(self._parse_chart_result, result))
            feeds = [process.result() for process in processes]
            yield from dict.fromkeys(feed for feed in feeds if feed)

    def _parse_chart_result(self, result: dict) -> Feed | None:
        with contextlib.suppress(KeyError, IndexError, httpx.HTTPError):
            response = self.client.get(
                self.podcast_url,
                params={"id": result["id"]},
            )
            return Feed.from_result(response.json()["results"][0])
        return None
