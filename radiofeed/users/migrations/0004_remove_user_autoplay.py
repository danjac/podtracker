# Generated by Django 3.1.5 on 2021-01-05 15:55

# Django
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0003_auto_20201222_1039"),
    ]

    operations = [
        migrations.RemoveField(model_name="user", name="autoplay",),
    ]
