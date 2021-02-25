import http
import json
from typing import List, Optional

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest
from django.views.decorators.http import require_POST

from turbo_response import TurboStream, TurboStreamResponse

from radiofeed.shortcuts import render_component
from radiofeed.users.decorators import ajax_login_required

from ..models import Episode, QueueItem
from . import get_episode_detail_or_404
from .queue import get_queue_items


@require_POST
@login_required
def start_player(
    request: HttpRequest,
    episode_id: int,
) -> HttpResponse:

    episode = get_episode_detail_or_404(request, episode_id)

    return render_player(
        request,
        episode,
        current_time=0 if episode.completed else (episode.current_time or 0),
    )


@require_POST
@login_required
def stop_player(request: HttpRequest) -> HttpResponse:
    return render_player(request)


@require_POST
@login_required
def play_next_episode(request: HttpRequest) -> HttpResponse:
    """Marks current episode complete, starts next episode in queue
    or closes player if queue empty."""

    next_item = (
        QueueItem.objects.filter(user=request.user)
        .select_related("episode", "episode__podcast")
        .order_by("position")
        .first()
    )

    return render_player(
        request,
        next_episode=next_item.episode if next_item else None,
        mark_completed=True,
    )


@require_POST
@ajax_login_required
def player_timeupdate(request: HttpRequest) -> HttpResponse:
    """Update current play time of episode"""

    if episode := request.player.get_episode():
        try:
            current_time = round(float(request.POST["current_time"]))
        except (KeyError, ValueError):
            return HttpResponseBadRequest("current_time missing or invalid")

        try:
            playback_rate = float(request.POST["playback_rate"])
        except (KeyError, ValueError):
            playback_rate = 1.0

        episode.log_activity(request.user, current_time)
        request.player.update(current_time=current_time, playback_rate=playback_rate)

        return HttpResponse(status=http.HTTPStatus.NO_CONTENT)
    return HttpResponseBadRequest("No player loaded")


def render_player_toggle(
    request: HttpRequest, episode: Episode, is_playing: bool
) -> str:

    return TurboStream(episode.get_player_toggle_id()).replace.render(
        render_component(request, "player_toggle", episode, is_playing)
    )


def render_player(
    request: HttpRequest,
    next_episode: Optional[Episode] = None,
    current_time: int = 0,
    mark_completed: bool = False,
) -> HttpResponse:

    streams: List[str] = []

    if current_episode := request.player.eject(mark_completed=mark_completed):
        streams.append(render_player_toggle(request, current_episode, False))

    if next_episode is None:
        response = TurboStreamResponse(
            streams
            + [
                TurboStream("player-controls").remove.render(),
            ]
        )
        response["X-Media-Player"] = json.dumps({"action": "stop"})
        return response

    # remove from queue
    QueueItem.objects.filter(user=request.user, episode=next_episode).delete()

    next_episode.log_activity(request.user, current_time=current_time)

    request.player.start(next_episode, current_time)

    response = TurboStreamResponse(
        streams
        + [
            render_player_toggle(request, next_episode, True),
            TurboStream("player")
            .update.template(
                "episodes/player/_controls.html",
                {"episode": next_episode},
            )
            .render(request=request),
            TurboStream("queue")
            .replace.template(
                "episodes/queue/_episode_list.html",
                {"queue_items": get_queue_items(request)},
            )
            .render(request=request),
        ]
    )
    response["X-Media-Player"] = json.dumps(
        {
            "action": "start",
            "currentTime": current_time,
            "mediaUrl": next_episode.media_url,
            "metadata": next_episode.get_media_metadata(),
        }
    )
    return response
