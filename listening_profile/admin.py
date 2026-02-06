from django.contrib import admin

from .models import HistoryPlayLog, HistoryPlayLogContext


@admin.register(HistoryPlayLogContext)
class HistoryPlayLogContextAdmin(admin.ModelAdmin):
    list_display = ('type', 'external_id', 'created_at', 'updated_at')
    list_filter = ('type', 'created_at')
    search_fields = ('external_id',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(HistoryPlayLog)
class HistoryPlayLogAdmin(admin.ModelAdmin):
    list_display = ('member', 'track', 'provider', 'played_at', 'context')
    list_filter = ('provider', 'member', 'played_at')
    search_fields = ('member__username', 'track__name')
    readonly_fields = ('played_at',)
    date_hierarchy = 'played_at'
