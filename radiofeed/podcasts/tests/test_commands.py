import pathlib

from django.core.management import call_command

from radiofeed.podcasts.itunes import Feed
from radiofeed.podcasts.models import Podcast


class TestCommands:
    def test_recommend(self, mocker):
        patched = mocker.patch("radiofeed.podcasts.recommender.recommend")
        call_command("recommend")
        patched.assert_called()

    def test_crawl_itunes(self, mocker, podcast):
        patched = mocker.patch(
            "radiofeed.podcasts.itunes.crawl",
            return_value=[
                Feed(
                    title="test 1",
                    url="https://example1.com",
                    rss="https://example1.com/test.xml",
                ),
                Feed(
                    title="test 2",
                    url="https://example2.com",
                    rss=podcast.rss,
                    podcast=podcast,
                ),
            ],
        )
        call_command("crawl_itunes")
        patched.assert_called()

    def test_import_podcast_feeds(self, db):
        call_command(
            "import_podcast_feeds",
            pathlib.Path(__file__).parent / "mocks" / "feeds.txt",
        )

        assert Podcast.objects.count() == 18
