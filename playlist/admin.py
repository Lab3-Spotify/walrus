from django.contrib import admin

from playlist.models import Playlist, PlaylistTrack


class PlaylistTrackInline(admin.TabularInline):
    model = PlaylistTrack
    extra = 0
    raw_id_fields = ['track']
    readonly_fields = ['created_at', 'updated_at']
    fields = [
        'order',
        'track',
        'is_favorite',
        'is_ever_listened',
        'satisfaction_score',
        'splendid_score',
    ]
    ordering = ['order']


@admin.register(Playlist)
class PlaylistAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'member',
        'type',
        'length_type',
        'favorite_track_position_type',
        'experiment_phase',
        'satisfaction_score',
        'created_at',
    ]
    list_filter = [
        'type',
        'length_type',
        'favorite_track_position_type',
        'experiment_phase',
    ]
    search_fields = ['member__name', 'member__email', 'external_id', 'description']
    raw_id_fields = ['member']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [PlaylistTrackInline]

    fieldsets = (
        ('基本資訊', {'fields': ('member', 'type', 'external_id')}),
        (
            '歌單配置',
            {
                'fields': (
                    'length_type',
                    'favorite_track_position_type',
                    'experiment_phase',
                )
            },
        ),
        (
            '其他',
            {
                'fields': (
                    'description',
                    'satisfaction_score',
                    'created_at',
                    'updated_at',
                )
            },
        ),
    )


@admin.register(PlaylistTrack)
class PlaylistTrackAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'playlist',
        'track',
        'order',
        'is_ever_listened',
        'is_favorite',
        'satisfaction_score',
        'splendid_score',
        'created_at',
    ]
    list_filter = ['is_favorite', 'playlist__type']
    search_fields = ['track__name', 'playlist__member__name']
    raw_id_fields = ['playlist', 'track']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('關聯', {'fields': ('playlist', 'track', 'order')}),
        ('屬性', {'fields': ('is_favorite', 'satisfaction_score', 'splendid_score')}),
        ('時間戳記', {'fields': ('created_at', 'updated_at')}),
    )
