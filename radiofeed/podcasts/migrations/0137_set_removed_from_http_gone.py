# Generated by Django 4.0.5 on 2022-06-12 12:10

import http

from django.db import migrations


def set_removed_from_http_gone(apps, schema_editor):
    apps.get_model("podcasts.Podcast").objects.filter(
        http_status=http.HTTPStatus.GONE
    ).update(result="removed")


class Migration(migrations.Migration):

    dependencies = [
        ("podcasts", "0136_alter_podcast_result"),
    ]

    operations = [
        migrations.RunPython(
            set_removed_from_http_gone, reverse_code=migrations.RunPython.noop
        )
    ]
