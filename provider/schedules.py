from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    'check-and-update-missing-artist-details': {
        'task': 'provider.tasks.check_and_update_missing_artist_details',
        'schedule': crontab(hour='*/4'),
    },
    'collect-all-members-recently-played-logs': {
        'task': 'provider.tasks.collect_all_members_recently_played_logs',
        'schedule': crontab(minute=0, hour='*'),
    },
}
