# Generated by Django 4.1.6 on 2023-02-09 09:41

from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("podcasts", "0015_podcast_websub_expires_podcast_websub_hub_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="podcast",
            name="websub_verified",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
