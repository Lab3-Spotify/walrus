from django.contrib import admin, messages
from django.db import transaction

from account.models import ExperimentGroup, Member
from playlist.services import ExperimentPlaylistService


@admin.action(description='為選中的 Members 建立實驗歌單')
def create_experiment_playlists(modeladmin, request, queryset):
    """
    為選中的 Members 建立實驗歌單

    使用 ExperimentPlaylistService 處理業務邏輯

    檢查項目：
    1. Member 必須設定 experiment_group
    2. Member 不能已有 EXPERIMENT 類型的 playlist
    3. MEMBER_FAVORITE 和 DISCOVER_WEEKLY 必須有足夠歌曲

    建立內容：
    - 兩個 type=EXPERIMENT 的 Playlist
    - 對應的 PlaylistTrack（標記 is_favorite）
    - 設定 description = "Experiment Playlist phase {1或2}"
    """
    success_count = 0
    error_messages = []

    for member in queryset:
        try:
            service = ExperimentPlaylistService(member)
            service.validate()

            with transaction.atomic():
                playlist1, playlist2 = service.create_playlists()

            success_count += 1
        except ValueError as e:
            error_messages.append(f"{member.name}: {str(e)}")
        except Exception as e:
            error_messages.append(f"{member.name}: 發生未預期的錯誤 - {str(e)}")

    # 顯示成功/失敗訊息
    if success_count:
        messages.success(request, f"成功為 {success_count} 位 Members 建立實驗歌單")

    for error in error_messages:
        messages.error(request, error)


@admin.register(ExperimentGroup)
class ExperimentGroupAdmin(admin.ModelAdmin):
    list_display = ['code', 'playlist_length', 'favorite_track_position']
    list_filter = ['playlist_length', 'favorite_track_position']
    search_fields = ['code']


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'name',
        'email',
        'experiment_group',
        'role',
        'spotify_provider',
        'created_at',
    ]
    list_filter = ['role', 'experiment_group', 'spotify_provider']
    search_fields = ['name', 'email', 'user__username']
    raw_id_fields = ['spotify_provider']
    readonly_fields = ['user']
    actions = [create_experiment_playlists]

    fieldsets = (
        ('基本資訊', {'fields': ('email', 'name', 'user')}),
        ('實驗設定', {'fields': ('experiment_group', 'role')}),
        ('Spotify 設定', {'fields': ('spotify_provider',)}),
    )
