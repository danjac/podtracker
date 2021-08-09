from __future__ import annotations

import http
import secrets

from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from typing import Generator

import feedparser
import requests

from django.utils import timezone
from django.utils.http import http_date, quote_etag
from django_rq import job
from feedparser.http import ACCEPT_HEADER
from pydantic import BaseModel, HttpUrl, ValidationError, root_validator, validator

from jcasts.episodes.models import Episode
from jcasts.podcasts.date_parser import parse_date
from jcasts.podcasts.models import Category, Podcast
from jcasts.podcasts.scheduler import schedule
from jcasts.podcasts.text_parser import extract_keywords

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.1.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:77.0) Gecko/20100101 Firefox/77.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.97 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:77.0) Gecko/20100101 Firefox/77.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.97 Safari/537.36",
]

EPISODE_BATCH_SIZE = 500


class Content(BaseModel):
    value: str = ""
    type: str = ""


class Enclosure(BaseModel):
    href: HttpUrl
    length: int = None
    type: str = ""
    rel: str = ""


class Tag(BaseModel):
    term: str


class Author(BaseModel):
    name: str


class Image(BaseModel):
    href: HttpUrl


class Item(BaseModel):

    id: str

    title: str = ""
    published: datetime

    image: Image = None
    link: HttpUrl = None

    itunes_explicit: bool = False
    itunes_season: int = None
    itunes_episode: int = None
    itunes_episodetype: str = "full"
    itunes_duration: str = ""

    description: str = ""
    summary: str = ""
    content: list[Content] = []

    audio: Enclosure

    enclosures: list[Enclosure] = []
    links: list[Enclosure] = []
    tags: list[Tag] = []

    @validator("published", pre=True)
    def get_published(cls, value: str | None) -> datetime | None:
        pub_date = parse_date(value)
        if pub_date and pub_date < timezone.now():
            return pub_date
        raise ValueError("No pub date")

    @validator("itunes_explicit", pre=True)
    def get_explicit(cls, value: str | bool | None) -> bool:
        return parse_explicit(value)

    @root_validator
    def get_description(cls, values: dict) -> dict:
        if description := parse_contents(values.get("content", [])):
            return {**values, "description": description}
        return values

    @root_validator(pre=True)
    def get_audio(cls, values: dict) -> dict:
        try:
            values["audio"] = next(
                filter(is_audio, values.get("enclosures", []) + values.get("links", []))
            )
            return values
        except StopIteration:
            raise ValueError("No audio enclosures found")


class Feed(BaseModel):

    title: str
    link: HttpUrl = None
    author: str = ""

    image: Image = None
    language: str = "en"

    publisher_detail: Author = None

    content: str = ""
    summary: str = ""
    description: str = ""
    subtitle: str = ""

    itunes_explicit: bool = False

    tags: list[Tag] = []

    @validator("itunes_explicit", pre=True)
    def get_explicit(cls, value: str | bool | None) -> bool:
        return parse_explicit(value)


@dataclass
class ParseResult:
    status: int | None = None
    success: bool = False
    exception: Exception | None = None

    def __bool__(self) -> bool:
        return self.success

    def raise_exception(self) -> None:
        if self.exception:
            raise self.exception


@lru_cache
def get_categories_dict() -> dict[str, Category]:
    return Category.objects.in_bulk(field_name="name")


def parse_frequent_feeds(force_update: bool = False) -> int:
    counter = 0
    qs = (
        Podcast.objects.frequent()
        .order_by("scheduled", "-pub_date")
        .values_list("rss", flat=True)
    )

    if not force_update:
        qs = qs.filter(
            scheduled__isnull=False,
            scheduled__lte=timezone.now(),
        )

    for counter, rss in enumerate(qs.iterator(), 1):
        parse_feed.delay(rss, force_update=force_update)

    return counter


def parse_sporadic_feeds() -> int:
    "Should run daily. Matches older feeds with same weekday in last pub date"
    counter = 0
    for counter, rss in enumerate(
        Podcast.objects.sporadic()
        .filter(
            pub_date__iso_week_day=timezone.now().isoweekday(),
        )
        .order_by("-pub_date")
        .values_list("rss", flat=True)
        .iterator(),
        1,
    ):
        parse_feed.delay(rss)

    return counter


@job("feeds")
def parse_feed(rss: str, *, force_update: bool = False) -> ParseResult:
    try:

        podcast = Podcast.objects.get(rss=rss, active=True)
    except Podcast.DoesNotExist as e:
        return ParseResult(None, False, exception=e)

    try:
        response = requests.get(
            podcast.rss,
            headers=get_feed_headers(podcast, force_update),
            allow_redirects=True,
            timeout=10,
        )

        response.raise_for_status()
    except requests.HTTPError:
        # dead feed, don't request again
        return parse_failure(podcast, status=response.status_code, active=False)

    except requests.RequestException as e:
        # temp issue, maybe network error, log & try again later
        return parse_failure(
            podcast, status=e.response.status_code if e.response else None, exception=e
        )

    if response.status_code == http.HTTPStatus.NOT_MODIFIED:
        # no change, ignore
        return parse_failure(podcast, status=response.status_code)

    return parse_podcast(podcast, response)


