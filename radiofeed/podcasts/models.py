from datetime import timedelta

from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField, TrigramSimilarity
from django.core.validators import MinLengthValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_str
from django.utils.functional import cached_property
from django.utils.text import slugify
from model_utils.models import TimeStampedModel

from radiofeed.common.db import FastCountMixin, SearchMixin
from radiofeed.common.utils.html import strip_html


class CategoryQuerySet(models.QuerySet):
    """Custom QuerySet for Category model."""

    def search(self, search_term, base_similarity=0.2):
        """Does a trigram similarity search for podcasts.

        Args:
            search_term (str)
            base_similarity (float): base similarity for trigram search

        Returns:
            QuerySet
        """
        return self.annotate(
            similarity=TrigramSimilarity("name", force_str(search_term))
        ).filter(similarity__gte=base_similarity)


class Category(models.Model):
    """iTunes category."""

    name = models.CharField(max_length=100, unique=True)
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="children",
    )

    objects = CategoryQuerySet.as_manager()

    class Meta:
        verbose_name_plural = "categories"
        ordering = ("name",)

    def __str__(self):
        """Returns category name.

        Returns:
            str
        """
        return self.name

    @property
    def slug(self):
        """Returns slugified name.

        Returns:
            str
        """
        return slugify(self.name, allow_unicode=False)

    def get_absolute_url(self):
        """Absolute URL to a category.

        Returns:
            str
        """
        return reverse("podcasts:category_detail", args=[self.pk, self.slug])


class PodcastQuerySet(FastCountMixin, SearchMixin, models.QuerySet):
    """Custom QuerySet of Podcast model."""

    def scheduled(self):
        """Returns podcasts scheduled for update.

         Scheduling algorithm:

             1. check once every n hours, where "n" is the number
                 of days since the podcast was last updated (i.e. last pub date)
             2. if podcast was last updated within 24 hours, check once an hour.
             3. if podcast was last updated > 24 days, check every 24 hours.
             4. if podcast has not been checked yet (i.e. just added to database), check immediately.

         Only *active* podcasts should be included.

        Returns:
             QuerySet: scheduled podcasts
        """
        now = timezone.now()

        return Podcast.objects.annotate(
            days_since_last_pub_date=models.functions.ExtractDay(
                now - models.F("pub_date")
            ),
        ).filter(
            models.Q(
                parsed__isnull=True,
            )
            | models.Q(
                pub_date__isnull=True,
            )
            | models.Q(
                days_since_last_pub_date__lt=1,
                parsed__lt=now - timedelta(hours=1),
            )
            | models.Q(
                days_since_last_pub_date__gt=24,
                parsed__lt=now - timedelta(hours=24),
            )
            | models.Q(
                days_since_last_pub_date__range=(1, 24),
                parsed__lt=now
                - timedelta(hours=1) * models.F("days_since_last_pub_date"),
            ),
            active=True,
        )


PodcastManager = models.Manager.from_queryset(PodcastQuerySet)


