from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    'check-and-update-missing-artist-details': {
        'task': 'provider.tasks.check_and_update_missing_artist_details',
        'schedule': crontab(hour='*/4'),  # 每 4 小時（0, 4, 8, 12, 16, 20）
    },
    'check-and-update-missing-playlist-context-details': {
        'task': 'provider.tasks.check_and_update_missing_playlist_context_details',
        'schedule': crontab(
            minute=30, hour='1,5,9,13,17,21'
        ),  # 每 4 小時，但在 1:30, 5:30, 9:30... 執行（與 artist 錯開）
    },
    'collect-all-members-recently-played-logs': {
        'task': 'provider.tasks.collect_all_members_recently_played_logs',
        'schedule': crontab(minute=0, hour='*'),  # 每小時整點
    },
}
