import datetime
import json
import pathlib
import uuid

from unittest.mock import patch

import pytz
import requests

from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from pydantic import ValidationError

from audiotrails.episodes.factories import EpisodeFactory
from audiotrails.episodes.models import Episode

from ..factories import CategoryFactory, PodcastFactory
from ..rss_parser import RssParserError, parse_rss
from ..rss_parser.date_parser import parse_date
from ..rss_parser.models import Audio, Feed, Item, get_categories_dict


class BaseMockResponse:
    def __init__(self, raises=False):
        self.raises = raises

    def raise_for_status(self):
        if self.raises:
            raise requests.exceptions.HTTPError()


class MockHeaderResponse(BaseMockResponse):
    def __init__(self):
        super().__init__()
        self.headers = {
            "ETag": uuid.uuid4().hex,
            "Last-Modified": "Sun, 05 Jul 2020 19:21:33 GMT",
        }


class MockResponse(BaseMockResponse):
    def __init__(self, mock_file=None, raises=False):
        super().__init__(raises)
        self.headers = {
            "ETag": uuid.uuid4().hex,
            "Last-Modified": "Sun, 05 Jul 2020 19:21:33 GMT",
        }

        if mock_file:
            self.content = open(
                pathlib.Path(__file__).parent / "mocks" / mock_file, "rb"
            ).read()
        self.raises = raises

    def json(self):
        return json.loads(self.content)


