# Generated by Django 3.2.7 on 2021-09-28 07:09

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("podcasts", "0051_set_scheduled_none_for_websub_podcasts"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="podcast",
            name="websub_exception",
        ),
        migrations.RemoveField(
            model_name="podcast",
            name="websub_hub",
        ),
        migrations.RemoveField(
            model_name="podcast",
            name="websub_requested",
        ),
        migrations.RemoveField(
            model_name="podcast",
            name="websub_secret",
        ),
        migrations.RemoveField(
            model_name="podcast",
            name="websub_subscribed",
        ),
        migrations.RemoveField(
            model_name="podcast",
            name="websub_token",
        ),
        migrations.RemoveField(
            model_name="podcast",
            name="websub_url",
        ),
    ]
