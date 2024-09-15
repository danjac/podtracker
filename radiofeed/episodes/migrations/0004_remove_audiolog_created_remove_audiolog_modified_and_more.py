# Generated by Django 5.1.1 on 2024-09-15 08:22

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("episodes", "0003_alter_episode_cover_url_alter_episode_website"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="audiolog",
            name="created",
        ),
        migrations.RemoveField(
            model_name="audiolog",
            name="modified",
        ),
        migrations.RemoveField(
            model_name="bookmark",
            name="modified",
        ),
        migrations.AlterField(
            model_name="bookmark",
            name="created",
            field=models.DateTimeField(auto_now_add=True),
        ),
    ]