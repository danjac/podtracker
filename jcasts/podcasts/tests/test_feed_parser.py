import http
import pathlib

from datetime import timedelta

import pytest
import requests

from django.utils import timezone

from jcasts.episodes.factories import EpisodeFactory
from jcasts.episodes.models import Episode
from jcasts.podcasts.date_parser import parse_date
from jcasts.podcasts.factories import CategoryFactory, PodcastFactory
from jcasts.podcasts.feed_parser import (
    clear_podcast_feed_queue,
    get_categories_dict,
    get_feed_headers,
    parse_podcast_feed,
    reschedule,
    reschedule_podcast_feeds,
    schedule_podcast_feeds,
)
from jcasts.podcasts.models import Podcast


class MockResponse:
    def __init__(
        self,
        url="",
        status=http.HTTPStatus.OK,
        content=b"",
        headers=None,
        links=None,
    ):
        self.url = url
        self.content = content
        self.headers = headers or {}
        self.links = links or {}
        self.status_code = status

    def raise_for_status(self):
        ...


class BadMockResponse(MockResponse):
    def raise_for_status(self):
        raise requests.HTTPError()


class TestFeedHeaders:
    def test_has_etag(self):
        podcast = Podcast(etag="abc123")
        headers = get_feed_headers(podcast)
        assert headers["If-None-Match"] == f'"{podcast.etag}"'

    def test_is_modified(self):
        podcast = Podcast(modified=timezone.now())
        headers = get_feed_headers(podcast)
        assert headers["If-Modified-Since"]


class TestClearPodcastFeedQueue:
    def test_clear_podcast_feed_queue(self, db, mocker):
        mock_queue = mocker.patch("jcasts.podcasts.feed_parser.get_queue")
        PodcastFactory(queued=timezone.now())
        clear_podcast_feed_queue()
        assert Podcast.objects.filter(queued__isnull=False).count() == 0
        mock_queue.assert_called_with("feeds")


class TestReschedulePodcastFeeds:
    def test_reschedule_podcast_feeds(self, db):
        PodcastFactory(active=True, scheduled=None)
        reschedule_podcast_feeds()
        assert Podcast.objects.count() == 1


class TestSchedulePodcastFeeds:
    @pytest.mark.parametrize(
        "active,scheduled,queued,expected",
        [
            (True, timedelta(days=-1), False, 1),
            (False, timedelta(days=-1), False, 0),
            (True, timedelta(days=1), False, 0),
            (True, timedelta(days=-1), True, 0),
        ],
    )
    def test_schedule_podcast_feeds(
        self, db, mocker, active, scheduled, queued, expected
    ):
        now = timezone.now()
        PodcastFactory(
            active=active,
            scheduled=now + scheduled if scheduled else None,
            queued=now if queued else None,
        )
        mock_parse = mocker.patch(
            "jcasts.podcasts.feed_parser.parse_podcast_feed.delay"
        )
        schedule_podcast_feeds()
        assert mock_parse.call_count == expected
        assert Podcast.objects.filter(queued__isnull=False).count() == expected


