import pathlib

import pytest

from radiofeed.podcasts.parsers import opml_parser


class TestOpmlParser:
    def test_empty(self):
        with pytest.raises(opml_parser.OpmlParserError):
            list(opml_parser.parse_opml(b""))

    def test_invalid_xml(self):
        outlines = list(opml_parser.parse_opml(b"not opml content"))
        assert len(outlines) == 0

    def test_invalid_outline(self):
        content = (
            pathlib.Path(__file__).parent.parent / "mocks" / "feeds_with_invalid.opml"
        ).read_bytes()
        outlines = list(opml_parser.parse_opml(content))
        assert len(outlines) == 10

    def test_ok(self):
        content = (
            pathlib.Path(__file__).parent.parent / "mocks" / "feeds.opml"
        ).read_bytes()
        outlines = list(opml_parser.parse_opml(content))
        assert len(outlines) == 11
