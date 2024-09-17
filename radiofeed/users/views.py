from typing import TypedDict

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect
from django.template.defaultfilters import pluralize
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_safe

from radiofeed.http import HttpRequest, UserRequest, require_form_methods
from radiofeed.partials import render_partial_for_target
from radiofeed.podcasts.models import Podcast
from radiofeed.users.forms import OpmlUploadForm, UserPreferencesForm


class UserStat(TypedDict):
    """Line item in user stats"""

    label: str
    value: int
    unit: str
    url: str


@require_form_methods
@login_required
def user_preferences(
    request: UserRequest,
) -> HttpResponseRedirect | TemplateResponse:
    """Allow user to edit their preferences."""
    if request.method == "POST":
        form = UserPreferencesForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Your preferences have been saved")
            return HttpResponseRedirect(request.path)
    else:
        form = UserPreferencesForm(instance=request.user)

    return render_partial_for_target(
        request,
        TemplateResponse(
            request,
            "account/preferences.html",
            {
                "form": form,
            },
        ),
        target="preferences-form",
        partial="form",
    )


@require_form_methods
@login_required
def import_podcast_feeds(
    request: UserRequest,
) -> HttpResponseRedirect | TemplateResponse:
    """Imports an OPML document and subscribes user to any discovered feeds."""
    if request.method == "POST":
        form = OpmlUploadForm(request.POST, request.FILES)
        if form.is_valid():
            if num_new_feeds := len(form.subscribe_to_feeds(request.user)):
                messages.success(
                    request,
                    f"{num_new_feeds} podcast feed{pluralize(num_new_feeds)} added to your collection",
                )
            else:
                messages.info(request, "No new podcasts found in uploaded file")
            return HttpResponseRedirect(request.path)
    else:
        form = OpmlUploadForm()

    return render_partial_for_target(
        request,
        TemplateResponse(
            request,
            "account/podcast_feeds.html",
            {
                "upload_form": form,
            },
        ),
        target="import-feeds-form",
        partial="form",
    )


@require_safe
@login_required
def export_podcast_feeds(request: UserRequest) -> TemplateResponse:
    """Download OPML document containing public feeds from user's subscriptions."""

    podcasts = (
        Podcast.objects.subscribed(request.user)
        .filter(
            private=False,
            pub_date__isnull=False,
        )
        .order_by("title")
    )

    return TemplateResponse(
        request,
        "feedparser/podcasts.opml",
        {
            "site": request.site,
            "podcasts": podcasts,
        },
        content_type="text/x-opml",
        headers={
            "Content-Disposition": "attachment;"
            f"filename=podcasts-{timezone.now().strftime('%Y-%m-%d')}.opml"
        },
    )


@require_safe
@login_required
def user_stats(request: UserRequest) -> TemplateResponse:
    """Render user statistics including listening history, subscriptions, etc."""
    stats = [
        UserStat(
            label="Subscribed",
            value=request.user.subscriptions.count(),
            unit="podcast",
            url=reverse("podcasts:subscriptions"),
        ),
        UserStat(
            label="Private Feeds",
            value=request.user.subscriptions.filter(podcast__private=True).count(),
            unit="podcast",
            url=reverse("podcasts:private_feeds"),
        ),
        UserStat(
            label="Bookmarks",
            value=request.user.bookmarks.count(),
            unit="episode",
            url=reverse("episodes:bookmarks"),
        ),
        UserStat(
            label="Listened",
            value=request.user.audio_logs.count(),
            unit="episode",
            url=reverse("episodes:history"),
        ),
    ]
    return TemplateResponse(request, "account/stats.html", {"stats": stats})


@require_form_methods
def delete_account(request: HttpRequest) -> HttpResponseRedirect | TemplateResponse:
    """Delete account on confirmation."""
    if (
        request.user.is_authenticated
        and request.method == "POST"
        and "confirm-delete" in request.POST
    ):
        request.user.delete()
        logout(request)
        messages.info(request, "Your account has been deleted")
        return HttpResponseRedirect(reverse("index"))
    return TemplateResponse(request, "account/delete_account.html")
