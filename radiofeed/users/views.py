from __future__ import annotations

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.template.response import SimpleTemplateResponse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.translation import ngettext, override
from django.views.decorators.http import require_POST, require_safe
from django_htmx.http import HttpResponseClientRedirect

from radiofeed.common.decorators import require_form_methods
from radiofeed.podcasts.models import Podcast
from radiofeed.users.forms import OpmlUploadForm, UserPreferencesForm


@require_form_methods
@login_required
def user_preferences(request: HttpRequest) -> HttpResponse:
    """Handle user preferences."""
    form = UserPreferencesForm(request.POST or None, instance=request.user)
    original_language = request.user.language

    if request.method == "POST" and form.is_valid():

        user = form.save()

        with override(user.language):
            messages.success(request, _("Your preferences have been saved"))

        # do redirect to refresh UI if language changed
        if user.language != original_language:
            return HttpResponseClientRedirect(request.htmx.current_url)

    return render(request, "account/preferences.html", {"form": form})


@require_safe
@login_required
def import_export_podcast_feeds(request: HttpRequest) -> HttpResponse:
    """Renders import/export page."""
    return render(
        request,
        "account/import_export_podcast_feeds.html",
        {
            "form": OpmlUploadForm(),
            "target": "opml-import-form",
        },
    )


@require_POST
@login_required
def import_podcast_feeds(request: HttpRequest) -> HttpResponse:
    """Imports an OPML document and subscribes user to any discovered feeds."""
    form = OpmlUploadForm(request.POST, request.FILES)
    if form.is_valid():

        if new_feeds := form.subscribe_to_feeds(request.user):
            messages.success(
                request,
                ngettext(
                    "%(count)d podcast feed added to your collection",
                    "%(count)d podcast feeds added to your collection",
                    new_feeds,
                )
                % {"count": new_feeds},
            )
        else:
            messages.info(request, _("No new podcasts found in uploaded file"))

    return render(request, "account/import_export_podcast_feeds.html", {"form": form})


@require_POST
@login_required
def export_podcast_feeds(request: HttpRequest) -> HttpResponse:
    """Download OPML document containing feeds from user's subscriptions."""
    return SimpleTemplateResponse(
        "account/podcasts.opml",
        {
            "podcasts": (
                Podcast.objects.filter(
                    subscriptions__subscriber=request.user,
                )
                .distinct()
                .order_by("title")
                .iterator()
            )
        },
        content_type="text/x-opml",
        headers={
            "Content-Disposition": f"attachment; filename=podcasts-{timezone.now().strftime('%Y-%m-%d')}.opml"
        },
    )


@require_safe
@login_required
def user_stats(request: HttpRequest) -> HttpResponse:
    """Render user statistics including listening history, subscriptions, etc."""
    return render(request, "account/stats.html")


@require_form_methods
@login_required
def delete_account(request: HttpRequest) -> HttpResponse:
    """Delete account on confirmation.

    Returns:
         redirect to index page on delete confirmation, otherwise render delete confirmation page.
    """
    if request.method == "POST" and "confirm-delete" in request.POST:
        request.user.delete()
        logout(request)
        messages.info(request, _("Your account has been deleted"))
        return redirect(settings.HOME_URL)
    return render(request, "account/delete_account.html")
