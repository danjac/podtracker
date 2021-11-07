from datetime import timedelta
from unittest import mock

import pytest

from django.contrib.admin.sites import AdminSite
from django.utils import timezone

from jcasts.podcasts.admin import (
    ActiveFilter,
    FollowedFilter,
    FrequencyFilter,
    PodcastAdmin,
    PromotedFilter,
    PubDateFilter,
    QueuedFilter,
    ResultFilter,
)
from jcasts.podcasts.factories import FollowFactory, PodcastFactory
from jcasts.podcasts.models import Podcast


@pytest.fixture(scope="class")
def admin():
    return PodcastAdmin(Podcast, AdminSite())


@pytest.fixture
def podcasts(db):
    return PodcastFactory.create_batch(3, active=True, promoted=False)


@pytest.fixture
def req(rf):
    req = rf.get("/")
    req._messages = mock.Mock()
    return req


class TestPodcastAdmin:
    def test_source(self, podcasts, admin):
        assert admin.source(podcasts[0]) == podcasts[0].get_domain()

    def test_get_search_results(self, podcasts, admin, req):
        podcast = PodcastFactory(title="Indie Hackers")
        qs, _ = admin.get_search_results(req, Podcast.objects.all(), "Indie Hackers")
        assert qs.count() == 1
        assert qs.first() == podcast

    def test_get_search_results_no_search_term(self, podcasts, admin, req):
        qs, _ = admin.get_search_results(req, Podcast.objects.all(), "")
        assert qs.count() == 3

    def test_get_ordering_no_search_term(self, admin, req):
        ordering = admin.get_ordering(req)
        assert ordering == ["scheduled", "-pub_date"]

    def test_get_ordering_search_term(self, admin, req):
        req.GET = {"q": "test"}
        ordering = admin.get_ordering(req)
        assert ordering == []

    def test_parse_podcast_feeds(self, podcast, admin, req, mock_parse_podcast_feed):
        admin.parse_podcast_feeds(req, Podcast.objects.all())
        mock_parse_podcast_feed.assert_called_with(podcast.id)

    def test_parse_podcast_feeds_inactive(
        self, podcast, admin, req, mock_parse_podcast_feed
    ):
        PodcastFactory(active=False)
        admin.parse_podcast_feeds(req, Podcast.objects.all())
        mock_parse_podcast_feed.assert_not_called()


class TestFrequencyFitler:
    def test_none(self, db, admin, req):
        PodcastFactory(frequency=timedelta(days=3))
        podcast = PodcastFactory(frequency=None)
        f = FrequencyFilter(req, {"frequency": "none"}, Podcast, admin)
        qs = f.queryset(req, Podcast.objects.all())
        assert qs.count() == 1
        assert podcast in qs

    def test_hourly(self, db, admin, req):
        PodcastFactory(frequency=timedelta(days=3))
        podcast = PodcastFactory(frequency=timedelta(hours=3))
        f = FrequencyFilter(req, {"frequency": "hourly"}, Podcast, admin)
        qs = f.queryset(req, Podcast.objects.all())
        assert qs.count() == 1
        assert podcast in qs

    def test_daily(self, db, admin, req):
        PodcastFactory(frequency=timedelta(days=3))
        PodcastFactory(frequency=timedelta(hours=3))
        podcast = PodcastFactory(frequency=timedelta(days=1))
        f = FrequencyFilter(req, {"frequency": "daily"}, Podcast, admin)
        qs = f.queryset(req, Podcast.objects.all())
        assert qs.count() == 1
        assert podcast in qs

    def test_weekly(self, db, admin, req):
        PodcastFactory(frequency=timedelta(days=1))
        PodcastFactory(frequency=timedelta(days=12))
        podcast = PodcastFactory(frequency=timedelta(days=6))
        f = FrequencyFilter(req, {"frequency": "weekly"}, Podcast, admin)
        qs = f.queryset(req, Podcast.objects.all())
        assert qs.count() == 1
        assert podcast in qs

    def test_fortnightly(self, db, admin, req):
        PodcastFactory(frequency=timedelta(days=1))
        PodcastFactory(frequency=timedelta(days=30))
        podcast = PodcastFactory(frequency=timedelta(days=12))
        f = FrequencyFilter(req, {"frequency": "fortnightly"}, Podcast, admin)
        qs = f.queryset(req, Podcast.objects.all())
        assert qs.count() == 1
        assert podcast in qs

    def test_monthly(self, db, admin, req):
        PodcastFactory(frequency=timedelta(days=20))
        podcast = PodcastFactory(frequency=timedelta(days=30))
        f = FrequencyFilter(req, {"frequency": "monthly"}, Podcast, admin)
        qs = f.queryset(req, Podcast.objects.all())
        assert qs.count() == 1
        assert podcast in qs

    def test_all(self, db, admin, req):
        PodcastFactory(frequency=None)
        PodcastFactory(frequency=timedelta(days=20))
        PodcastFactory(frequency=timedelta(days=30))
        f = FrequencyFilter(req, {}, Podcast, admin)
        qs = f.queryset(req, Podcast.objects.all())
        assert qs.count() == 3


