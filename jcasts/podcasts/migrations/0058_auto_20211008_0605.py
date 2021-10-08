# Generated by Django 3.2.8 on 2021-10-08 06:05

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("podcasts", "0057_set_succeeded_default"),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name="podcast",
            name="podcasts_po_succeed_2b570a_idx",
        ),
        migrations.AddIndex(
            model_name="podcast",
            index=models.Index(
                fields=["-pub_date", "-succeeded"],
                name="podcasts_po_pub_dat_38d2cb_idx",
            ),
        ),
    ]
