from __future__ import annotations

from django.contrib import admin, messages
from django.db.models import Count, Exists, OuterRef, Q, QuerySet
from django.http import HttpRequest
from django.template.defaultfilters import timeuntil
from django.utils import timezone
from django_object_actions import DjangoObjectActions

from radiofeed.fast_count import FastCountAdminMixin
from radiofeed.feedparser import scheduler
from radiofeed.podcasts import websub
from radiofeed.podcasts.models import Category, Podcast, Subscription


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    """Admin for podcast categories."""

    ordering = ("name",)
    list_display = (
        "name",
        "parent",
        "num_podcasts",
    )
    search_fields = ("name",)

    def get_queryset(self, request: HttpRequest) -> QuerySet[Category]:
        """Returns queryset with number of podcasts."""
        return super().get_queryset(request).annotate(num_podcasts=Count("podcasts"))

    def num_podcasts(self, obj: Category) -> int:
        """Returns number of podcasts in this category."""
        return obj.num_podcasts or 0


class ActiveFilter(admin.SimpleListFilter):
    """Filters active/inactive podcasts."""

    title = "Active"
    parameter_name = "active"

    def lookups(
        self, request: HttpRequest, model_admin: admin.ModelAdmin[Podcast]
    ) -> tuple[tuple[str, str], ...]:
        """Returns lookup values/labels."""
        return (
            ("yes", "Active"),
            ("no", "Inactive"),
        )

    def queryset(self, request: HttpRequest, queryset: QuerySet[Podcast]):
        """Returns filtered queryset."""
        match self.value():
            case "yes":
                return queryset.filter(active=True)
            case "no":
                return queryset.filter(active=False)
            case _:
                return queryset


class ParserErrorFilter(admin.SimpleListFilter):
    """Filters based on parser error."""

    title = "Parser Error"
    parameter_name = "parser_error"

    def lookups(
        self, request: HttpRequest, model_admin: admin.ModelAdmin[Podcast]
    ) -> tuple[tuple[str, str], ...]:
        """Returns lookup values/labels."""
        return Podcast.ParserError.choices

    def queryset(self, request: HttpRequest, queryset: QuerySet[Podcast]):
        """Returns filtered queryset."""

        match self.value():
            case value if value in Podcast.ParserError:  # type: ignore
                return queryset.filter(parser_error=value)
            case _:
                return queryset


class PubDateFilter(admin.SimpleListFilter):
    """Filters podcasts based on last pub date."""

    title = "Pub Date"
    parameter_name = "pub_date"

    def lookups(
        self, request: HttpRequest, model_admin: admin.ModelAdmin[Podcast]
    ) -> tuple[tuple[str, str], ...]:
        """Returns lookup values/labels."""
        return (
            ("yes", "With pub date"),
            ("no", "With no pub date"),
        )

    def queryset(
        self, request: HttpRequest, queryset: QuerySet[Podcast]
    ) -> QuerySet[Podcast]:
        """Returns filtered queryset."""
        match self.value():
            case "yes":
                return queryset.filter(pub_date__isnull=False)
            case "no":
                return queryset.filter(pub_date__isnull=True)
            case _:
                return queryset


class PromotedFilter(admin.SimpleListFilter):
    """Filters podcasts promoted status."""

    title = "Promoted"
    parameter_name = "promoted"

    def lookups(
        self, request: HttpRequest, model_admin: admin.ModelAdmin[Podcast]
    ) -> tuple[tuple[str, str], ...]:
        """Returns lookup values/labels."""
        return (("yes", "Promoted"),)

    def queryset(
        self, request: HttpRequest, queryset: QuerySet[Podcast]
    ) -> QuerySet[Podcast]:
        """Returns filtered queryset."""
        return queryset.filter(promoted=True) if self.value() == "yes" else queryset


