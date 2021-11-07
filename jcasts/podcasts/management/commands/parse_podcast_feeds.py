from __future__ import annotations

import argparse

from datetime import timedelta

from django.core.management.base import BaseCommand

from jcasts.podcasts import feed_parser


class Command(BaseCommand):
    help = "Parse podcast feeds"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--minutes",
            help="Frequency between updates (minutes)",
            type=int,
        )

    def handle(self, *args, **options) -> None:
        num_podcasts = feed_parser.parse_podcast_feeds(
            frequency=timedelta(minutes=options["frequency"])
            if options["frequency"]
            else None
        )
        self.stdout.write(
            self.style.SUCCESS(f"{num_podcasts} podcast feeds queued for update")
        )
