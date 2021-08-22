from __future__ import annotations

import pytest
import requests

from django.core.cache import cache

from jcasts.podcasts import podcastindex
from jcasts.podcasts.factories import PodcastFactory
from jcasts.podcasts.models import Podcast


def patch_request(mocker, response):
    return mocker.patch("requests.post", return_value=response, autospec=True)


@pytest.fixture
def mock_parse_feed(mocker):
    return mocker.patch("jcasts.podcasts.podcastindex.parse_feed.delay")


@pytest.fixture
def mock_good_response(mocker):
    class MockResponse:
        def raise_for_status(self):
            ...

        def json(self) -> dict:

            return {
                "count": 1,
                "feeds": [
                    {
                        "id": 12345,
                        "url": "https://feeds.fireside.fm/testandcode/rss",
                        "title": "Test & Code : Python Testing",
                        "image": "https://assets.fireside.fm/file/fireside-images/podcasts/images/b/bc7f1faf-8aad-4135-bb12-83a8af679756/cover.jpg?v=3",
                    }
                ],
            }

    yield patch_request(mocker, MockResponse())


@pytest.fixture
def mock_bad_response(mocker):
    class MockResponse:
        def raise_for_status(self):
            raise requests.HTTPError()

    yield patch_request(mocker, MockResponse())


@pytest.fixture
def mock_invalid_response(mocker):
    class MockResponse:
        def raise_for_status(self):
            ...

        def json(self):
            return {"count": 1, "feeds": [{"id": 12345, "url": "bad-url"}]}

    yield patch_request(mocker, MockResponse())


class TestNewFeeds:
    def test_ok(self, db, mock_good_response, mock_parse_feed):

        feeds = podcastindex.new_feeds()
        assert len(feeds) == 1
        assert Podcast.objects.filter(rss=feeds[0].url).exists()
        mock_parse_feed.assert_called()


class TestSearch:
    cache_key = "podcastindex:6447567a64413d3d"

    def test_not_ok(self, db, mock_bad_response, mock_parse_feed):

        with pytest.raises(requests.HTTPError):
            podcastindex.search("test")

        assert not Podcast.objects.exists()
        mock_parse_feed.assert_not_called()

    def test_ok(self, db, mock_good_response, mock_parse_feed):
        feeds = podcastindex.search("test")
        assert len(feeds) == 1
        assert Podcast.objects.filter(rss=feeds[0].url).exists()
        mock_parse_feed.assert_called()

    def test_bad_data(self, db, mock_invalid_response, mock_parse_feed):
        feeds = podcastindex.search("test")
        assert len(feeds) == 0
        mock_parse_feed.assert_not_called()

    def test_is_not_cached(self, db, mock_good_response, mock_parse_feed, locmem_cache):

        feeds = podcastindex.search_cached("test")

        assert len(feeds) == 1
        assert Podcast.objects.filter(rss=feeds[0].url).exists()
        mock_parse_feed.assert_called()

        assert cache.get(self.cache_key) == feeds

    def test_is_cached(self, db, mock_good_response, mock_parse_feed, locmem_cache):

        cache.set(
            self.cache_key,
            [podcastindex.Feed(url="https://example.com", title="test")],
        )

        feeds = podcastindex.search_cached("test")

        assert len(feeds) == 1
        assert not Podcast.objects.filter(rss=feeds[0].url).exists()

        mock_good_response.assert_not_called()
        mock_parse_feed.assert_not_called()

    def test_podcast_exists(self, db, mock_good_response, mock_parse_feed):
        PodcastFactory(rss="https://feeds.fireside.fm/testandcode/rss")
        feeds = podcastindex.search("test")
        assert len(feeds) == 1
        assert Podcast.objects.filter(rss=feeds[0].url).exists()
        mock_parse_feed.assert_not_called()