class TestResultFilter:
    def test_result_filter_no_filter(self, podcasts, admin, req):
        PodcastFactory(result=Podcast.Result.NOT_MODIFIED)
        f = ResultFilter(req, {}, Podcast, admin)
        qs = f.queryset(req, Podcast.objects.all())
        assert qs.count() == 4

    def test_result_filter_none(self, podcasts, admin, req):
        podcast = PodcastFactory(result=Podcast.Result.NOT_MODIFIED)
        f = ResultFilter(req, {"result": "none"}, Podcast, admin)
        qs = f.queryset(req, Podcast.objects.all())
        assert qs.count() == 3
        assert podcast not in qs

    def test_result_filter_not_modified(self, podcasts, admin, req):
        podcast = PodcastFactory(result=Podcast.Result.NOT_MODIFIED)
        f = ResultFilter(req, {"result": Podcast.Result.NOT_MODIFIED}, Podcast, admin)
        qs = f.queryset(req, Podcast.objects.all())
        assert qs.count() == 1
        assert podcast in qs


class TestPubDateFilter:
    def test_pub_date_filter_none(self, podcasts, admin, req):
        PodcastFactory(pub_date=None)
        f = PubDateFilter(req, {}, Podcast, admin)
        qs = f.queryset(req, Podcast.objects.all())
        assert qs.count() == 4

    def test_pub_date_filter_false(self, podcasts, admin, req):
        no_pub_date = PodcastFactory(pub_date=None)
        f = PubDateFilter(req, {"pub_date": "no"}, Podcast, admin)
        qs = f.queryset(req, Podcast.objects.all())
        assert qs.count() == 1
        assert qs.first() == no_pub_date

    def test_pub_date_filter_true(self, podcasts, admin, req):
        no_pub_date = PodcastFactory(pub_date=None)
        f = PubDateFilter(req, {"pub_date": "yes"}, Podcast, admin)
        qs = f.queryset(req, Podcast.objects.all())
        assert qs.count() == 3
        assert no_pub_date not in qs

    def test_pub_date_stale(self, settings, podcasts, admin, req):
        now = timezone.now()
        settings.FRESHNESS_THRESHOLD = timedelta(days=90)
        PodcastFactory(pub_date=None)
        PodcastFactory(pub_date=now - timedelta(days=9))
        not_fresh = PodcastFactory(pub_date=now - timedelta(days=99))

        f = PubDateFilter(req, {"pub_date": "stale"}, Podcast, admin)
        qs = f.queryset(req, Podcast.objects.all())
        assert qs.count() == 1
        assert not_fresh in qs

    def test_pub_date_fresh(self, settings, podcasts, admin, req):
        now = timezone.now()
        settings.FRESHNESS_THRESHOLD = timedelta(days=90)
        no_pub_date = PodcastFactory(pub_date=None)
        not_fresh = PodcastFactory(pub_date=now - timedelta(days=99))

        f = PubDateFilter(req, {"pub_date": "fresh"}, Podcast, admin)
        qs = f.queryset(req, Podcast.objects.all())
        assert qs.count() == 4
        assert no_pub_date in qs
        assert not_fresh not in qs


class TestActiveFilter:
    def test_active_filter_none(self, podcasts, admin, req):
        PodcastFactory(active=False)
        f = ActiveFilter(req, {}, Podcast, admin)
        qs = f.queryset(req, Podcast.objects.all())
        assert qs.count() == 4

    def test_active_filter_false(self, podcasts, admin, req):
        inactive = PodcastFactory(active=False)
        f = ActiveFilter(req, {"active": "no"}, Podcast, admin)
        qs = f.queryset(req, Podcast.objects.all())
        assert qs.count() == 1
        assert qs.first() == inactive

    def test_active_filter_true(self, podcasts, admin, req):
        inactive = PodcastFactory(active=False)
        f = ActiveFilter(req, {"active": "yes"}, Podcast, admin)
        qs = f.queryset(req, Podcast.objects.all())
        assert qs.count() == 3
        assert inactive not in qs


class TestPromotedFilter:
    def test_promoted_filter_none(self, podcasts, admin, req):
        PodcastFactory(promoted=False)
        f = PromotedFilter(req, {}, Podcast, admin)
        qs = f.queryset(req, Podcast.objects.all())
        assert qs.count() == 4

    def test_promoted_filter_true(self, podcasts, admin, req):
        promoted = PodcastFactory(promoted=True)
        f = PromotedFilter(req, {"promoted": "yes"}, Podcast, admin)
        qs = f.queryset(req, Podcast.objects.all())
        assert qs.count() == 1
        assert qs.first() == promoted


class TestQueuedFilter:
    def test_queued_filter_none(self, podcasts, admin, req):
        PodcastFactory(queued=timezone.now())
        f = QueuedFilter(req, {}, Podcast, admin)
        qs = f.queryset(req, Podcast.objects.all())
        assert qs.count() == 4

    def test_queued_filter_true(self, podcasts, admin, req):
        queued = PodcastFactory(queued=timezone.now())
        f = QueuedFilter(req, {"queued": "yes"}, Podcast, admin)
        qs = f.queryset(req, Podcast.objects.all())
        assert qs.count() == 1
        assert qs.first() == queued


class TestFollowedFilter:
    def test_followed_filter_none(self, podcasts, admin, req):
        FollowFactory()
        f = FollowedFilter(req, {}, Podcast, admin)
        qs = f.queryset(req, Podcast.objects.all())
        assert qs.count() == 4

    def test_promoted_filter_true(self, podcasts, admin, req):
        followed = FollowFactory().podcast
        f = FollowedFilter(req, {"followed": "yes"}, Podcast, admin)
        qs = f.queryset(req, Podcast.objects.all())
        assert qs.count() == 1
        assert qs.first() == followed
