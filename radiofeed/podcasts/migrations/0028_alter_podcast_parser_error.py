# Generated by Django 4.2.1 on 2023-05-16 15:03

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("podcasts", "0027_podcast_parser_error_alter_podcast_title"),
    ]

    operations = [
        migrations.AlterField(
            model_name="podcast",
            name="parser_error",
            field=models.CharField(
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
    ]
