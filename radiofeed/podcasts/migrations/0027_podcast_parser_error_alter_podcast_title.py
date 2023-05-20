# Generated by Django 4.2.1 on 2023-05-14 18:30

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("podcasts", "0026_podcast_podping"),
    ]

    operations = [
        migrations.AddField(
            model_name="podcast",
            name="parser_error",
            field=models.CharField(
                blank=True,
                choices=[
                    ("duplicate", "Duplicate"),
                    ("inaccessible", "Inaccessible"),
                    ("invalid_rss", "Invalid RSS"),
                    ("not_modified", "Not Modified"),
                    ("unavailable", "Unavailable"),
                ],
                max_length=30,
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="podcast",
            name="title",
            field=models.TextField(blank=True),
        ),
    ]