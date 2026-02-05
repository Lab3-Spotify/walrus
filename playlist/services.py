"""
實驗歌單建立服務
"""
from django.db import transaction

from account.models import ExperimentGroup, Member
from playlist.constants import PlaylistConfig
from playlist.models import Playlist, PlaylistTrack


class ExperimentPlaylistService:
    """
    實驗歌單建立服務

    負責處理實驗歌單的建立邏輯，包括：
    - 驗證 Member 的實驗組設定
    - 驗證來源歌單的歌曲數量
    - 根據實驗組配置建立兩個階段的歌單
    - 分配歌曲到對應位置
    """

    def __init__(self, member):
        """
        初始化服務

        Args:
            member: Member instance，要建立實驗歌單的會員
        """
        self.member = member

    def validate(self):
        """
        驗證是否可以建立實驗歌單

        檢查：
        1. Member 是否設定 experiment_group
        2. Member 是否已有 EXPERIMENT playlist
        3. MEMBER_FAVORITE 是否存在且有足夠歌曲
        4. DISCOVER_WEEKLY 是否存在且有足夠歌曲

        Raises:
            ValueError: 驗證失敗時拋出異常，包含錯誤訊息
        """
        # 檢查 experiment_group
        if not self.member.experiment_group:
            raise ValueError(f"Member {self.member.name} 未設定 experiment_group")

        # 檢查是否已有實驗歌單
        existing_experiment = Playlist.objects.filter(
            member=self.member, type=Playlist.TypeOptions.EXPERIMENT
        ).exists()
        if existing_experiment:
            raise ValueError(f"Member {self.member.name} 已有實驗歌單")

        # 檢查來源歌單
        favorite_playlist = Playlist.objects.filter(
            member=self.member, type=Playlist.TypeOptions.MEMBER_FAVORITE
        ).first()

        if not favorite_playlist:
            raise ValueError(f"Member {self.member.name} 沒有 MEMBER_FAVORITE 歌單")

        discover_playlist = Playlist.objects.filter(
            member=self.member, type=Playlist.TypeOptions.DISCOVER_WEEKLY
        ).first()

        if not discover_playlist:
            raise ValueError(f"Member {self.member.name} 沒有 DISCOVER_WEEKLY 歌單")

        # 檢查歌曲數量
        favorite_count = favorite_playlist.playlist_tracks.count()
        if favorite_count < PlaylistConfig.MIN_FAVORITE_TRACKS:
            raise ValueError(
                f"Member {self.member.name} 的 MEMBER_FAVORITE 歌曲不足 "
                f"(需要 {PlaylistConfig.MIN_FAVORITE_TRACKS} 首，目前 {favorite_count} 首)"
            )

        discover_count = discover_playlist.playlist_tracks.count()
        if discover_count < PlaylistConfig.MIN_DISCOVER_TRACKS:
            raise ValueError(
                f"Member {self.member.name} 的 DISCOVER_WEEKLY 歌曲不足 "
                f"(需要 {PlaylistConfig.MIN_DISCOVER_TRACKS} 首，目前 {discover_count} 首)"
            )

    @transaction.atomic
    def create_playlists(self):
        """
        建立兩個實驗歌單

        Returns:
            tuple: (playlist_phase1, playlist_phase2)
        """
        # 取得來源歌單
        favorite_playlist, discover_playlist = self._get_source_playlists()

        # 取得兩個 phase 的規格
        phase1_spec, phase2_spec = self._get_playlist_specs()

        # 選擇 favorite 歌曲
        phase1_favorite_tracks, phase2_favorite_tracks = self._select_tracks_for_phases(
            favorite_playlist,
            phase1_spec['favorite_count'],
            phase2_spec['favorite_count'],
        )

        # 選擇 discover 歌曲
        phase1_discover_tracks, phase2_discover_tracks = self._select_tracks_for_phases(
            discover_playlist,
            phase1_spec['discover_count'],
            phase2_spec['discover_count'],
        )

        # 建立兩個歌單
        playlist1 = self._create_single_playlist(
            phase=1,
            spec=phase1_spec,
            favorite_tracks=phase1_favorite_tracks,
            discover_tracks=phase1_discover_tracks,
        )

        playlist2 = self._create_single_playlist(
            phase=2,
            spec=phase2_spec,
            favorite_tracks=phase2_favorite_tracks,
            discover_tracks=phase2_discover_tracks,
        )

        return playlist1, playlist2

    def _get_playlist_specs(self):
        """
        根據 experiment_group 取得兩個 phase 的規格

        Returns:
            tuple: (phase1_spec, phase2_spec)
            每個 spec 包含：
            {
                'phase': int,
                'length_type': str,
                'favorite_position_type': str,
                'total_tracks': int,
                'favorite_positions': list,
                'favorite_count': int,
                'discover_count': int,
            }
        """
        experiment_group = self.member.experiment_group

        # 根據 xxx_FIRST 決定 phase 1 和 phase 2 的配置
        if (
            experiment_group.playlist_length
            == ExperimentGroup.PlaylistLengthOptions.SHORT_FIRST
        ):
            phase1_length = Playlist.LengthOptions.SHORT
            phase2_length = Playlist.LengthOptions.LONG
        else:  # LONG_FIRST
            phase1_length = Playlist.LengthOptions.LONG
            phase2_length = Playlist.LengthOptions.SHORT

        if (
            experiment_group.favorite_track_position
            == ExperimentGroup.FavoriteTrackPositionOptions.EDGE_FIRST
        ):
            phase1_position = Playlist.FavoriteTrackPositionOptions.EDGE
            phase2_position = Playlist.FavoriteTrackPositionOptions.MIDDLE
        else:  # MIDDLE_FIRST
            phase1_position = Playlist.FavoriteTrackPositionOptions.MIDDLE
            phase2_position = Playlist.FavoriteTrackPositionOptions.EDGE

        # 建立 phase 1 規格
        phase1_total = PlaylistConfig.LENGTH_CONFIG[phase1_length]
        phase1_favorite_positions = PlaylistConfig.FAVORITE_POSITIONS[
            (phase1_length, phase1_position)
        ]
        phase1_favorite_count = len(phase1_favorite_positions)
        phase1_discover_count = phase1_total - phase1_favorite_count

        phase1_spec = {
            'phase': 1,
            'length_type': phase1_length,
            'favorite_position_type': phase1_position,
            'total_tracks': phase1_total,
            'favorite_positions': phase1_favorite_positions,
            'favorite_count': phase1_favorite_count,
            'discover_count': phase1_discover_count,
        }

        # 建立 phase 2 規格
        phase2_total = PlaylistConfig.LENGTH_CONFIG[phase2_length]
        phase2_favorite_positions = PlaylistConfig.FAVORITE_POSITIONS[
            (phase2_length, phase2_position)
        ]
        phase2_favorite_count = len(phase2_favorite_positions)
        phase2_discover_count = phase2_total - phase2_favorite_count

        phase2_spec = {
            'phase': 2,
            'length_type': phase2_length,
            'favorite_position_type': phase2_position,
            'total_tracks': phase2_total,
            'favorite_positions': phase2_favorite_positions,
            'favorite_count': phase2_favorite_count,
            'discover_count': phase2_discover_count,
        }

        return phase1_spec, phase2_spec

    def _get_source_playlists(self):
        """
        取得 MEMBER_FAVORITE 和 DISCOVER_WEEKLY playlist

        Returns:
            tuple: (favorite_playlist, discover_playlist)
        """
        favorite_playlist = Playlist.objects.get(
            member=self.member, type=Playlist.TypeOptions.MEMBER_FAVORITE
        )

        discover_playlist = Playlist.objects.get(
            member=self.member, type=Playlist.TypeOptions.DISCOVER_WEEKLY
        )

        return favorite_playlist, discover_playlist

    def _select_tracks_for_phases(
        self, source_playlist, phase1_required, phase2_required
    ):
        """
        從來源 playlist 選擇歌曲給兩個 phase

        Phase 1 優先取奇數 order (1,3,5...)
        Phase 2 優先取偶數 order (2,4,6...)

        為避免兩邊 order 範圍重疊：
        - 需要較少的那邊，先取它的優先 order，得到「分界點」
        - 需要較多的那邊，先取 order ≤ 分界點的另一種 order，再從分界點+1 開始連續取

        Args:
            source_playlist: Playlist instance
            phase1_required: Phase 1 需要的歌曲數量
            phase2_required: Phase 2 需要的歌曲數量

        Returns:
            tuple: (phase1_tracks, phase2_tracks)
        """
        # 取得所有歌曲，按 order 排序
        all_tracks = list(source_playlist.playlist_tracks.order_by('order'))
        all_tracks_by_order = {t.order: t for t in all_tracks}

        # 分成奇數和偶數
        odd_tracks = [t for t in all_tracks if t.order % 2 == 1]
        even_tracks = [t for t in all_tracks if t.order % 2 == 0]

        if phase1_required <= phase2_required:
            # Phase 1 需要較少，先讓 Phase 1 取奇數，得到分界點
            phase1_tracks = odd_tracks[:phase1_required]
            boundary = phase1_tracks[-1].order if phase1_tracks else 0

            # Phase 2 先取 order ≤ boundary 的偶數
            phase2_tracks = [t for t in even_tracks if t.order <= boundary]

            # Phase 2 剩餘從 boundary + 1 開始連續取
            remaining_needed = phase2_required - len(phase2_tracks)
            if remaining_needed > 0:
                start_order = boundary + 1
                for order in range(start_order, max(all_tracks_by_order.keys()) + 1):
                    if order in all_tracks_by_order:
                        phase2_tracks.append(all_tracks_by_order[order])
                        if len(phase2_tracks) >= phase2_required:
                            break
        else:
            # Phase 2 需要較少，先讓 Phase 2 取偶數，得到分界點
            phase2_tracks = even_tracks[:phase2_required]
            boundary = phase2_tracks[-1].order if phase2_tracks else 0

            # Phase 1 先取 order ≤ boundary 的奇數
            phase1_tracks = [t for t in odd_tracks if t.order <= boundary]

            # Phase 1 剩餘從 boundary + 1 開始連續取
            remaining_needed = phase1_required - len(phase1_tracks)
            if remaining_needed > 0:
                start_order = boundary + 1
                for order in range(start_order, max(all_tracks_by_order.keys()) + 1):
                    if order in all_tracks_by_order:
                        phase1_tracks.append(all_tracks_by_order[order])
                        if len(phase1_tracks) >= phase1_required:
                            break

        return phase1_tracks, phase2_tracks

    def _create_single_playlist(self, phase, spec, favorite_tracks, discover_tracks):
        """
        建立單一實驗歌單

        Args:
            phase: phase 編號（1 或 2）
            spec: 從 _get_playlist_specs 返回的 spec
            favorite_tracks: MEMBER_FAVORITE 的 PlaylistTrack 列表
            discover_tracks: DISCOVER_WEEKLY 的 PlaylistTrack 列表

        Returns:
            Playlist: 建立的實驗歌單
        """
        # 建立 Playlist
        playlist = Playlist.objects.create(
            member=self.member,
            type=Playlist.TypeOptions.EXPERIMENT,
            length_type=spec['length_type'],
            favorite_track_position_type=spec['favorite_position_type'],
            experiment_phase=phase,
            description=f"Experiment Playlist phase {phase}",
        )

        # 分配歌曲到對應位置
        self._assign_tracks_to_positions(
            playlist, spec, favorite_tracks, discover_tracks
        )

        return playlist

    def _assign_tracks_to_positions(
        self, playlist, spec, favorite_tracks, discover_tracks
    ):
        """
        將歌曲分配到指定位置

        Args:
            playlist: Playlist instance
            spec: 歌單規格
            favorite_tracks: MEMBER_FAVORITE 的 PlaylistTrack 列表
            discover_tracks: DISCOVER_WEEKLY 的 PlaylistTrack 列表
        """
        favorite_positions_set = set(spec['favorite_positions'])

        favorite_idx = 0
        discover_idx = 0

        # 遍歷所有位置（1-indexed）
        for position in range(1, spec['total_tracks'] + 1):
            if position in favorite_positions_set:
                # 這個位置應該放喜愛歌曲
                source_track = favorite_tracks[favorite_idx]
                is_favorite = True
                favorite_idx += 1
            else:
                # 這個位置應該放發現歌曲
                source_track = discover_tracks[discover_idx]
                is_favorite = False
                discover_idx += 1

            # 建立 PlaylistTrack
            PlaylistTrack.objects.create(
                playlist=playlist,
                track=source_track.track,
                order=position,
                is_favorite=is_favorite,
            )


