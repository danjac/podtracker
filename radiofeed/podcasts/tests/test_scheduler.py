from datetime import timedelta

from django.utils import timezone

from radiofeed.podcasts import scheduler
from radiofeed.podcasts.factories import PodcastFactory, SubscriptionFactory


class TestSchedulePodcastsForUpdate:
    def test_parsed_is_null(self, db):
        PodcastFactory(parsed=None)
        assert scheduler.schedule_podcasts_for_update().exists()

    def test_pub_date_is_null(self, db):
        PodcastFactory(parsed=timezone.now(), pub_date=None)
        assert scheduler.schedule_podcasts_for_update().exists()

    def test_inactive(self, db):
        PodcastFactory(parsed=None, active=False)
        assert not scheduler.schedule_podcasts_for_update().exists()

    def test_scheduled(self, db):
        now = timezone.now()
        PodcastFactory(
            parsed=now - timedelta(hours=1),
            pub_date=now - timedelta(days=7),
            refresh_interval=timedelta(days=7),
        )
        assert scheduler.schedule_podcasts_for_update().exists()

    def test_not_scheduled(self, db):
        now = timezone.now()

        PodcastFactory(
            parsed=now - timedelta(hours=1),
            pub_date=now - timedelta(days=4),
            refresh_interval=timedelta(days=7),
        )

        assert not scheduler.schedule_podcasts_for_update().exists()

    def test_scheduled_older_than_two_weeks(self, db):
        now = timezone.now()
        PodcastFactory(
            parsed=now - timedelta(hours=14),
            pub_date=now - timedelta(days=15),
            refresh_interval=timedelta(days=14),
        )
        assert scheduler.schedule_podcasts_for_update().exists()

    def test_not_scheduled_older_than_two_weeks(self, db):
        now = timezone.now()
        PodcastFactory(
            parsed=now - timedelta(hours=7),
            pub_date=now - timedelta(days=15),
            refresh_interval=timedelta(days=14),
        )
        assert scheduler.schedule_podcasts_for_update().exists()

    def test_promoted_scheduled(self, db):
        PodcastFactory(parsed=timezone.now() - timedelta(hours=1), promoted=True)
        assert scheduler.schedule_podcasts_for_update().exists()

    def test_promoted_not_scheduled(self, db):
        PodcastFactory(parsed=timezone.now() - timedelta(minutes=30), promoted=True)
        assert not scheduler.schedule_podcasts_for_update().exists()

    def test_subscribed_scheduled(self, db):
        SubscriptionFactory(podcast__parsed=timezone.now() - timedelta(hours=1))
        assert scheduler.schedule_podcasts_for_update().exists()

    def test_subscribed_not_scheduled(self, db):
        SubscriptionFactory(podcast__parsed=timezone.now() - timedelta(minutes=30))
        assert not scheduler.schedule_podcasts_for_update().exists()


class TestRecalculateRefreshInterval:
    def test_recalculate(self):
        assert scheduler.recalculate_refresh_interval(timedelta(hours=1)) == timedelta(
            hours=1, minutes=6
        )

    def test_recalculate_over_max(self):
        assert scheduler.recalculate_refresh_interval(timedelta(days=14)) == timedelta(
            days=14
        )


class TestCalculateRefreshInterval:
    def test_no_dates(self):
        assert scheduler.calculate_refresh_interval([]) == timedelta(hours=1)

    def test_just_one_date(self):

        assert scheduler.calculate_refresh_interval([timezone.now()]) == timedelta(
            hours=1
        )

    def test_two_dates(self):
        dt = timezone.now()

        pub_dates = [
            dt,
            dt - timedelta(days=3),
        ]

        assert scheduler.calculate_refresh_interval(pub_dates) == timedelta(days=3)

    def test_sufficent_dates(self):

        dt = timezone.now()

        pub_dates = [
            dt,
            dt - timedelta(days=3),
            dt - timedelta(days=6),
        ]

        assert scheduler.calculate_refresh_interval(pub_dates) == timedelta(days=3)

    def test_latest_before_now(self):

        dt = timezone.now()

        pub_dates = [
            dt - timedelta(days=30),
            dt - timedelta(days=36),
            dt - timedelta(days=40),
        ]

        assert scheduler.calculate_refresh_interval(pub_dates).days == 14

    def test_no_diffs(self):

        pub_dates = [timezone.now() - timedelta(days=3)] * 10

        assert scheduler.calculate_refresh_interval(pub_dates).days == 3
