import pathlib

from datetime import timedelta

import pytest

from django.utils import timezone

from radiofeed.podcasts.parsers import rss_parser


class TestComplete:
    def test_true(self):
        assert rss_parser.complete("yes") is True

    def test_false(self):
        assert rss_parser.complete("no") is False

    def test_none(self):
        assert rss_parser.complete(None) is False


class TestExplicit:
    def test_true(self):
        assert rss_parser.explicit("yes") is True

    def test_false(self):
        assert rss_parser.explicit("no") is False

    def test_none(self):
        assert rss_parser.explicit(None) is False


class TestDuration:
    @pytest.mark.parametrize(
        "value,expected",
        [
            (None, ""),
            ("", ""),
            ("invalid", ""),
            ("300", "300"),
            ("10:30", "10:30"),
            ("10:30:59", "10:30:59"),
            ("10:30:99", "10:30"),
        ],
    )
    def test_parse_duration(self, value, expected):
        assert rss_parser.duration(value) == expected


class TestLanguageCode:
    @pytest.mark.parametrize(
        "value,expected",
        [
            ("fr", "fr"),
            ("fr-CA", "fr"),
            ("", "en"),
            (None, "en"),
        ],
    )
    def test_language_code(self, value, expected):
        assert rss_parser.language_code(value) == expected


class TestNotEmpty:
    @pytest.mark.parametrize(
        "value,raises",
        [
            ("ok", False),
            ("", True),
            (None, True),
        ],
    )
    def test_not_empty(self, value, raises):

        if raises:
            with pytest.raises(ValueError):
                rss_parser.not_empty(None, None, value)
        else:
            rss_parser.not_empty(None, None, value)


class TestUrl:
    @pytest.mark.parametrize(
        "value,raises",
        [
            ("http://example.com", False),
            ("https://example.com", False),
            ("example", True),
        ],
    )
    def test_url(self, value, raises):
        if raises:
            with pytest.raises(ValueError):
                rss_parser.url(None, None, value)
        else:
            rss_parser.url(None, None, value)


class TestPubDate:
    def test_ok(self):
        rss_parser.pub_date(None, None, timezone.now() - timedelta(hours=1))

    def test_in_future(self):
        with pytest.raises(ValueError):
            rss_parser.pub_date(None, None, timezone.now() + timedelta(hours=1))


class TestRssParser:
    def read_mock_file(self, mock_filename):
        return (pathlib.Path(__file__).parent / "mocks" / mock_filename).read_bytes()

    def test_empty(self):
        with pytest.raises(rss_parser.RssParserError):
            rss_parser.parse_rss(b"")

    def test_invalid_xml(self):
        with pytest.raises(rss_parser.RssParserError):
            rss_parser.parse_rss(b"junk string")

    def test_missing_channel(self):
        with pytest.raises(rss_parser.RssParserError):
            rss_parser.parse_rss(b"<rss />")

    def test_invalid_feed_channel(self):
        with pytest.raises(rss_parser.RssParserError):
            rss_parser.parse_rss(b"<rss><channel /></rss>")

    def test_with_bad_chars(self):
        content = self.read_mock_file("rss_mock.xml").decode("utf-8")
        content = content.replace("&amp;", "&")
        feed = rss_parser.parse_rss(bytes(content.encode("utf-8")))

        assert len(feed.items) == 20
        assert feed.title == "Mysterious Universe"

    @pytest.mark.parametrize(
        "filename,title,num_items",
        [
            ("rss_missing_enc_length.xml", "The Vanilla JS Podcast", 71),
            (
                "rss_bad_pub_date.xml",
                "Old Time Radio Mystery Theater",
                69,
            ),
            (
                "rss_mock_large.xml",
                "AAA United Public Radio & UFO Paranormal Radio Network",
                8641,
            ),
            ("rss_mock_iso_8859-1.xml", "Thunder & Lightning", 643),
            (
                "rss_mock_small.xml",
                "ABC News Update",
                1,
            ),
            (
                "rss_mock.xml",
                "Mysterious Universe",
                20,
            ),
            ("rss_invalid_duration.xml", "At The Races with Steve Byk", 450),
            (
                "rss_bad_cover_urls.xml",
                "TED Talks Daily",
                327,
            ),
            (
                "rss_superfeedr.xml",
                "The Chuck ToddCast: Meet the Press",
                296,
            ),
        ],
    )
    def test_parse_rss(self, filename, title, num_items):
        feed = rss_parser.parse_rss(self.read_mock_file(filename))
        assert feed.title == title
        assert len(feed.items) == num_items
