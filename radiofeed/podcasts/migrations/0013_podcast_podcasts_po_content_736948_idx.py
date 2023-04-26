# Generated by Django 4.1.4 on 2022-12-21 09:30

from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("podcasts", "0012_remove_podcast_parse_result"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="podcast",
            index=models.Index(
                fields=["content_hash"], name="podcasts_po_content_736948_idx"
            ),
        ),
    ]
