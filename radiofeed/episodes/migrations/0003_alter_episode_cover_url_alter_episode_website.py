# Generated by Django 5.1.1 on 2024-09-14 11:01

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("episodes", "0002_add_episode_search_trigger"),
    ]

    operations = [
        migrations.AlterField(
            model_name="episode",
            name="cover_url",
            field=models.URLField(blank=True, default="", max_length=2083),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="episode",
            name="website",
            field=models.URLField(blank=True, default="", max_length=2083),
            preserve_default=False,
        ),
    ]
