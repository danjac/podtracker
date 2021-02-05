from typing import Dict, Generator, List, Optional

import bs4
import feedparser
from pydantic import ValidationError

from .date_parser import parse_date
from .models import Audio, Feed, Item


def parse_xml(xml: bytes) -> Feed:
    result = feedparser.parse(xml)
    channel = result["feed"]

    return Feed(
        title=channel.get("title", None),
        description=channel.get("description", ""),
        link=channel.get("link", ""),
        explicit=bool(channel.get("itunes_explicit", False)),
        authors=[a["name"] for a in channel.get("authors", []) if "name" in a],
        image=parse_image(xml, channel),
        categories=list(parse_tags(channel.get("tags", []))),
        items=list(parse_items(result)),
    )


def parse_items(result: Dict) -> Generator:
    entries = list(
        {e["id"]: e for e in result.get("entries", []) if "id" in e}.values()
    )
    for entry in entries:
        try:
            yield Item(
                guid=entry["id"],
                title=entry.get("title"),
                duration=entry.get("itunes_duration", ""),
                explicit=bool(entry.get("itunes_explicit", False)),
                audio=parse_audio(entry),
                description=parse_description(entry),
                keywords=" ".join(parse_tags(entry.get("tags", []))),
                pub_date=parse_date(entry.get("published")),
            )
        except ValidationError:
            pass


def parse_tags(tags: List[Dict]) -> Generator:
    for t in tags:
        term = t.get("term")
        if term:
            yield term


def parse_audio(entry: Dict) -> Optional[Audio]:

    for link in entry.get("links", []):
        try:
            return Audio(
                rel=link["rel"],
                type=link["type"],
                url=link["url"],
                length=link.get("length", None),
            )
        except (ValidationError, KeyError):
            pass

    return None


def parse_description(entry: Dict) -> str:
    try:
        return (
            [
                c["value"]
                for c in entry.get("content", [])
                if c.get("type") == "text/html"
            ]
            + [
                entry[field]
                for field in ("description", "summary", "subtitle")
                if field in entry and entry[field]
            ]
        )[0]
    except (KeyError, IndexError):
        return ""


def parse_image(xml: bytes, channel: Dict) -> Optional[str]:
    # try itunes image first
    soup = bs4.BeautifulSoup(xml, "lxml")
    tag = soup.find("itunes:image")
    if tag and "href" in tag.attrs:
        return tag.attrs["href"]

    try:
        return channel["image"]["href"]
    except KeyError:
        pass

    return None
