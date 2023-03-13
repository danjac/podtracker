from __future__ import annotations

import html

from typing import Final

from django.template.defaultfilters import striptags
from lxml.html.clean import Cleaner, autolink_html

_ALLOWED_TAGS: Final = {
    "a",
    "abbr",
    "acronym",
    "address",
    "b",
    "br",
    "code",
    "div",
    "dl",
    "dt",
    "em",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "hr",
    "i",
    "li",
    "ol",
    "p",
    "pre",
    "q",
    "s",
    "small",
    "strike",
    "strong",
    "span",
    "sub",
    "sup",
    "table",
    "tbody",
    "td",
    "tfoot",
    "th",
    "thead",
    "tr",
    "tt",
    "u",
    "ul",
}

_cleaner = Cleaner(allow_tags=_ALLOWED_TAGS, safe_attrs_only=True, add_nofollow=True)


def clean_html(value: str) -> str:
    """Scrubs any unwanted HTML tags and attributes."""
    return (
        _cleaner.clean_html(
            autolink_html(
                value,
                avoid_elements=[
                    "textarea",
                    "pre",
                    "code",
                ],
            )
        )
        if (value := value.strip())
        else ""
    )


def strip_html(value: str) -> str:
    """Scrubs all HTML tags and entities from text."""
    return html.unescape(striptags(value.strip()))
