# Generated by Django 3.2.9 on 2021-11-16 13:30

from __future__ import annotations

from django.db import migrations


def set_frequency(apps, schema_editor):
    pass


def set_frequency_none(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("podcasts", "0090_podcast_frequency"),
    ]

    operations = [
        migrations.RunPython(
            set_frequency,
            set_frequency_none,
        )
    ]
