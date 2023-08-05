import httpx
from django.contrib import messages
from django.db import IntegrityError
from django.db.models import Exists, OuterRef
from django.http import Http404, HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.urls import reverse
from django.views.decorators.http import require_POST, require_safe

from radiofeed.decorators import (
    render_htmx,
    require_auth,
    require_DELETE,
    require_form_methods,
)
from radiofeed.episodes.models import Episode
from radiofeed.forms import handle_form
from radiofeed.http import HttpResponseConflict
from radiofeed.podcasts import itunes
from radiofeed.podcasts.forms import PrivateFeedForm
from radiofeed.podcasts.models import Category, Podcast


@require_safe
def landing_page(request: HttpRequest, limit: int = 30) -> HttpResponse:
    """Render default site home page for anonymous users.

    Redirects authenticated users to podcast index page.
    """
    if request.user.is_authenticated:
        return HttpResponseRedirect(reverse("podcasts:index"))

    return TemplateResponse(
        request,
        "podcasts/landing_page.html",
        {
            "podcasts": Podcast.objects.filter(
                pub_date__isnull=False,
                promoted=True,
            ).order_by("-pub_date")[:limit],
        },
    )


@require_safe
@require_auth
@render_htmx(use_blocks="pagination", target="pagination")
def index(request: HttpRequest) -> TemplateResponse:
    """Render default podcast home page for authenticated users."""

    podcasts = Podcast.objects.filter(pub_date__isnull=False).order_by("-pub_date")

    subscribed = podcasts.annotate(
        is_subscribed=Exists(
            request.user.subscriptions.filter(
                podcast=OuterRef("pk"),
            )
        )
    ).filter(is_subscribed=True)

    has_subscriptions = subscribed.exists()
    promoted = "promoted" in request.GET or not has_subscriptions
    podcasts = podcasts.filter(promoted=True) if promoted else subscribed

    return TemplateResponse(
        request,
        "podcasts/index.html",
        {
            "promoted": promoted,
            "has_subscriptions": has_subscriptions,
            "page_obj": request.pagination.get_page(podcasts),
        },
    )


@require_safe
@require_auth
@render_htmx(use_blocks="pagination", target="pagination")
def search_podcasts(request: HttpRequest) -> TemplateResponse:
    """Render search page. Redirects to index page if search is empty."""
    if request.search:
        podcasts = (
            Podcast.objects.search(request.search.value)
            .filter(pub_date__isnull=False, private=False)
            .order_by(
                "-exact_match",
                "-rank",
                "-pub_date",
            )
        )
        return TemplateResponse(
            request,
            "podcasts/search.html",
            {
                "page_obj": request.pagination.get_page(podcasts),
            },
        )

    return HttpResponseRedirect(reverse("podcasts:index"))


@require_safe
@require_auth
def search_itunes(request: HttpRequest) -> HttpResponse:
    """Render iTunes search page. Redirects to index page if search is empty."""
    if request.search:
        feeds: list[itunes.Feed] = []

        try:
            feeds = itunes.search(request.search.value)
        except httpx.HTTPError:
            messages.error(request, "Error: iTunes unavailable")

        return TemplateResponse(
            request,
            "podcasts/itunes_search.html",
            {
                "feeds": feeds,
                "clear_search_url": reverse("podcasts:index"),
            },
        )

    return HttpResponseRedirect(reverse("podcasts:index"))


@require_safe
@require_auth
def latest_episode(
    request: HttpRequest, podcast_id: int, slug: str | None = None
) -> HttpResponseRedirect:
    """Redirects to the latest episode for a given podcast."""
    if (
        episode := Episode.objects.filter(podcast=podcast_id)
        .order_by("-pub_date")
        .first()
    ) is None:
        raise Http404

    return HttpResponseRedirect(episode.get_absolute_url())


@require_safe
@require_auth
def podcast_detail(
    request: HttpRequest, podcast_id: int, slug: str | None = None
) -> TemplateResponse:
    """Details for a single podcast."""

    podcast = get_object_or_404(Podcast, pk=podcast_id)
    is_subscribed = request.user.subscriptions.filter(podcast=podcast).exists()

    return _render_podcast_detail(request, podcast, is_subscribed=is_subscribed)


@require_safe
@require_auth
@render_htmx(use_blocks="pagination", target="pagination")
def episodes(
    request: HttpRequest, podcast_id: int, slug: str | None = None
) -> TemplateResponse:
    """Render episodes for a single podcast."""
    podcast = get_object_or_404(Podcast, pk=podcast_id)

    episodes = podcast.episodes.select_related("podcast")

    if request.search:
        episodes = episodes.search(request.search.value).order_by("-rank", "-pub_date")
    else:
        episodes = episodes.order_by(
            "-pub_date" if request.ordering.is_desc else "pub_date"
        )

    return TemplateResponse(
        request,
        "podcasts/episodes.html",
        {
            "podcast": podcast,
            "is_podcast_detail": True,
            "page_obj": request.pagination.get_page(episodes),
        },
    )