class Podcast(models.Model):
    """Podcast channel or feed."""

    class ParseResult(models.TextChoices):
        """Result of feed parser process."""

        SUCCESS = "success", "Success"
        COMPLETE = "complete", "Complete"
        NOT_MODIFIED = "not_modified", "Not Modified"
        HTTP_ERROR = "http_error", "HTTP Error"
        RSS_PARSER_ERROR = "rss_parser_error", "RSS Parser Error"
        DUPLICATE_FEED = "duplicate_feed", "Duplicate Feed"

    rss = models.URLField(unique=True, max_length=500)
    active = models.BooleanField(default=True)

    etag = models.TextField(blank=True)
    title = models.TextField()

    # latest episode pub date from RSS feed
    pub_date = models.DateTimeField(null=True, blank=True)

    # last parse time (success or fail)
    parsed = models.DateTimeField(null=True, blank=True)

    # Last-Modified header from RSS feed
    modified = models.DateTimeField(null=True, blank=True)

    # hash of last polled content
    content_hash = models.CharField(max_length=64, null=True, blank=True)

    http_status = models.SmallIntegerField(null=True, blank=True)

    parse_result = models.CharField(
        max_length=30,
        null=True,
        blank=True,
        choices=ParseResult.choices,
    )

    cover_url = models.URLField(max_length=2083, null=True, blank=True)

    funding_url = models.URLField(max_length=2083, null=True, blank=True)
    funding_text = models.TextField(blank=True)

    language = models.CharField(
        max_length=2, default="en", validators=[MinLengthValidator(2)]
    )
    description = models.TextField(blank=True)
    link = models.URLField(max_length=2083, null=True, blank=True)
    keywords = models.TextField(blank=True)
    extracted_text = models.TextField(blank=True)
    owner = models.TextField(blank=True)

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    explicit = models.BooleanField(default=False)
    promoted = models.BooleanField(default=False)

    categories = models.ManyToManyField("podcasts.Category", blank=True)

    # received recommendation email
    recipients = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="recommended_podcasts",
    )

    search_vector = SearchVectorField(null=True, editable=False)

    objects = PodcastManager()

    class Meta:
        indexes = [
            models.Index(fields=["-pub_date"]),
            models.Index(fields=["pub_date"]),
            models.Index(fields=["promoted"]),
            GinIndex(fields=["search_vector"]),
        ]

    def __str__(self):
        """Returns podcast title or RSS if missing.

        Returns:
            str
        """
        return self.title or self.rss

    def get_absolute_url(self):
        """Default absolute URL of podcast.

        Returns:
            str
        """
        return self.get_detail_url()

    def get_detail_url(self):
        """Absolute URL of podcast detail page.

        Returns:
            str
        """
        return reverse("podcasts:podcast_detail", args=[self.pk, self.slug])

    def get_episodes_url(self):
        """Absolute URL of podcast episode list page.

        Returns:
            str
        """
        return reverse("podcasts:podcast_episodes", args=[self.pk, self.slug])

    def get_similar_url(self):
        """Absolute URL of podcast similar recommendations page.

        Returns:
            str
        """
        return reverse("podcasts:podcast_similar", args=[self.pk, self.slug])

    def get_latest_episode_url(self):
        """Absolute URL to latest episode redirect.

        Returns:
            str
        """
        return reverse("podcasts:latest_episode", args=[self.pk, self.slug])

    @cached_property
    def cleaned_title(self):
        """Strips HTML from title field.

        Returns:
            str
        """
        return strip_html(self.title)

    @cached_property
    def cleaned_description(self):
        """Strips HTML from description field.

        Returns:
            str
        """
        return strip_html(self.description)

    @cached_property
    def slug(self):
        """Returns slugified title.

        Returns:
            str
        """
        return slugify(self.title, allow_unicode=False) or "no-title"

    def is_subscribed(self, user):
        """Check if user is subscribed to this podcast.

        Args:
            user (User | AnonymousUser)

        Returns:
            bool
        """
        if user.is_anonymous:
            return False
        return Subscription.objects.filter(podcast=self, user=user).exists()

    def get_subscribe_target(self):
        """Returns HTMX subscribe action target.

        Returns:
            str
        """
        return f"subscribe-actions-{self.id}"


class Subscription(TimeStampedModel):
    """Subscribed podcast belonging to a user's collection."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    podcast = models.ForeignKey("podcasts.Podcast", on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                name="unique_%(app_label)s_%(class)s_user_podcast",
                fields=["user", "podcast"],
            )
        ]
        indexes = [models.Index(fields=["-created"])]


class RecommendationQuerySet(models.QuerySet):
    """Custom QuerySet for Recommendation model."""

    def bulk_delete(self):
        """More efficient quick delete.

        Returns:
            int: number of rows deleted
        """
        return self._raw_delete(self.db)


RecommendationManager = models.Manager.from_queryset(RecommendationQuerySet)


class Recommendation(models.Model):
    """Recommendation based on similarity between two podcasts."""

    podcast = models.ForeignKey(
        "podcasts.Podcast",
        related_name="+",
        on_delete=models.CASCADE,
    )

    recommended = models.ForeignKey(
        "podcasts.Podcast",
        related_name="+",
        on_delete=models.CASCADE,
    )

    frequency = models.PositiveIntegerField(default=0)

    similarity = models.DecimalField(
        decimal_places=10, max_digits=100, null=True, blank=True
    )

    objects = RecommendationManager()

    class Meta:
        indexes = [
            models.Index(fields=["podcast"]),
            models.Index(fields=["recommended"]),
            models.Index(fields=["-similarity", "-frequency"]),
        ]
        constraints = [
            models.UniqueConstraint(
                name="unique_%(app_label)s_%(class)s",
                fields=["podcast", "recommended"],
            ),
        ]
