from __future__ import annotations

from argparse import ArgumentParser
from concurrent.futures import ThreadPoolExecutor

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from radiofeed.websub import subscriber
from radiofeed.websub.models import Subscription


class Command(BaseCommand):
    """Subscribes new feeds to their websub hub."""

    help = """Subscribes new feeds to their websub hub."""

    def add_arguments(self, parser: ArgumentParser) -> None:
        """Parse command args."""
        parser.add_argument(
            "--limit",
            help="Max number of feeds for update",
            type=int,
            default=360,
        )

    def handle(self, **options) -> None:
        """Command handler implementation."""
        with ThreadPoolExecutor() as executor:
            executor.map(
                self._subscribe,
                Subscription.objects.filter(
                    Q(status=Subscription.Status.PENDING)
                    | Q(
                        status=Subscription.Status.SUBSCRIBED,
                        expires__lt=timezone.now(),
                    )
                )
                .select_related("podcast")
                .order_by("expires", "-created")[: options["limit"]]
                .iterator(),
            )

    def _subscribe(self, subscription: Subscription) -> None:
        self.stdout.write(f"Subscribing feed {subscription.podcast}...")
        subscriber.subscribe(subscription)
