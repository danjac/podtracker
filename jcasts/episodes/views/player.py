from __future__ import annotations

from datetime import datetime

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

    return render_player(
        request,
        episode,
        current_time=log.current_time,
        completed=log.completed,
        player_action=True,
    )


@require_http_methods(["POST"])
@ajax_login_required
def close_player(request: HttpRequest, mark_complete: bool = False) -> HttpResponse:

    if episode_id := request.player.pop():
        episode = get_episode_or_404(request, episode_id)
        completed: datetime | None = None

        if mark_complete:

            completed = timezone.now()

            AudioLog.objects.filter(user=request.user, episode=episode).update(
                completed=completed,
                updated=completed,
                current_time=0,
            )

        return render_player(
            request,
            episode,
            completed=completed,
            is_playing=False,
            player_action=True,
        )

    return HttpResponse()


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

        return render_player(
            request,
            log.episode,
            completed=log.completed,
            current_time=log.current_time,
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


def render_player(
    request: HttpRequest,
    episode: Episode,
    *,
    is_playing: bool = True,
    completed: datetime | None = None,
    current_time: int | None = None,
    player_action: bool = False,
):

    return TemplateResponse(
        request,
        "episodes/_player.html",
        {
            "episode": episode,
            "current_time": current_time,
            "is_playing": is_playing,
            "player_action": player_action,
            "completed": completed,
            "listened": timezone.now(),
        },
    )
