# Generated by Django 4.1.5 on 2023-01-05 18:44

from __future__ import annotations

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0009_alter_user_language_and_more"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="user",
            name="language",
        ),
    ]
