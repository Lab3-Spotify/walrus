# Generated by Django 5.2.2 on 2025-06-25 15:33

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ('account', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Provider',
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
                    'code',
                    models.CharField(
                        choices=[('spotify', 'Spotify')], max_length=50, unique=True
                    ),
                ),
                (
                    'category',
                    models.CharField(choices=[('music', 'Music')], max_length=100),
                ),
                (
                    'auth_handler',
                    models.CharField(
                        help_text='Auth Handler import path',
                        max_length=255,
                        unique=True,
                    ),
                ),
                (
                    'api_handler',
                    models.CharField(
                        help_text='API Handler import path', max_length=255, unique=True
                    ),
                ),
                ('base_url', models.CharField(blank=True, max_length=255)),
                (
                    'auth_type',
                    models.CharField(
                        choices=[('oauth2', 'OAuth2'), ('jwt', 'JWT')], max_length=20
                    ),
                ),
                ('auth_details', models.JSONField(default=dict, null=True)),
                ('extra_details', models.JSONField(default=dict, null=True)),
                ('display_name', models.CharField(max_length=100)),
                ('description', models.TextField(blank=True)),
                (
                    'default_token_expiration',
                    models.PositiveIntegerField(blank=True, null=True),
                ),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name='MemberAPIToken',
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
                ('_access_token', models.TextField(db_column='access_token')),
                (
                    '_refresh_token',
                    models.TextField(blank=True, db_column='refresh_token', null=True),
                ),
                ('expires_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'member',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='api_tokens',
                        to='account.member',
                    ),
                ),
                (
                    'provider',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='member_tokens',
                        to='provider.provider',
                    ),
                ),
            ],
            options={
                'unique_together': {('member', 'provider')},
            },
        ),
    ]
