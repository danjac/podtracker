# Generated by Django 4.1 on 2022-08-15 10:25

from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("podcasts", "0004_podcast_frequency"),
    ]

    operations = [
        migrations.AddField(
            model_name="podcast",
            name="queued",
            field=models.DateTimeField(
                blank=True, null=True, verbose_name="Queued for Update"
            ),
        ),
    ]
