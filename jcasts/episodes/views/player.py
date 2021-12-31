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
    episode = get_episode_or_404(request, episode_id, with_podcast=True)

    log, _ = AudioLog.objects.update_or_create(
        episode=episode,
        user=request.user,
        defaults={
            "completed": None,
            "updated": timezone.now(),
        },
    )

    request.player.set(episode.id)

    return TemplateResponse(
        request,
        "episodes/_player.html",
        {
            "log": log,
            "episode": episode,
            "autoplay": True,
            "completed": False,
            "listened": True,
            "is_playing": True,
            "player_action": True,
        },
    )


@require_http_methods(["POST"])
@ajax_login_required
def close_player(request: HttpRequest, mark_complete: bool = False) -> HttpResponse:
    episode: Episode | None = None

    if episode_id := request.player.pop():
        episode = get_episode_or_404(request, episode_id)

        if mark_complete:

            now = timezone.now()

            AudioLog.objects.filter(user=request.user, episode=episode).update(
                completed=now,
                updated=now,
                current_time=0,
            )

    return TemplateResponse(
        request,
        "episodes/_player.html",
        {
            "episode": episode,
            "completed": mark_complete,
            "listened": True,
            "is_playing": False,
            "player_action": True,
        },
    )


@require_http_methods(["GET"])
@ajax_login_required
def reload_player(request: HttpRequest) -> HttpResponse:

    if (episode_id := request.player.get()) and (
        log := (
            AudioLog.objects.filter(user=request.user, episode=episode_id)
            .select_related("episode", "episode__podcast")
            .first()
        )
    ):

        return TemplateResponse(
            request,
            "episodes/_player.html",
            {
                "log": log,
                "episode": log.episode,
                "is_playing": True,
            },
        )

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