def parse_podcast(podcast: Podcast, response: requests.Response) -> ParseResult:

    rss, is_changed = resolve_podcast_rss(podcast, response)

    if is_changed and (
        other := Podcast.objects.filter(rss=rss).exclude(pk=podcast.pk).first()
    ):
        # permanent redirect to URL already taken by another podcast
        return parse_failure(
            podcast, status=response.status_code, redirect_to=other, active=False
        )

    result = feedparser.parse(response.content)

    # check if any items
    if not (items := list(parse_items(result.entries))):
        return parse_failure(podcast, status=response.status_code, rss=rss)

    podcast.rss = rss
    podcast.etag = response.headers.get("ETag", "")
    podcast.modified = parse_date(response.headers.get("Last-Modified"))
    podcast.status = response.status_code
    podcast.exception = ""

    podcast.num_episodes = len(items)

    pub_dates = [item.published for item in items]

    podcast.pub_date = max(pub_dates)
    podcast.scheduled = schedule(podcast, pub_dates)

    try:
        feed = Feed.parse_obj(result.feed)
    except ValidationError as e:
        return parse_failure(podcast, status=response.status_code, exception=e)

    podcast.title = feed.title
    podcast.link = feed.link
    podcast.cover_url = feed.image.href if feed.image else None

    podcast.language = feed.language[:2]

    podcast.description = (
        feed.content or feed.summary or feed.description or feed.subtitle
    )

    podcast.owner = feed.publisher_detail.name if feed.publisher_detail else feed.author
    podcast.explicit = feed.itunes_explicit

    keywords, categories = parse_taxonomy(feed)

    podcast.keywords = " ".join(keywords)
    podcast.extracted_text = extract_text(podcast, categories, items)
    podcast.categories.set(categories)  # type: ignore

    podcast.save()

    parse_episodes(podcast, items)

    return ParseResult(response.status_code, True)


def parse_episodes(podcast: Podcast, items: list[Item]) -> None:
    """Remove any episodes no longer in feed, update any current and
    add new"""

    qs = Episode.objects.filter(podcast=podcast)

    # remove any episodes that may have been deleted on the podcast
    qs.exclude(guid__in=[item.id for item in items]).delete()

    # determine new/current items
    guid_map = dict(qs.values_list("guid", "pk"))

    episodes = [
        make_episode(podcast, item, guid_map.get(item.id, None)) for item in items
    ]

    guids = guid_map.keys()

    # update existing content

    Episode.objects.bulk_update(
        [episode for episode in episodes if episode.guid in guids],
        fields=[
            "cover_url",
            "description",
            "duration",
            "episode",
            "episode_type",
            "explicit",
            "keywords",
            "length",
            "link",
            "media_type",
            "media_url",
            "season",
            "title",
        ],
        batch_size=EPISODE_BATCH_SIZE,
    )

    # new episodes

    Episode.objects.bulk_create(
        [episode for episode in episodes if episode.guid not in guids],
        ignore_conflicts=True,
        batch_size=EPISODE_BATCH_SIZE,
    )


def make_episode(podcast: Podcast, item: Item, pk: int | None = None) -> Episode:
    return Episode(
        pk=pk,
        podcast=podcast,
        pub_date=item.published,
        guid=item.id,
        title=item.title,
        link=item.link,
        description=item.description or item.summary,
        explicit=item.itunes_explicit,
        season=item.itunes_season,
        episode=item.itunes_episode,
        episode_type=item.itunes_episodetype,
        cover_url=item.image.href if item.image else None,
        media_url=item.audio.href,
        length=item.audio.length,
        media_type=item.audio.type,
        duration=item.itunes_duration,
        keywords=" ".join([tag.term for tag in item.tags if tag.term]),
    )


def parse_taxonomy(feed: Feed) -> tuple[list[str], list[Category]]:
    categories_dct = get_categories_dict()
    tags = [t.term for t in feed.tags if t.term]
    return (
        [tag for tag in tags if tag and tag not in categories_dct],
        [categories_dct[tag] for tag in tags if tag in categories_dct],
    )


def extract_text(
    podcast: Podcast,
    categories: list[Category],
    items: list[Item],
) -> str:
    text = " ".join(
        [
            podcast.title,
            podcast.description,
            podcast.keywords,
            podcast.owner,
        ]
        + [c.name for c in categories]
        + [item.title for item in items][:6]
    )
    return " ".join(extract_keywords(podcast.language, text))


def parse_items(entries: list[dict]) -> Generator[Item, None, None]:

    for entry in entries:
        try:
            yield Item.parse_obj(entry)
        except ValidationError:
            pass


def is_audio(link: Enclosure) -> bool:
    return bool(
        link.type
        and link.type.startswith("audio/")
        and link.href
        and link.rel == "enclosure"
    )


def get_feed_headers(podcast: Podcast, force_update: bool = False) -> dict[str, str]:
    headers: dict[str, str] = {
        "Accept": ACCEPT_HEADER,
        "User-Agent": secrets.choice(USER_AGENTS),
    }

    # ignore any modified/etag headers
    if force_update:
        return headers

    if podcast.etag:
        headers["If-None-Match"] = quote_etag(podcast.etag)
    if podcast.modified:
        headers["If-Modified-Since"] = http_date(podcast.modified.timestamp())
    return headers


def resolve_podcast_rss(
    podcast: Podcast, response: requests.Response
) -> tuple[str, bool]:

    return response.url, (
        response.status_code
        in (
            http.HTTPStatus.MOVED_PERMANENTLY,
            http.HTTPStatus.PERMANENT_REDIRECT,
        )
        or response.url != podcast.rss
    )


def parse_explicit(value: str | None | bool) -> bool:
    if value in (None, False, "no", "none"):
        return False
    return True


def parse_contents(contents: list[Content]) -> str:
    for content_type in ("text/html", "text/plain"):
        for content in contents:
            if content.type == content_type and content.value:
                return content.value
    return ""


def parse_failure(
    podcast: Podcast,
    *,
    status: int | None,
    exception: Exception | None = None,
    active=True,
    **fields,
) -> ParseResult:

    Podcast.objects.filter(pk=podcast.id).update(
        scheduled=schedule(podcast) if active else None,
        updated=timezone.now(),
        active=active,
        status=status,
        **fields,
    )

    return ParseResult(status, False, exception)
