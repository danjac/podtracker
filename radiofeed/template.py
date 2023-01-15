from __future__ import annotations

import collections
import math

from django import template
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db.models import Model
from django.shortcuts import resolve_url
from django.template.context import Context, RequestContext
from django.template.defaultfilters import stringfilter
from django.templatetags.static import static
from django.urls import reverse

from radiofeed import encoder
from radiofeed.absolute_uri import build_absolute_uri
from radiofeed.common import markup

register = template.Library()

ActiveLink = collections.namedtuple("ActiveLink", ["url", "css", "active"])


_validate_url = URLValidator(["http", "https"])


@register.simple_tag(takes_context=True)
def pagination_url(context: RequestContext, page_number: int, *args, **kwargs) -> str:
    """Inserts the "page" query string parameter with the provided page number into the template.

    Preserves the original request path and any other query string parameters.

    Given the above and a URL of "/search?q=test" the result would
    be something like: "/search?q=test&page=3"

    Returns:
        updated URL path with new page
    """
    return context.request.paginator.url(page_number, *args, **kwargs)


@register.simple_tag(takes_context=True)
def absolute_uri(context: Context, to: str | Model = "", *args, **kwargs) -> str:
    """Generate absolute URI.

    `to` argument can be :
        * a URL string
        * URL pattern along with `*args` and `**kwargs`
        * Django model with `get_absolute_url()` method.
    """
    return build_absolute_uri(
        resolve_url(to, *args, **kwargs) if to else "",
        request=context.get("request", None),
    )


@register.filter
def format_duration(total_seconds: int | None) -> str:
    """Formats duration (in seconds) as human readable value e.g. 1h 30min."""
    if total_seconds is None or total_seconds < 60:
        return ""

    rv: list[str] = []

    if total_hours := math.floor(total_seconds / 3600):
        rv.append(f"{total_hours}h")

    if total_minutes := round((total_seconds % 3600) / 60):
        rv.append(f"{total_minutes}min")

    return " ".join(rv)


@register.simple_tag(takes_context=True)
def active_link(
    context: RequestContext,
    url_name: str,
    css="link",
    active_css="active",
    *args,
    **kwargs,
) -> ActiveLink:
    """Returns url with active link info."""
    url = resolve_url(url_name, *args, **kwargs)

    return (
        ActiveLink(url, f"{css} {active_css}", True)
        if context.request.path == url
        else ActiveLink(url, css, False)
    )


@register.inclusion_tag("includes/markdown.html")
def markdown(value: str | None) -> dict:
    """Renders Markdown or HTML content."""
    return {"content": markup.markup(value)}


@register.inclusion_tag("includes/cookie_notice.html", takes_context=True)
def cookie_notice(context: RequestContext) -> dict:
    """Renders GDPR cookie notice. Notice should be hidden once user has clicked "Accept Cookies" button."""
    return {"accept_cookies": "accept-cookies" in context.request.COOKIES}


@register.inclusion_tag("includes/icon.html")
def icon(
    name: str, style: str = "", *, size="", title: str = "", css_class: str = ""
) -> dict:
    """Renders a FontAwesome icon."""
    return {
        "name": name,
        "style": f"fa-{style}" if style else "fa",
        "size": f"fa-{size}" if size else "",
        "title": title,
        "css_class": css_class,
    }


@register.inclusion_tag("includes/cover_image.html")
def cover_image(
    cover_url: str,
    size: int,
    title: str,
    url: str = "",
    css_class: str = "",
):
    """Renders a cover image with proxy URL."""
    placeholder = static(f"img/placeholder-{size}.webp")

    proxy_url = (
        reverse(
            "cover_image",
            kwargs={
                "encoded_url": encoder.encode(cover_url),
                "size": size,
            },
        )
        if cover_url
        else ""
    )

    return {
        "cover_url": proxy_url,
        "placeholder": placeholder,
        "title": title,
        "size": size,
        "url": url,
        "css_class": css_class,
    }


@register.filter
@stringfilter
def force_url(url: str) -> str:
    """If a URL is provided minus http(s):// prefix, prepends protocol.

    If we cannot create a valid URL, just return an empty string.
    """
    if url:
        for value in (url, f"https://{url}"):
            try:
                _validate_url(value)
                return value
            except ValidationError:
                continue
    return ""
