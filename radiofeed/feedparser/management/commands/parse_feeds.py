from argparse import ArgumentParser
from concurrent.futures import ThreadPoolExecutor

from django.core.management.base import BaseCommand
from django.db import connections

from radiofeed.feedparser import feed_parser, scheduler
from radiofeed.feedparser.exceptions import FeedParserError
from radiofeed.podcasts.models import Podcast


class Command(BaseCommand):
    """Parses RSS feeds."""

    help = """Parses RSS feeds of all scheduled podcasts."""

    def add_arguments(self, parser: ArgumentParser) -> None:
        """Parse command args."""
        parser.add_argument(
            "--watch",
            help="Watch continuously",
            default=False,
            action="store_true",
        )
        parser.add_argument(
            "--limit",
            help="Number of feeds to process",
            type=int,
            default=360,
        )

    def handle(self, **options) -> None:
        """Command handler implementation."""

        def _done(future):
            connections.close_all()

        while True:
            with ThreadPoolExecutor() as executor:
                for podcast_id in scheduler.get_podcasts_for_update().values_list(
                    "pk", flat=True
                )[: options["limit"]]:
                    future = executor.submit(self._parse_feed, podcast_id)
                    future.add_done_callback(_done)

            if not options["watch"]:
                break

    def _parse_feed(self, podcast_id: int) -> None:
        podcast = Podcast.objects.get(pk=podcast_id)
        try:
            feed_parser.FeedParser(podcast).parse()
            self.stdout.write(self.style.SUCCESS(f"parse feed ok: {podcast}"))
        except FeedParserError as e:
            self.stderr.write(
                self.style.ERROR(f"parse feed {e.parser_error}: {podcast}")
            )
