# Generated by Django 4.0.6 on 2022-07-20 13:28

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('podcasts', '0002_alter_podcast_parse_result'),
    ]

    operations = [
        migrations.AlterField(
            model_name='podcast',
            name='http_status',
            field=models.SmallIntegerField(blank=True, null=True, verbose_name='HTTP Status'),
        ),
        migrations.AlterField(
            model_name='podcast',
            name='num_retries',
            field=models.PositiveSmallIntegerField(default=0, verbose_name='RSS Feed Retry Count'),
        ),
    ]
