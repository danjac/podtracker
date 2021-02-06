from typing import Dict, Optional, Tuple

from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVectorField
from django.db import models
from django.template.defaultfilters import filesizeformat
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_str
from django.utils.text import slugify

from model_utils.models import TimeStampedModel
from sorl.thumbnail import get_thumbnail

from radiofeed.podcasts.models import Podcast
from radiofeed.typing import AnyUser


class EpisodeQuerySet(models.QuerySet):
    def with_current_time(self, user: AnyUser) -> models.QuerySet:

        """Adds `completed`, `current_time` and `listened` annotations."""

        if user.is_anonymous:
            return self.annotate(
                completed=models.Value(False, output_field=models.BooleanField()),
                current_time=models.Value(0, output_field=models.IntegerField()),
                listened=models.Value(None, output_field=models.DateTimeField()),
            )

        logs = AudioLog.objects.filter(user=user, episode=models.OuterRef("pk"))

        return self.annotate(
            completed=models.Subquery(logs.values("completed")),
            current_time=models.Subquery(logs.values("current_time")),
            listened=models.Subquery(logs.values("updated")),
        )

    def search(self, search_term: str) -> models.QuerySet:
        if not search_term:
            return self.none()

        query = SearchQuery(force_str(search_term), search_type="websearch")
        return self.annotate(
            rank=SearchRank(models.F("search_vector"), query=query)
        ).filter(search_vector=query)


EpisodeManager: models.Manager = models.Manager.from_queryset(EpisodeQuerySet)


class Episode(models.Model):

    podcast = models.ForeignKey(Podcast, on_delete=models.CASCADE)

    guid = models.TextField()

    pub_date = models.DateTimeField()
    link = models.URLField(null=True, blank=True, max_length=500)

    title = models.TextField(blank=True)
    description = models.TextField(blank=True)
    keywords = models.TextField(blank=True)

    media_url = models.URLField(max_length=500)
    media_type = models.CharField(max_length=60)
    length = models.IntegerField(null=True, blank=True)

    duration = models.CharField(max_length=30, blank=True)
    explicit = models.BooleanField(default=False)

    search_vector = SearchVectorField(null=True, editable=False)

    objects: models.Manager = EpisodeManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["podcast", "guid"], name="unique_episode")
        ]
        indexes = [
            models.Index(fields=["podcast"]),
            models.Index(fields=["guid"]),
            models.Index(fields=["-pub_date"]),
            models.Index(fields=["pub_date"]),
            GinIndex(fields=["search_vector"]),
        ]

    def __str__(self) -> str:
        return self.title or self.guid

    def get_absolute_url(self) -> str:
        return reverse("episodes:episode_detail", args=[self.id, self.slug])

    @property
    def slug(self) -> str:
        return slugify(self.title, allow_unicode=False) or "episode"

    def get_file_size(self) -> Optional[str]:
        return filesizeformat(self.length) if self.length else None

    def get_bookmark_toggle_id(self) -> str:
        # https://github.com/hotwired/turbo/issues/86
        return f"episode-bookmark-{self.id}"

    def get_duration_in_seconds(self) -> int:
        """Returns duration string in h:m:s or h:m to seconds"""
        if not self.duration:
            return 0
        hours, minutes, seconds = 0, 0, 0
        parts = self.duration.split(":")
        num_parts = len(parts)

        try:
            if num_parts == 1:
                seconds = int(parts[0])
            elif num_parts == 2:
                [minutes, seconds] = [int(p) for p in parts]
            elif num_parts == 3:
                [hours, minutes, seconds] = [int(p) for p in parts]
            else:
                return 0
        except ValueError:
            return 0

        try:
            return (int(hours) * 3600) + (int(minutes) * 60) + int(seconds)
        except ValueError:
            return 0

    def log_activity(
        self,
        user: settings.AUTH_USER_MODEL,
        current_time=0,
        completed: bool = False,
    ) -> Tuple[Optional["AudioLog"], bool]:
        # Updates audio log with current time
        now = timezone.now()
        return AudioLog.objects.update_or_create(
            episode=self,
            user=user,
            defaults={
                "current_time": current_time,
                "updated": now,
                "completed": now if completed else None,
            },
        )

    def get_next_episode(self) -> Optional["Episode"]:
        try:
            return self.get_next_by_pub_date(podcast=self.podcast)
        except self.DoesNotExist:
            return None

    def get_previous_episode(self) -> Optional["Episode"]:
        try:
            return self.get_previous_by_pub_date(podcast=self.podcast)
        except self.DoesNotExist:
            return None

    def get_media_metadata(self) -> Dict:
        # https://developers.google.com/web/updates/2017/02/media-session
        data: Dict = {
            "title": self.title,
            "album": self.podcast.title,
            "artist": self.podcast.authors,
        }

        if self.podcast.cover_image:
            thumbnail = get_thumbnail(
                self.podcast.cover_image, "200", format="PNG", crop="center"
            )

            if thumbnail:
                data |= {
                    "artwork": [
                        {
                            "src": thumbnail.url,
                            "sizes": f"{size}x{size}",
                            "type": "image/png",
                        }
                        for size in [96, 128, 192, 256, 384, 512]
                    ]
                }

        return data


