from django.contrib import admin

from track.models import Artist, Genre, Track


@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'category', 'provider']
    list_filter = ['provider', 'category']
    search_fields = ['name', 'category']
    raw_id_fields = ['provider']


@admin.register(Artist)
class ArtistAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'name',
        'provider',
        'popularity',
        'followers_count',
        'created_at',
    ]
    list_filter = ['provider']
    search_fields = ['name', 'external_id']
    raw_id_fields = ['provider']
    filter_horizontal = ['genres']
    readonly_fields = ['created_at']


@admin.register(Track)
class TrackAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'name',
        'provider',
        'popularity',
        'is_playable',
        'isrc',
        'created_at',
    ]
    list_filter = ['provider', 'is_playable']
    search_fields = ['name', 'external_id', 'isrc']
    raw_id_fields = ['provider']
    filter_horizontal = ['artists', 'genres']
    readonly_fields = ['created_at']

    fieldsets = (
        ('基本資訊', {'fields': ('name', 'external_id', 'provider')}),
        (
            '音樂資訊',
            {'fields': ('artists', 'genres', 'popularity', 'is_playable', 'isrc')},
        ),
        ('時間戳記', {'fields': ('created_at',)}),
    )