class ParseRssTests(TestCase):
    def tearDown(self):
        get_categories_dict.cache_clear()

    @patch("requests.head", autospec=True, side_effect=requests.RequestException)
    def test_parse_error(self, *mocks):
        podcast = PodcastFactory()
        self.assertRaises(RssParserError, parse_rss, podcast)
        podcast.refresh_from_db()
        self.assertEqual(podcast.num_retries, 1)

    @patch("requests.head", autospec=True, return_value=MockHeaderResponse())
    @patch("requests.get", autospec=True, return_value=MockResponse("rss_mock.xml"))
    def test_parse(self, *mocks):
        [
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
        podcast = PodcastFactory(
            rss="https://mysteriousuniverse.org/feed/podcast/",
            last_updated=None,
            pub_date=None,
        )
        self.assertTrue(parse_rss(podcast))
        podcast.refresh_from_db()

        self.assertTrue(podcast.last_updated)
        self.assertTrue(podcast.pub_date)

        self.assertTrue(podcast.etag)
        self.assertTrue(podcast.cover_image)
        self.assertTrue(podcast.extracted_text)

        self.assertEqual(podcast.title, "Mysterious Universe")
        self.assertEqual(podcast.creators, "8th Kind")
        self.assertEqual(podcast.categories.count(), 6)
        self.assertEqual(podcast.episode_set.count(), 20)

    @patch("requests.head", autospec=True, return_value=MockHeaderResponse())
    @patch("requests.get", autospec=True, return_value=MockResponse("rss_mock.xml"))
    def test_parse_if_already_updated(self, *mocks):
        podcast = PodcastFactory(
            rss="https://mysteriousuniverse.org/feed/podcast/",
            last_updated=timezone.now(),
            cover_image=None,
            pub_date=None,
        )

        self.assertFalse(parse_rss(podcast))
        podcast.refresh_from_db()

        self.assertFalse(podcast.pub_date)
        self.assertFalse(podcast.cover_image)

        self.assertNotEqual(podcast.title, "Mysterious Universe")
        self.assertEqual(podcast.episode_set.count(), 0)

    @patch("requests.head", autospec=True, return_value=MockHeaderResponse())
    @patch("requests.get", autospec=True, return_value=MockResponse("rss_mock.xml"))
    def test_parse_existing_episodes(self, *mocks):
        podcast = PodcastFactory(
            rss="https://mysteriousuniverse.org/feed/podcast/",
            last_updated=None,
            pub_date=None,
        )

        EpisodeFactory(podcast=podcast, guid="https://mysteriousuniverse.org/?p=168097")
        EpisodeFactory(podcast=podcast, guid="https://mysteriousuniverse.org/?p=167650")
        EpisodeFactory(podcast=podcast, guid="https://mysteriousuniverse.org/?p=167326")

        # check episode not present is deleted
        EpisodeFactory(podcast=podcast, guid="some-random")

        self.assertEqual(len(parse_rss(podcast)), 17)
        podcast.refresh_from_db()

        self.assertEqual(podcast.episode_set.count(), 20)
        self.assertFalse(Episode.objects.filter(guid="some-random").exists())


class AudioModelTests(SimpleTestCase):
    def test_audio(self):
        Audio(
            type="audio/mpeg",
            url="https://www.podtrac.com/pts/redirect.mp3/traffic.megaphone.fm/TSK8060512733.mp3",
        )

    def test_not_audio(self):
        self.assertRaises(
            ValidationError,
            Audio,
            type="text/xml",
            url="https://www.podtrac.com/pts/redirect.mp3/traffic.megaphone.fm/TSK8060512733.mp3",
        )


class FeedModelTests(SimpleTestCase):
    def setUp(self):
        self.item = Item(
            audio=Audio(
                type="audio/mpeg",
                rel="enclosure",
                url="https://www.podtrac.com/pts/redirect.mp3/traffic.megaphone.fm/TSK8060512733.mp3",
            ),
            title="test",
            guid="test",
            pub_date="Fri, 12 Jun 2020 17:33:46 +0000",
            duration="2000",
        )

    def test_language(self):

        feed = Feed(
            title="test",
            description="test",
            items=[self.item],
            creators=[],
            image=None,
            link="http://reddit.com",
            language="en-gb",
            categories=[],
        )

        self.assertEqual(feed.language, "en")

    def test_language_with_spaces(self):

        feed = Feed(
            title="test",
            description="test",
            items=[self.item],
            creators=[],
            image=None,
            link="http://reddit.com",
            language=" en-us",
            categories=[],
        )

        self.assertEqual(feed.language, "en")

    def test_language_with_single_value(self):

        feed = Feed(
            title="test",
            description="test",
            items=[self.item],
            creators=[],
            image=None,
            link="http://reddit.com",
            language="fi",
            categories=[],
        )

        self.assertEqual(feed.language, "fi")

    def test_language_with_empty(self):

        feed = Feed(
            title="test",
            description="test",
            items=[self.item],
            creators=[],
            image=None,
            link="http://reddit.com",
            language="",
            categories=[],
        )

        self.assertEqual(feed.language, "en")

    def test_valid_link(self):
        feed = Feed(
            title="test",
            description="test",
            items=[self.item],
            creators=[],
            image=None,
            link="http://reddit.com",
            categories=[],
        )

        self.assertEqual(feed.link, "http://reddit.com")

    def test_empty_link(self):
        feed = Feed(
            title="test",
            description="test",
            items=[self.item],
            creators=[],
            image=None,
            link="",
            categories=[],
        )

        self.assertEqual(feed.link, "")

    def test_missing_http(self):
        feed = Feed(
            title="test",
            description="test",
            items=[self.item],
            creators=[],
            image=None,
            link="politicology.com",
            categories=[],
        )

        self.assertEqual(feed.link, "http://politicology.com")


class ParseDateTests(SimpleTestCase):
    def test_parse_date_if_valid(self):
        dt = datetime.datetime(2020, 6, 19, 16, 58, 3, tzinfo=pytz.UTC)
        self.assertEqual(parse_date("Fri, 19 Jun 2020 16:58:03 +0000"), dt)

    def test_parse_date_if_no_tz(self):
        dt = datetime.datetime(2020, 6, 19, 16, 58, 3, tzinfo=pytz.UTC)
        self.assertEqual(parse_date("Fri, 19 Jun 2020 16:58:03"), dt)

    def test_parse_date_if_invalid(self):
        self.assertEqual(parse_date("Fri, 33 June 2020 16:58:03 +0000"), None)