class BookmarkQuerySet(models.QuerySet):
    def search(self, search_term: str) -> models.QuerySet:
        if not search_term:
            return self.none()

        query = SearchQuery(force_str(search_term), search_type="websearch")
        return self.annotate(
            episode_rank=SearchRank(models.F("episode__search_vector"), query=query),
            podcast_rank=SearchRank(
                models.F("episode__podcast__search_vector"), query=query
            ),
            rank=models.F("episode_rank") + models.F("podcast_rank"),
        ).filter(
            models.Q(episode__search_vector=query)
            | models.Q(episode__podcast__search_vector=query)
        )


BookmarkManager: models.Manager = models.Manager.from_queryset(BookmarkQuerySet)


class Bookmark(TimeStampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    episode = models.ForeignKey(Episode, on_delete=models.CASCADE)

    objects = BookmarkManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(name="uniq_bookmark", fields=["user", "episode"])
        ]
        indexes = [
            models.Index(fields=["-created"]),
        ]

    def get_remove_url(self) -> str:
        return reverse("episodes:remove_bookmark", args=[self.episode_id])


class AudioLogQuerySet(models.QuerySet):
    def search(self, search_term: str) -> models.QuerySet:
        if not search_term:
            return self.none()

        query = SearchQuery(force_str(search_term), search_type="websearch")
        return self.annotate(
            episode_rank=SearchRank(models.F("episode__search_vector"), query=query),
            podcast_rank=SearchRank(
                models.F("episode__podcast__search_vector"), query=query
            ),
            rank=models.F("episode_rank") + models.F("podcast_rank"),
        ).filter(
            models.Q(episode__search_vector=query)
            | models.Q(episode__podcast__search_vector=query)
        )


AudioLogManager: models.Manager = models.Manager.from_queryset(AudioLogQuerySet)


class AudioLog(TimeStampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    episode = models.ForeignKey(Episode, on_delete=models.CASCADE)
    updated = models.DateTimeField()
    completed = models.DateTimeField(null=True, blank=True)
    current_time = models.IntegerField(default=0)

    objects = AudioLogManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(name="uniq_audio_log", fields=["user", "episode"])
        ]
        indexes = [
            models.Index(fields=["-updated"]),
        ]

    def get_remove_url(self) -> str:
        return reverse("episodes:remove_history", args=[self.episode_id])


class QueueItem(TimeStampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    episode = models.ForeignKey(Episode, on_delete=models.CASCADE)
    position = models.IntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(name="uniq_queue_item", fields=["user", "episode"]),
            models.UniqueConstraint(
                name="uniq_queue_item_position", fields=["user", "position"]
            ),
        ]
        indexes = [
            models.Index(fields=["position"]),
        ]
