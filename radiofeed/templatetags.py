from __future__ import annotations

import functools
import itertools
import json
import math
from typing import TYPE_CHECKING, Any, Final, TypedDict

from django import template
from django.conf import settings
from django.contrib.sites.models import Site
from django.core.serializers.json import DjangoJSONEncoder
from django.shortcuts import resolve_url
from django.template.defaultfilters import pluralize
from django.utils.encoding import force_str
from django.utils.functional import LazyObject

from radiofeed import covers, html

if TYPE_CHECKING:  # pragma: nocover
    from django.template.context import RequestContext

    from radiofeed.covers import CoverVariant


_SECONDS_IN_MINUTE: Final = 60
_SECONDS_IN_HOUR: Final = 3600

register = template.Library()


class ActiveLink(TypedDict):
    """Provides details on whether a link is currently active, along with its
    URL and CSS."""

    url: str
    css: str
    active: bool


@register.simple_tag(takes_context=True)
def active_link(
    context: RequestContext,
    to: Any,
    *args,
    css: str = "link",
    active_css: str = "active",
    **kwargs,
) -> ActiveLink:
    """Returns url with active link info if matching URL."""
    url = resolve_url(to, *args, **kwargs)
    return (
        ActiveLink(active=True, css=f"{css} {active_css}", url=url)
        if context.request.path == url
        else ActiveLink(active=False, css=css, url=url)
    )


@register.simple_tag
def json_attr(*pairs: str) -> str:
    """Renders attribute value containing JSON.

    Takes multiple pairs of headers and values e.g.:
        {% json_attr "hx-headers" "X-CSRFToken" csrf_token "myHeader" "form" %}

    This will generate:
        '{"X-CSRF-Token": "...", "myHeader": "form"}'

    Note: LazyObjects will be resolved to strings. Should be ok for the simple case e.g
    csrf_token but more complex cases should require evaluation of the lazy value first.
    """
    return json.dumps(
        {
            k: force_str(v) if isinstance(v, LazyObject) else v
            for k, v in itertools.batched(pairs, 2)
        },
        cls=DjangoJSONEncoder,
    )


@register.simple_tag
def htmx_config() -> str:
    """Returns HTMX config."""
    return json.dumps(settings.HTMX_CONFIG, cls=DjangoJSONEncoder)


@register.simple_tag
def theme_color() -> dict:
    """Returns the PWA configuration theme color."""
    return settings.PWA_CONFIG["manifest"]["theme_color"]


@register.simple_tag
@functools.cache
def get_site() -> Site:
    """Returns the current Site instance. Use when `request.site` is unavailable, e.g. in emails run from cronjobs."""

    return Site.objects.get_current()


@register.simple_tag
def absolute_uri(to: Any | None = None, *args, **kwargs) -> str:
    """Returns the absolute URL to site domain."""

    site = get_site()
    path = resolve_url(to, *args, **kwargs) if to else ""
    scheme = "https" if settings.SECURE_SSL_REDIRECT else "http"

    return f"{scheme}://{site.domain}{path}"


get_cover_attrs = register.simple_tag(covers.get_cover_attrs)


@register.inclusion_tag("_cover_image.html")
def cover_image(
    variant: CoverVariant,
    cover_url: str,
    title: str,
    *,
    css_class: str = "",
) -> dict:
    """Renders a cover image with proxy URL."""
    return {
        "attrs": covers.get_cover_attrs(cover_url, variant)
        | {
            "title": title,
            "alt": title,
        },
        "classes": [
            classes
            for classes in [covers.get_cover_class(variant), css_class]
            if classes
        ],
    }


@register.inclusion_tag("_search_form.html", takes_context=True)
def search_form(
    context: RequestContext,
    *,
    search_url: str = "",
    placeholder: str = "Search",
    clear_search: bool = True,
    **attrs,
) -> dict:
    """Renders search form.

    If `search_url` is `None`, assumes current URL for search.
    """

    search_url = search_url or context.request.path
    clear_search_url = context.request.path if clear_search else None

    return context.flatten() | {
        "search_url": search_url,
        "clear_search_url": clear_search_url,
        "placeholder": placeholder,
        "attrs": attrs,
    }


@register.inclusion_tag("_search_button.html", takes_context=True)
def search_button(
    context: RequestContext,
    search_url: str,
    label: str,
    **attrs,
) -> dict:
    """Renders search button."""

    return context.flatten() | {
        "search_url": search_url,
        "label": label,
        "attrs": attrs,
    }


@register.inclusion_tag("_gdpr_cookies_banner.html", takes_context=True)
def gdpr_cookies_banner(context: RequestContext) -> dict:
    """Renders GDPR cookie notice. Notice should be hidden once user has clicked
    "Accept Cookies" button."""
    return context.flatten() | {
        "accept_cookies": settings.GDPR_COOKIE_NAME in context.request.COOKIES,
    }


@register.inclusion_tag("_markdown.html")
def markdown(content: str | None) -> dict:
    """Render content as Markdown."""
    return {"content": html.markdown(content or "")}


@register.filter
def format_duration(total_seconds: int | None) -> str:
    """Formats duration (in seconds) as human readable value e.g. 1h 30min."""
    if total_seconds is None or total_seconds < _SECONDS_IN_MINUTE:
        return ""

    rv: list[str] = []

    if total_hours := math.floor(total_seconds / _SECONDS_IN_HOUR):
        rv.append(f"{total_hours} hour{pluralize(total_hours)}")

    if total_minutes := round((total_seconds % _SECONDS_IN_HOUR) / _SECONDS_IN_MINUTE):
        rv.append(f"{total_minutes} minute{pluralize(total_minutes)}")

    return " ".join(rv)


@register.filter
def percentage(value: float, total: float) -> int:
    """Returns % value.

    Example:
    {{ value|percentage:total }}% done
    """
    if 0 in (value, total):
        return 0
    return min(math.ceil((value / total) * 100), 100)
