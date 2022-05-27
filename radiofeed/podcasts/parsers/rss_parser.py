from __future__ import annotations

from datetime import datetime
from typing import Generator

import attr
import lxml.etree

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.utils import timezone

from radiofeed.podcasts.parsers.date_parser import parse_date
from radiofeed.podcasts.parsers.xml_parser import XPathFinder, iterparse

NAMESPACES: dict[str, str] = {
    "atom": "http://www.w3.org/2005/Atom",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd",
    "media": "http://search.yahoo.com/mrss/",
    "podcast": "https://podcastindex.org/namespace/1.0",
}


_validate_url = URLValidator(["http", "https"])


def is_explicit(value: str | None) -> bool:
    return (value or "").casefold() in ("clean", "yes")


def is_complete(value: str | None) -> bool:
    return (value or "").casefold() == "yes"


def int_or_none(value: str | None) -> int | None:

    if value is None:
        return None

    try:
        if (result := int(value)) in range(-2147483648, 2147483647):
            return result

    except ValueError:
        ...

    return None


def list_to_str(value: list[str]) -> str:
    return " ".join(value or [])


def language_code(value: str) -> str:
    return value[:2]


def url_or_none(value: str | None) -> str | None:
    try:
        _validate_url(value)
        return value
    except ValidationError:
        return None


def duration(value: str | None) -> str:
    if not value:
        return ""
    try:
        # plain seconds value
        return str(int(value))
    except ValueError:
        pass
    try:
        return ":".join(
            [
                str(v)
                for v in [int(v) for v in value.split(":")[:3]]
                if v in range(0, 60)
            ]
        )
    except ValueError:
        return ""


def is_url(inst: object, attr: attr.Attribute, value: str | None) -> None:
    try:
        _validate_url(value)
    except ValidationError as e:
        raise ValueError from e


def not_empty(inst: object, attr: attr.Attribute, value: str | None) -> None:
    if not value:
        raise ValueError(f"{attr} is empty")


class RssParserError(ValueError):
    ...


@attr.s(kw_only=True)
class Item:

    guid: str = attr.ib(validator=not_empty)
    title: str = attr.ib(validator=not_empty)
    link: str | None = attr.ib(default=None, converter=url_or_none)

    # https://github.com/python/mypy/issues/6172
    pub_date: datetime | None = attr.ib(converter=parse_date)  # type: ignore

    media_url: str = attr.ib(validator=is_url)
    media_type: str = attr.ib()

    explicit: bool = attr.ib(converter=is_explicit)

    length: int | None = attr.ib(default=None, converter=int_or_none)
    season: int | None = attr.ib(default=None, converter=int_or_none)
    episode: int | None = attr.ib(default=None, converter=int_or_none)

    cover_url: str | None = attr.ib(default=None, converter=url_or_none)

    episode_type: str = attr.ib(default="full")
    duration: str = attr.ib(default="", converter=duration)

    description: str = attr.ib(default="")
    keywords: str = attr.ib(default="", converter=list_to_str)

    @pub_date.validator
    def is_pub_date_ok(self, attr: attr.Attribute, value: str | None) -> None:
        if not value or value > timezone.now():
            raise ValueError("not a valid pub date")

    @media_type.validator
    def is_audio(self, attr: attr.Attribute, value: str | None) -> None:
        if not (value or "").startswith("audio/"):
            raise ValueError("not a valid audio enclosure")


@attr.s(kw_only=True)
class Feed:

    title: str | None = attr.ib(validator=not_empty)

    language: str = attr.ib(default="en", converter=language_code)

    link: str | None = attr.ib(default=None, converter=url_or_none)

    cover_url: str | None = attr.ib(default=None, converter=url_or_none)

    funding_text: str = attr.ib(default="")
    funding_url: str | None = attr.ib(default=None, converter=url_or_none)

    owner: str = attr.ib(default="")
    description: str = attr.ib(default="")

    complete: bool = attr.ib(default=False, converter=is_complete)
    explicit: bool = attr.ib(default=False, converter=is_explicit)

    categories: list[str] = attr.ib(default=list)


def parse_rss(content: bytes) -> tuple[Feed, list[Item]]:

    try:
        for element in iterparse(content):
            if element.tag == "channel":
                try:
                    return parse_channel(
                        element,
                        namespaces=NAMESPACES | (element.getparent().nsmap or {}),
                    )
                finally:
                    element.clear()
    except lxml.etree.XMLSyntaxError as e:
        raise RssParserError from e

    raise RssParserError("<channel /> not found in RSS feed")


def parse_channel(
    channel: lxml.etree.Element, namespaces: dict[str, str]
) -> tuple[Feed, list[Item]]:
    try:
        feed = parse_feed(XPathFinder(channel, namespaces))
    except (TypeError, ValueError) as e:
        raise RssParserError from e
    if not (items := [*parse_items(channel, namespaces)]):
        raise RssParserError("no items found in RSS feed")
    return feed, items


def parse_feed(finder: XPathFinder) -> Feed:
    return Feed(
        title=finder.first("title/text()"),
        link=finder.first("link/text()"),
        language=finder.first("language/text()", default="en"),
        complete=finder.first("itunes:complete/text()"),
        explicit=finder.first("itunes:explicit/text()"),
        cover_url=finder.first("itunes:image/@href", "image/url/text()"),
        funding_url=finder.first("podcast:funding/@url"),
        funding_text=finder.first("podcast:funding/text()"),
        description=finder.first(
            "description/text()",
            "itunes:summary/text()",
        ),
        owner=finder.first(
            "itunes:author/text()",
            "itunes:owner/itunes:name/text()",
        ),
        categories=finder.all("//itunes:category/@text"),
    )


def parse_items(
    channel: lxml.etree.Element, namespaces: dict[str, str]
) -> Generator[Item, None, None]:

    for item in channel.iterfind("item"):

        try:
            yield parse_item(XPathFinder(item, namespaces))

        except (ValueError, TypeError):
            pass


def parse_item(finder: XPathFinder) -> Item:
    return Item(
        guid=finder.first("guid/text()"),
        title=finder.first("title/text()"),
        link=finder.first("link/text()"),
        pub_date=finder.first("pubDate/text()"),
        media_url=finder.first(
            "enclosure//@url",
            "media:content//@url",
        ),
        media_type=finder.first(
            "enclosure//@type",
            "media:content//@type",
        ),
        length=finder.first(
            "enclosure//@length",
            "media:content//@fileSize",
        ),
        explicit=finder.first("itunes:explicit/text()"),
        cover_url=finder.first("itunes:image/@href"),
        episode=finder.first("itunes:episode/text()"),
        season=finder.first("itunes:season/text()"),
        description=finder.first(
            "content:encoded/text()",
            "description/text()",
            "itunes:summary/text()",
            default="",
        ),
        duration=finder.first("itunes:duration/text()"),
        episode_type=finder.first("itunes:episodetype/text()", default="full"),
        keywords=finder.all("category/text()"),
    )
