# Generated by Django 3.2.9 on 2021-11-29 08:40

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("podcasts", "0103_alter_podcast_frequency_modifier"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="podcast",
            name="last_build_date",
        ),
    ]
