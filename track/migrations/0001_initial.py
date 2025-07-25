# Generated by Django 5.2.2 on 2025-06-28 12:46

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ('provider', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Genre',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                ('name', models.CharField(max_length=100)),
                ('category', models.CharField(blank=True, max_length=100, null=True)),
                (
                    'provider',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='genres',
                        to='provider.provider',
                    ),
                ),
            ],
            options={
                'unique_together': {('name', 'provider')},
            },
        ),
        migrations.CreateModel(
            name='Artist',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                ('external_id', models.CharField(max_length=255)),
                ('name', models.CharField(max_length=200)),
                ('popularity', models.IntegerField(blank=True, null=True)),
                ('followers_count', models.IntegerField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                (
                    'provider',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='artists',
                        to='provider.provider',
                    ),
                ),
                (
                    'genres',
                    models.ManyToManyField(related_name='artists', to='track.genre'),
                ),
            ],
            options={
                'unique_together': {('external_id', 'provider')},
            },
        ),
        migrations.CreateModel(
            name='Track',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                ('external_id', models.CharField(max_length=255)),
                ('name', models.CharField(max_length=200)),
                ('popularity', models.IntegerField(blank=True, null=True)),
                ('is_playable', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                (
                    'artists',
                    models.ManyToManyField(related_name='tracks', to='track.artist'),
                ),
                (
                    'genres',
                    models.ManyToManyField(related_name='tracks', to='track.genre'),
                ),
                (
                    'provider',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='tracks',
                        to='provider.provider',
                    ),
                ),
            ],
            options={
                'unique_together': {('external_id', 'provider')},
            },
        ),
        migrations.CreateModel(
            name='Clip',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                (
                    'source',
                    models.CharField(
                        choices=[
                            ('spotify', 'Spotify'),
                            ('force', 'Force'),
                            ('ai', 'AI'),
                        ],
                        max_length=50,
                    ),
                ),
                ('start_time_ms', models.FloatField()),
                ('end_time_ms', models.FloatField()),
                ('is_active', models.BooleanField(default=True)),
                ('extra_details', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'description',
                    models.CharField(blank=True, max_length=255, null=True),
                ),
                (
                    'track',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='clips',
                        to='track.track',
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name='TrackAudioFeatures',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                ('acousticness', models.FloatField(blank=True, null=True)),
                ('danceability', models.FloatField(blank=True, null=True)),
                ('energy', models.FloatField(blank=True, null=True)),
                ('instrumentalness', models.FloatField(blank=True, null=True)),
                ('liveness', models.FloatField(blank=True, null=True)),
                ('loudness', models.FloatField(blank=True, null=True)),
                ('speechiness', models.FloatField(blank=True, null=True)),
                ('valence', models.FloatField(blank=True, null=True)),
                ('tempo', models.FloatField(blank=True, null=True)),
                ('key', models.IntegerField(blank=True, null=True)),
                ('mode', models.IntegerField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'track',
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='audio_features',
                        to='track.track',
                    ),
                ),
            ],
        ),
    ]