class ExperimentDataValidationService:
    """驗證實驗數據完整性"""

    @staticmethod
    def validate_member(member, phase=None):
        """
        驗證單個成員的實驗歌單是否都已評分

        Args:
            member: Member instance
            phase: 可選，只驗證特定 phase (1 or 2)

        Returns:
            bool: True 表示資料完整，False 表示資料不完整
        """
        playlists = Playlist.objects.filter(
            member=member, type=Playlist.TypeOptions.EXPERIMENT
        )

        if phase:
            playlists = playlists.filter(experiment_phase=phase)

        # 檢查每個 phase 的歌單
        phases_to_check = [phase] if phase else [1, 2]

        for p in phases_to_check:
            playlist = playlists.filter(experiment_phase=p).first()

            if not playlist:
                return False

            # 檢查 playlist satisfaction_score
            if playlist.satisfaction_score is None:
                return False

            # 檢查所有 tracks 是否都有評分
            unrated = playlist.playlist_tracks.filter(
                satisfaction_score__isnull=True
            ) | playlist.playlist_tracks.filter(splendid_score__isnull=True)

            if unrated.exists():
                return False

        return True

    @staticmethod
    def validate_all_members(phase=None):
        """
        驗證所有成員的實驗歌單是否都已評分

        Args:
            phase: 可選，只驗證特定 phase (1 or 2)

        Returns:
            bool: True 表示所有成員資料都完整，False 表示有成員資料不完整
        """
        members = Member.objects.filter(experiment_group__isnull=False)

        for member in members:
            if not ExperimentDataValidationService.validate_member(member, phase=phase):
                return False

        return True