class TestParsePodcastFeed:

    mock_file = "rss_mock.xml"
    mock_http_get = "requests.get"
    rss = "https://mysteriousuniverse.org/feed/podcast/"
    redirect_rss = "https://example.com/test.xml"
    updated = "Wed, 01 Jul 2020 15:25:26 +0000"

    @pytest.fixture
    def new_podcast(self, db):
        return PodcastFactory(cover_url=None, pub_date=None)

    @pytest.fixture
    def categories(self, db):
        yield [
            CategoryFactory(name=name)
            for name in (
                "Philosophy",
                "Science",
                "Social Sciences",
                "Society & Culture",
                "Spirituality",
                "Religion & Spirituality",
            )
        ]

        get_categories_dict.cache_clear()

    def get_rss_content(self, filename=""):
        return open(
            pathlib.Path(__file__).parent / "mocks" / (filename or self.mock_file), "rb"
        ).read()

    def test_parse_no_podcasts(self, mocker, new_podcast, categories):
        mocker.patch(
            self.mock_http_get,
            return_value=MockResponse(
                url=new_podcast.rss,
                content=self.get_rss_content("rss_no_podcasts_mock.xml"),
            ),
        )

        result = parse_podcast_feed(new_podcast.rss)
        assert not result
        with pytest.raises(ValueError):
            result.raise_exception()

        new_podcast.refresh_from_db()
        assert not new_podcast.active
        assert new_podcast.parsed
        assert new_podcast.queued is None

    def test_parse_empty_feed(self, mocker, new_podcast, categories):

        mocker.patch(
            self.mock_http_get,
            return_value=MockResponse(
                url=new_podcast.rss,
                content=self.get_rss_content("rss_empty_mock.xml"),
            ),
        )

        result = parse_podcast_feed(new_podcast.rss)
        assert not result
        with pytest.raises(ValueError):
            result.raise_exception()

        new_podcast.refresh_from_db()
        assert not new_podcast.active
        assert new_podcast.parsed
        assert new_podcast.queued is None

    def test_parse_podcast_feed_podcast_not_found(self, db):
        result = parse_podcast_feed("https://example.com/rss.xml")
        assert result.success is False

        with pytest.raises(Podcast.DoesNotExist):
            result.raise_exception()

    def test_parse_podcast_feed_ok(self, mocker, new_podcast, categories):

        episode_guid = "https://mysteriousuniverse.org/?p=168097"
        episode_title = "original title"

        # test updated
        EpisodeFactory(podcast=new_podcast, guid=episode_guid, title=episode_title)

        mocker.patch(
            self.mock_http_get,
            return_value=MockResponse(
                url=new_podcast.rss,
                content=self.get_rss_content(),
                headers={
                    "ETag": "abc123",
                    "Last-Modified": self.updated,
                },
            ),
        )
        assert parse_podcast_feed(new_podcast.rss)

        # new episodes: 19
        assert Episode.objects.count() == 20

        # check episode updated
        episode = Episode.objects.get(guid=episode_guid)
        assert episode.title != episode_title

        new_podcast.refresh_from_db()

        assert new_podcast.rss
        assert new_podcast.active
        assert new_podcast.title == "Mysterious Universe"

        assert (
            new_podcast.description == "Blog and Podcast specializing in offbeat news"
        )

        assert new_podcast.owner == "8th Kind"

        assert new_podcast.modified
        assert new_podcast.modified.day == 1
        assert new_podcast.modified.month == 7
        assert new_podcast.modified.year == 2020
        assert new_podcast.parsed
        assert new_podcast.succeeded
        assert new_podcast.queued is None

        assert new_podcast.etag
        assert new_podcast.explicit
        assert new_podcast.cover_url

        assert new_podcast.pub_date == parse_date("Fri, 19 Jun 2020 16:58:03 +0000")

        assigned_categories = [c.name for c in new_podcast.categories.all()]

        assert "Science" in assigned_categories
        assert "Religion & Spirituality" in assigned_categories
        assert "Society & Culture" in assigned_categories
        assert "Philosophy" in assigned_categories

    def test_parse_podcast_feed_permanent_redirect(
        self, mocker, new_podcast, categories
    ):
        mocker.patch(
            self.mock_http_get,
            return_value=MockResponse(
                url=self.redirect_rss,
                status=http.HTTPStatus.PERMANENT_REDIRECT,
                headers={
                    "ETag": "abc123",
                    "Last-Modified": self.updated,
                },
                content=self.get_rss_content(),
            ),
        )
        assert parse_podcast_feed(new_podcast.rss)
        assert Episode.objects.filter(podcast=new_podcast).count() == 20

        new_podcast.refresh_from_db()

        assert new_podcast.rss == self.redirect_rss
        assert new_podcast.modified
        assert new_podcast.parsed
        assert new_podcast.queued is None

    def test_parse_podcast_feed_permanent_redirect_url_taken(
        self, mocker, new_podcast, categories
    ):
        other = PodcastFactory(rss=self.redirect_rss)
        current_rss = new_podcast.rss

        mocker.patch(
            self.mock_http_get,
            return_value=MockResponse(
                url=other.rss,
                status=http.HTTPStatus.PERMANENT_REDIRECT,
                headers={
                    "ETag": "abc123",
                    "Last-Modified": self.updated,
                },
                content=self.get_rss_content(),
            ),
        )
        assert not parse_podcast_feed(new_podcast.rss)

        new_podcast.refresh_from_db()

        assert new_podcast.rss == current_rss
        assert not new_podcast.active
        assert new_podcast.parsed
        assert new_podcast.queued is None

    def test_parse_podcast_feed_not_modified(self, mocker, new_podcast, categories):
        mocker.patch(
            self.mock_http_get,
            return_value=MockResponse(
                new_podcast.rss, status=http.HTTPStatus.NOT_MODIFIED
            ),
        )
        assert not parse_podcast_feed(new_podcast.rss)

        new_podcast.refresh_from_db()
        assert new_podcast.active
        assert new_podcast.modified is None
        assert new_podcast.queued is None

    def test_parse_podcast_feed_error(self, mocker, new_podcast, categories):
        mocker.patch(self.mock_http_get, side_effect=requests.RequestException)

        result = parse_podcast_feed(new_podcast.rss)
        assert result.success is False

        with pytest.raises(requests.RequestException):
            result.raise_exception()

        new_podcast.refresh_from_db()
        assert not new_podcast.active
        assert new_podcast.queued is None

    def test_parse_podcast_feed_gone(self, mocker, new_podcast, categories):
        mocker.patch(
            self.mock_http_get,
            return_value=BadMockResponse(new_podcast.rss, status=http.HTTPStatus.GONE),
        )
        result = parse_podcast_feed(new_podcast.rss)
        assert result.success is False

        with pytest.raises(requests.HTTPError):
            result.raise_exception()

        new_podcast.refresh_from_db()

        assert not new_podcast.active
        assert new_podcast.queued is None


class TestReschedule:
    @pytest.mark.parametrize(
        "hours_ago,hours_range",
        [
            (0, (0.5, 1.6)),
            (72, (1.8, 5.5)),
            (90 * 24, (54, 163.0)),
        ],
    )
    def test_reschedule(self, hours_ago, hours_range):
        now = timezone.now()
        podcast = Podcast(succeeded=now - timedelta(hours=hours_ago))
        scheduled = reschedule(podcast)
        value = (scheduled - now).total_seconds() / 3600
        assert value >= hours_range[0]
        assert value <= hours_range[1]

    def test_succeeded_none(self):
        scheduled = reschedule(Podcast(succeeded=None))
        value = (scheduled - timezone.now()).total_seconds() / 3600
        assert value >= 0.5
        assert value <= 1.5
