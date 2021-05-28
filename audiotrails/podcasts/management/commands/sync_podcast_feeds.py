from django.core.management.base import BaseCommand, CommandParser

from audiotrails.podcasts.models import Podcast
from audiotrails.podcasts.tasks import sync_podcast_feed, sync_podcast_feeds


class Command(BaseCommand):
    help = "Updates all podcasts from their RSS feeds."

    def add_arguments(self, parser: CommandParser) -> None:

        parser.add_argument(
            "--run-job",
            action="store_true",
            help="Just runs the sync_podcast_feeds celery task with no arguments",
        )

        parser.add_argument(
            "--no-pub-date",
            action="store_true",
            help="Updates only podcasts without a pub date",
        )

        parser.add_argument(
            "--use-celery",
            action="store_true",
            help="Sync each podcast using celery task",
        )

    def handle(self, *args, **options) -> None:

        if options["run_job"]:
            sync_podcast_feeds.delay()
            return

        podcasts = Podcast.objects.all()

        if options["no_pub_date"]:
            podcasts = podcasts.filter(pub_date__isnull=True)

        use_celery = options["use_celery"]

        for podcast in podcasts:
            self.sync_podcast(podcast, use_celery)

    def sync_podcast(self, podcast: Podcast, use_celery: bool) -> None:
        if use_celery:
            self.stdout.write(f"Create sync task for {podcast}")
            sync_podcast_feed.delay(rss=podcast.rss)
        else:
            try:
                sync_podcast_feed(rss=podcast.rss)
            except Exception as e:
                self.stdout.write(self.style.ERROR(str(e)))
