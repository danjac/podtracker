import dataclasses
import functools
import itertools
import re
from collections.abc import Iterator
from typing import Final
from urllib.parse import urlparse

import lxml
import requests
from django.conf import settings
from django.core.cache import cache
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from radiofeed import batcher
from radiofeed.podcasts.models import Podcast
from radiofeed.xml_parser import XMLParser

_ITUNES_PODCAST_ID: Final = re.compile(r"id(?P<id>\d+)")


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


def search(search_term: str, timeout: int = 5) -> list[Feed]:
    """Runs cached search for podcasts on iTunes API."""
    cache_key = search_cache_key(search_term)
    if (feeds := cache.get(cache_key)) is None:
        response = _get_response(
            "https://itunes.apple.com/search",
            params={
                "term": search_term,
                "media": "podcast",
            },
            headers={
                "Accept": "application/json",
            },
            timeout=timeout,
        )
        feeds = list(_parse_feeds(response))
        cache.set(cache_key, feeds)
    return feeds


def search_cache_key(search_term: str) -> str:
    """Cache key based on search term."""
    return "itunes:" + urlsafe_base64_encode(force_bytes(search_term, "utf-8"))


class ItunesCatalogParser:
    """Parses feeds from specific locale in iTunes podcast catalog."""

    def __init__(self, *, locale: str):
        self._locale = locale

        self._feed_ids: set[str] = set()
        self._parser = _itunes_parser()

        self._categories_pattern = re.compile(
            rf"https://podcasts\.apple.com/{self._locale}/genre/podcasts/*."
        )
        self._podcasts_pattern = re.compile(
            rf"https://podcasts\.apple.com/{self._locale}/podcast/*."
        )

    def parse(self) -> Iterator[Feed]:
        """Parses feeds from specific locale."""
        for feed_ids in batcher.batch(self._parse_feed_ids(), 100):
            try:
                yield from _parse_feeds(
                    _get_response(
                        "https://itunes.apple.com/lookup",
                        params={
                            "id": ",".join(feed_ids),
                            "entity": "podcast",
                        },
                        headers={
                            "Accept": "application/json",
                        },
                    )
                )
            except requests.RequestException:
                continue

    def _parse_feed_ids(self) -> Iterator[str]:
        for url in self._parse_urls(
            self._categories_pattern,
            f"https://itunes.apple.com/{self._locale}/genre/podcasts/id26",
        ):
            yield from self._parse_feed_ids_in_category(url)

    def _parse_feed_ids_in_category(self, page_url: str) -> Iterator[str]:
        for url in self._parse_urls(
            self._podcasts_pattern,
            page_url,
        ):
            if (feed_id := _parse_feed_id(url)) and feed_id not in self._feed_ids:
                self._feed_ids.add(feed_id)
                yield feed_id

    def _parse_urls(self, pattern: re.Pattern, url: str) -> Iterator[str]:
        try:
            response = _get_response(url, allow_redirects=True)
            for element in self._parser.iterparse(
                response.content, "{http://www.apple.com/itms/}html", "/apple:html"
            ):
                try:
                    for href in self._parser.itertext(element, "//a//@href"):
                        if pattern.match(href):
                            yield href
                finally:
                    element.clear()
        except (requests.RequestException, lxml.etree.XMLSyntaxError):
            return


def _parse_feed_id(url: str) -> str | None:
    if match := _ITUNES_PODCAST_ID.search(urlparse(url).path.split("/")[-1]):
        return match.group("id")
    return None


def _parse_feeds(
    response: requests.Response,
) -> Iterator[Feed]:
    for batch in batcher.batch(
        _build_feeds_from_json(response.json()),
        100,
    ):
        feeds_for_podcasts, feeds = itertools.tee(batch)

        podcasts = Podcast.objects.filter(
            rss__in={f.rss for f in feeds_for_podcasts},
            private=False,
        ).in_bulk(field_name="rss")

        feeds_for_insert, feeds = itertools.tee(
            (
                dataclasses.replace(feed, podcast=podcasts.get(feed.rss))
                for feed in feeds
            ),
        )

        Podcast.objects.bulk_create(
            (
                Podcast(title=feed.title, rss=feed.rss)
                for feed in set(feeds_for_insert)
                if feed.podcast is None
            ),
            ignore_conflicts=True,
        )

        yield from feeds


def _build_feeds_from_json(json_data: dict) -> Iterator[Feed]:
    for result in json_data.get("results", []):
        try:
            yield Feed(
                rss=result["feedUrl"],
                url=result["collectionViewUrl"],
                title=result["collectionName"],
                image=result["artworkUrl600"],
            )
        except KeyError:
            continue


def _get_response(
    url,
    params: dict | None = None,
    headers: dict | None = None,
    timeout: int = 10,
    **kwargs,
):
    response = requests.get(
        url,
        params=params,
        timeout=timeout,
        headers={
            **(headers or {}),
            "User-Agent": settings.USER_AGENT,
        },
        **kwargs,
    )
    response.raise_for_status()
    return response


@functools.cache
def _itunes_parser() -> XMLParser:
    return XMLParser({"apple": "http://www.apple.com/itms/"})
