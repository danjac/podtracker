# Generated by Django 3.2.3 on 2021-05-23 14:58

from django.db import migrations
from django.utils import timezone


def set_cover_image_date(apps, schema_editor):
    podcast_model = apps.get_model("podcasts", "Podcast")

    podcast_model.objects.filter(
        cover_image__isnull=False, cover_image_date__isnull=True
    ).update(cover_image_date=timezone.now())


class Migration(migrations.Migration):

    dependencies = [
        ("podcasts", "0002_auto_20210523_1457"),
    ]

    operations = [
        migrations.RunPython(
            set_cover_image_date, reverse_code=migrations.RunPython.noop
        )
    ]
