# Generated by Django 3.2.9 on 2021-11-18 11:12

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("podcasts", "0097_rename_schedule_modifier_podcast_frequency_modifier"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="podcast",
            name="podcastindex",
        ),
    ]
