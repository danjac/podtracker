# Generated by Django 3.2.5 on 2021-07-27 10:46

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("podcasts", "0021_remove_podcast_scheduled"),
    ]

    operations = [
        migrations.AddField(
            model_name="podcast",
            name="frequency",
            field=models.PositiveIntegerField(default=1),
        ),
    ]