class SubscribedFilter(admin.SimpleListFilter):
    """Filters podcasts based on subscription status."""

    title = "Subscribed"
    parameter_name = "subscribed"

    def lookups(
        self, request: HttpRequest, model_admin: admin.ModelAdmin[Podcast]
    ) -> tuple[tuple[str, str], ...]:
        """Returns lookup values/labels."""
        return (("yes", "Subscribed"),)

    def queryset(
        self, request: HttpRequest, queryset: QuerySet[Podcast]
    ) -> QuerySet[Podcast]:
        """Returns filtered queryset."""

        if self.value() == "yes":
            return queryset.annotate(
                has_subscribers=Exists(
                    Subscription.objects.filter(podcast=OuterRef("pk"))
                )
            ).filter(has_subscribers=True)

        return queryset


class WebsubFilter(admin.SimpleListFilter):
    """Filters podcasts based on websub status."""

    title = "Websub"
    parameter_name = "websub"

    def lookups(
        self, request: HttpRequest, model_admin: admin.ModelAdmin[Podcast]
    ) -> tuple[tuple[str, str], ...]:
        """Returns lookup values/labels."""
        return (
            ("yes", "Websub"),
            ("no", "No Websub"),
            ("pending", "Pending"),
            ("subscribed", "Subscribed"),
            ("failed", "Failed"),
        )

    def queryset(
        self, request: HttpRequest, queryset: QuerySet[Podcast]
    ) -> QuerySet[Podcast]:
        """Returns filtered queryset."""
        now = timezone.now()

        match self.value():
            case "yes":
                return queryset.filter(websub_hub__isnull=False)
            case "no":
                return queryset.filter(websub_hub__isnull=True)
            case "pending":
                return queryset.filter(
                    Q(websub_mode="")
                    | Q(
                        websub_mode="subscribe",
                        websub_expires__lt=timezone.now(),
                    ),
                    websub_hub__isnull=False,
                    num_websub_retries__lt=websub.MAX_NUM_RETRIES,
                )

            case "subscribed":
                return queryset.filter(
                    websub_hub__isnull=False,
                    websub_mode="subscribe",
                    websub_expires__gte=now,
                )
            case "failed":
                return queryset.filter(
                    websub_hub__isnull=False,
                    num_websub_retries__gte=websub.MAX_NUM_RETRIES,
                )

            case _:
                return queryset


@admin.register(Podcast)
class PodcastAdmin(DjangoObjectActions, FastCountAdminMixin, admin.ModelAdmin):
    """Podcast model admin."""

    date_hierarchy = "pub_date"

    list_filter = (
        ActiveFilter,
        ParserErrorFilter,
        PubDateFilter,
        PromotedFilter,
        SubscribedFilter,
        WebsubFilter,
    )

    list_display = (
        "__str__",
        "active",
        "promoted",
        "pub_date",
        "parsed",
    )

    list_editable = (
        "active",
        "promoted",
    )

    search_fields = ("title", "rss")

    raw_id_fields = ("recipients",)

    readonly_fields = (
        "pub_date",
        "parsed",
        "frequency",
        "next_scheduled_update",
        "parser_error",
        "modified",
        "etag",
        "content_hash",
        "websub_hub",
        "websub_mode",
        "websub_secret",
        "websub_expires",
        "num_websub_retries",
    )

    actions = ("parse_podcast_feeds",)

    change_actions = ("parse_podcast_feed",)

    def parse_podcast_feed(self, request: HttpRequest, obj: Podcast) -> None:
        """Runs feed parser on single podcast."""

        if obj.active:
            # queue podast for immediate update
            obj.immediate = True
            obj.save()

            self.message_user(
                request,
                "Podcast feed has been queued for update",
                level=messages.SUCCESS,
            )
        else:
            self.message_user(
                request,
                "Podcast feed cannot be scheduled because it is inactive",
                level=messages.ERROR,
            )

    @admin.display(description="Estimated Next Update")
    def next_scheduled_update(self, obj: Podcast):
        """Return estimated next update time."""
        return timeuntil(scheduler.next_scheduled_update(obj))

    def get_ordering(self, request: HttpRequest) -> list[str]:
        """Returns default ordering."""
        return [] if request.GET.get("q") else ["-parsed", "-pub_date"]
