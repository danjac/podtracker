from __future__ import annotations

from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest
from django.template.response import TemplateResponse
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from ratelimit.decorators import ratelimit

from jcasts.episodes.models import AudioLog, Episode
from jcasts.episodes.views import get_episode_or_404
from jcasts.shared.decorators import ajax_login_required
from jcasts.shared.response import HttpResponseNoContent


@require_http_methods(["POST"])
@ajax_login_required
def start_player(request: HttpRequest, episode_id: int) -> HttpResponse:
    remove_episode_from_player(request, mark_complete=False)

    return render_start_player(
        request, get_episode_or_404(request, episode_id, with_podcast=True)
    )


@require_http_methods(["POST"])
@ajax_login_required
def close_player(request: HttpRequest) -> HttpResponse:
    episode: Episode | None = None

    if episode_id := remove_episode_from_player(request, mark_complete=False):

        episode = get_episode_or_404(
            request,
            episode_id,
            with_current_time=True,
        )

    return render_player(
        request,
        {
            "episode": episode,
            "is_playing": False,
        },
    )


@require_http_methods(["GET"])
@ajax_login_required
def reload_player(request: HttpRequest) -> HttpResponse:

    if episode_id := request.player.get():
        log = (
            AudioLog.objects.filter(user=request.user, episode=episode_id)
            .select_related("episode", "episode__podcast")
            .first()
        )
        return render_player(request, {"log": log})

    return HttpResponse()


@ratelimit(key="ip", rate="20/m")
@require_http_methods(["POST"])
@ajax_login_required
def player_time_update(request: HttpRequest) -> HttpResponse:
    """Update current play time of episode."""

    try:
        if episode_id := request.player.get():

            AudioLog.objects.filter(episode=episode_id, user=request.user).update(
                completed=None,
                updated=timezone.now(),
                current_time=int(request.POST["current_time"]),
            )

        return HttpResponseNoContent()
    except (KeyError, ValueError):
        return HttpResponseBadRequest()


def remove_episode_from_player(request: HttpRequest, mark_complete: bool) -> int | None:

    if (episode_id := request.player.pop()) and mark_complete:

        now = timezone.now()

        AudioLog.objects.filter(user=request.user, episode_id=episode_id).update(
            updated=now,
            completed=now,
            current_time=0,
        )

    return episode_id


def render_start_player(request: HttpRequest, episode: Episode) -> HttpResponse:

    log, _ = AudioLog.objects.update_or_create(
        episode=episode,
        user=request.user,
        defaults={
            "completed": None,
            "updated": timezone.now(),
        },
    )

    request.player.set(episode.id)

    return render_player(
        request,
        {
            "log": log,
            "episode": episode,
            "autoplay": True,
            "is_playing": True,
        },
    )


def render_player(
    request: HttpRequest, extra_context: dict | None = None
) -> HttpResponse:
    return TemplateResponse(request, "episodes/_player.html", extra_context)
