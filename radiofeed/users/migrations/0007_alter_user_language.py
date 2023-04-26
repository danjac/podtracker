# Generated by Django 4.0.6 on 2022-07-16 12:06

from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0006_user_language"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="language",
            field=models.CharField(
                choices=[("en", "English"), ("fi", "Finnish")],
                default="en",
                max_length=2,
                verbose_name="Language",
            ),
        ),
    ]
