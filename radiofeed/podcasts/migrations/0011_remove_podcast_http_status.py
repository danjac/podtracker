# Generated by Django 4.1.4 on 2022-12-15 07:08

from __future__ import annotations

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("podcasts", "0010_podcast_podcasts_podcast_lwr_title_idx"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="podcast",
            name="http_status",
        ),
    ]
