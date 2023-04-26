# Generated by Django 4.0.6 on 2022-07-16 12:04

from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0005_alter_user_send_email_notifications"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="language",
            field=models.CharField(
                choices=[("en", "English"), ("fi", "Finnish")],
                default="en",
                max_length=2,
            ),
        ),
    ]