@require_safe
@require_auth
def similar(
    request: HttpRequest, podcast_id: int, slug: str | None = None, limit: int = 12
) -> TemplateResponse:
    """List similar podcasts based on recommendations."""

    podcast = get_object_or_404(Podcast, pk=podcast_id)

    recommendations = (
        podcast.recommendations.with_relevance()
        .select_related("recommended")
        .order_by("-relevance")[:limit]
    )

    return TemplateResponse(
        request,
        "podcasts/similar.html",
        {
            "podcast": podcast,
            "recommendations": recommendations,
        },
    )


@require_safe
@require_auth
def category_list(request: HttpRequest) -> TemplateResponse:
    """List all categories containing podcasts."""
    categories = (
        Category.objects.annotate(
            has_podcasts=Exists(
                Podcast.objects.filter(
                    categories=OuterRef("pk"),
                    pub_date__isnull=False,
                    private=False,
                )
            )
        )
        .filter(has_podcasts=True)
        .order_by("name")
    )

    if request.search:
        categories = categories.search(request.search.value)

    return TemplateResponse(
        request,
        "podcasts/categories.html",
        {
            "categories": categories,
        },
    )


@require_safe
@require_auth
@render_htmx(use_blocks="pagination", target="pagination")
def category_detail(
    request: HttpRequest, category_id: int, slug: str | None = None
) -> TemplateResponse:
    """Render individual podcast category along with its podcasts.

    Podcasts can also be searched.
    """
    category = get_object_or_404(Category, pk=category_id)

    podcasts = category.podcasts.filter(
        pub_date__isnull=False, private=False
    ).distinct()

    if request.search:
        podcasts = podcasts.search(request.search.value).order_by(
            "-exact_match",
            "-rank",
            "-pub_date",
        )
    else:
        podcasts = podcasts.order_by("-pub_date")

    return TemplateResponse(
        request,
        "podcasts/category_detail.html",
        {
            "category": category,
            "page_obj": request.pagination.get_page(podcasts),
        },
    )


@require_POST
@require_auth
@render_htmx(use_blocks="subscribe_button")
def subscribe(request: HttpRequest, podcast_id: int) -> TemplateResponse:
    """Subscribe a user to a podcast. Podcast must be active and public."""
    podcast = get_object_or_404(Podcast, private=False, pk=podcast_id)
    try:
        request.user.subscriptions.create(podcast=podcast)
    except IntegrityError:
        return HttpResponseConflict()

    messages.success(request, "Subscribed to Podcast")
    return _render_podcast_detail(request, podcast, is_subscribed=True)


@require_DELETE
@require_auth
@render_htmx(use_blocks="subscribe_button")
def unsubscribe(request: HttpRequest, podcast_id: int) -> TemplateResponse:
    """Unsubscribe user from a podcast."""
    podcast = get_object_or_404(Podcast, private=False, pk=podcast_id)
    request.user.subscriptions.filter(podcast=podcast).delete()
    messages.info(request, "Unsubscribed from Podcast")
    return _render_podcast_detail(request, podcast, is_subscribed=False)


@require_safe
@require_auth
@render_htmx(use_blocks="pagination", target="pagination")
def private_feeds(request: HttpRequest) -> HttpResponse:
    """Lists user's private feeds."""
    podcasts = Podcast.objects.annotate(
        is_subscribed=Exists(
            request.user.subscriptions.filter(
                podcast=OuterRef("pk"),
            )
        )
    ).filter(
        is_subscribed=True,
        private=True,
        pub_date__isnull=False,
    )

    if request.search:
        podcasts = podcasts.search(request.search.value).order_by(
            "-exact_match",
            "-rank",
            "-pub_date",
        )
    else:
        podcasts = podcasts.order_by("-pub_date")

    return TemplateResponse(
        request,
        "podcasts/private_feeds.html",
        {
            "page_obj": request.pagination.get_page(podcasts),
        },
    )


@require_form_methods
@require_auth
@render_htmx(use_blocks="form", target="private-feed-form")
def add_private_feed(request: HttpRequest) -> HttpResponse:
    """Add new private feed to collection."""
    form, result = handle_form(PrivateFeedForm, request, user=request.user)

    if result.success:
        podcast, is_new = form.save()

        messages.success(request, "Added to Private Feeds")

        redirect_url = (
            reverse("podcasts:private_feeds") if is_new else podcast.get_absolute_url()
        )

        return HttpResponseRedirect(redirect_url)

    return TemplateResponse(
        request,
        "podcasts/private_feed_form.html",
        {
            "form": form,
        },
        status=result.status,
    )


@require_DELETE
@require_auth
def remove_private_feed(request: HttpRequest, podcast_id: int) -> HttpResponseRedirect:
    """Removes subscription to private feed."""
    podcast = get_object_or_404(Podcast, private=True, pk=podcast_id)
    request.user.subscriptions.filter(podcast=podcast).delete()
    messages.info(request, "Removed from Private Feeds")
    return HttpResponseRedirect(reverse("podcasts:private_feeds"))


def _render_podcast_detail(
    request: HttpRequest, podcast: Podcast, *, is_subscribed: bool
) -> TemplateResponse:
    return TemplateResponse(
        request,
        "podcasts/detail.html",
        {
            "podcast": podcast,
            "is_subscribed": is_subscribed,
        },
    )
