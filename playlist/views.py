from dataclasses import asdict

from django.db import transaction
from rest_framework.decorators import action
from rest_framework.mixins import ListModelMixin, RetrieveModelMixin, UpdateModelMixin

from account.permissions import IsMember
from playlist.caches import SpotifyPlaylistOrderCache
from playlist.filters import PlaylistFilter
from playlist.models import Playlist, PlaylistTrack
from playlist.serializers import (
    PlaylistImportSerializer,
    PlaylistOrderCacheSerializer,
    PlaylistRatingSerializer,
    PlaylistSerializer,
    PlaylistTrackBatchRatingSerializer,
    PlaylistValidationSerializer,
)
from playlist.services import ExperimentDataValidationService
from provider.exceptions import ProviderException
from utils.constants import ResponseCode, ResponseMessage
from utils.response import APIFailedResponse, APISuccessResponse
from utils.views import BaseGenericViewSet


class PlaylistViewSet(
    ListModelMixin, RetrieveModelMixin, UpdateModelMixin, BaseGenericViewSet
):
    permission_classes = [IsMember]
    serializer_class = PlaylistSerializer
    filterset_class = PlaylistFilter

    def get_serializer_class(self):
        if self.action == 'partial_update':
            return PlaylistRatingSerializer
        return super().get_serializer_class()

    def get_queryset(self):
        member = self.request.user.member
        return (
            Playlist.objects.filter(member=member)
            .prefetch_related('playlist_tracks__track__artists')
            .order_by('-created_at')
        )

    @action(detail=False, methods=['post'], url_path='validate')
    def validate_external_playlist(self, request):
        """
        驗證 Spotify playlist 是否符合實驗要求

        Request Body:
        {
            "spotify_playlist_id": "spotify_playlist_id",
            "type": "member_favorite" or "discover_weekly"
        }

        Response:
        {
            "success": true,
            "data": {
                "is_valid": true/false,
                "track_count": 15,
                "required_minimum": 12,
                "playlist_type": "member_favorite",
                "tracks": [...],
                "validation_errors": []
            }
        }
        """
        try:
            serializer = PlaylistValidationSerializer(data=request.data)
            if not serializer.is_valid():
                return APIFailedResponse(
                    code=ResponseCode.VALIDATION_ERROR,
                    msg=ResponseMessage.VALIDATION_ERROR,
                    details=serializer.errors,
                )

            member = request.user.member
            provider = member.spotify_provider

            if not provider:
                raise ProviderException(
                    code=ResponseCode.NOT_FOUND,
                    message='No Spotify provider assigned to this member',
                )

            spotify_playlist_id = serializer.validated_data['spotify_playlist_id']
            playlist_type = serializer.validated_data['type']

            from provider.services import SpotifyPlaylistService

            service = SpotifyPlaylistService(provider, member)
            validation_result = service.validate_playlist(
                spotify_playlist_id, playlist_type
            )

            # 將 dataclass 轉成 dict
            return APISuccessResponse(data=asdict(validation_result))

        except ProviderException as e:
            return APIFailedResponse(code=e.code, msg=e.message, details=e.details)
        except Exception as e:
            return APIFailedResponse(
                code=ResponseCode.SERVER_ERROR,
                msg='Failed to validate playlist',
                details=str(e),
            )

    @action(detail=False, methods=['post'], url_path='import')
    def import_external_playlist(self, request):
        """
        匯入 Spotify playlist

        Request Body:
        {
            "spotify_playlist_id": "spotify_playlist_id",
            "type": "member_favorite" or "discover_weekly"
        }
        """
        try:
            serializer = PlaylistImportSerializer(data=request.data)
            if not serializer.is_valid():
                return APIFailedResponse(
                    code=ResponseCode.VALIDATION_ERROR,
                    msg=ResponseMessage.VALIDATION_ERROR,
                    details=serializer.errors,
                )

            member = request.user.member
            provider = member.spotify_provider

            if not provider:
                raise ProviderException(
                    code=ResponseCode.NOT_FOUND,
                    message='No Spotify provider assigned to this member',
                )

            spotify_playlist_id = serializer.validated_data['spotify_playlist_id']
            playlist_type = serializer.validated_data['type']

            # 使用 Service（業務入口）
            from provider.services import SpotifyPlaylistService

            service = SpotifyPlaylistService(provider, member)
            playlist = service.import_playlist(spotify_playlist_id, playlist_type)

            if not playlist:
                return APIFailedResponse(
                    code=ResponseCode.NOT_FOUND,
                    msg='No tracks found in the playlist or playlist not found',
                )

            data = {
                'playlist_id': playlist.id,
                'external_id': playlist.external_id,
                'type': playlist.type,
                'track_count': playlist.playlist_tracks.count(),
                'description': playlist.description,
                'created_at': playlist.created_at,
            }

            return APISuccessResponse(data=data)

        except ProviderException as e:
            return APIFailedResponse(code=e.code, msg=e.message, details=e.details)

    @action(detail=True, methods=['patch'], url_path='tracks/ratings')
    def update_tracks_ratings(self, request, pk=None):
        """
        批量更新 playlist 中所有歌曲的評分

        Request Body:
        {
            "ratings": [
                {
                    "playlist_track_id": 1,
                    "satisfaction_score": 5,
                    "splendid_score": 4
                },
                {
                    "playlist_track_id": 2,
                    "satisfaction_score": 3,
                    "splendid_score": 5
                }
            ]
        }
        """
        # 取得 playlist 並確認屬於當前 member
        playlist = self.get_object()

        # 驗證 request data（驗證邏輯在 serializer 中）
        serializer = PlaylistTrackBatchRatingSerializer(
            data=request.data, playlist=playlist
        )
        if not serializer.is_valid():
            return APIFailedResponse(
                code=ResponseCode.VALIDATION_ERROR,
                msg=ResponseMessage.VALIDATION_ERROR,
                details=serializer.errors,
            )

        ratings = serializer.validated_data['ratings']
        track_map = {
            pt.id: pt for pt in PlaylistTrack.objects.filter(playlist=playlist)
        }
        with transaction.atomic():
            tracks_to_update = []
            for rating_data in ratings:
                track_id = rating_data['playlist_track_id']
                playlist_track = track_map[track_id]

                playlist_track.is_ever_listened = rating_data['is_ever_listened']
                playlist_track.satisfaction_score = rating_data['satisfaction_score']
                playlist_track.splendid_score = rating_data['splendid_score']
                tracks_to_update.append(playlist_track)

            # 一次性批量更新（只產生一個 UPDATE query）
            PlaylistTrack.objects.bulk_update(
                tracks_to_update,
                ['is_ever_listened', 'satisfaction_score', 'splendid_score'],
            )

        return APISuccessResponse()

    @action(detail=False, methods=['get'], url_path='experiment/complete')
    def validate_experiment_data(self, request):
        """
        驗證自己的實驗歌單評分是否完整

        Response:
        - 200: 回傳兩個 phase 的完成狀態
        """
        member = request.user.member

        # 驗證兩個 phase 的資料
        phase1_complete = ExperimentDataValidationService.validate_member(
            member, phase=1
        )
        phase2_complete = ExperimentDataValidationService.validate_member(
            member, phase=2
        )

        return APISuccessResponse(
            data={
                'phase1': phase1_complete,
                'phase2': phase2_complete,
            }
        )

    @action(detail=False, methods=['post'], url_path='cache-order')
    def cache_playlist_order(self, request):
        """
        快取 Spotify playlist 的 track IDs 順序

        用於確保 validate 和 import 之間的資料一致性，因為spotify playlist 回傳的歌曲順序可能會不同

        Request Body:
        {
            "type": "member_favorite" or "discover_weekly",
            "track_ids": ["spotify_track_id_1", "spotify_track_id_2", ...]
        }

        Response:
        {
            "success": true,
            "data": {
                "cached": true,
                "track_count": 15
            }
        }
        """
        serializer = PlaylistOrderCacheSerializer(data=request.data)
        if not serializer.is_valid():
            return APIFailedResponse(
                code=ResponseCode.VALIDATION_ERROR,
                msg=ResponseMessage.VALIDATION_ERROR,
                details=serializer.errors,
            )

        member = request.user.member
        playlist_type = serializer.validated_data['type']
        track_ids = serializer.validated_data['track_ids']

        # 快取 track IDs
        SpotifyPlaylistOrderCache.set_track_ids(
            member_id=member.id,
            playlist_type=playlist_type,
            spotify_track_ids=track_ids,
        )

        return APISuccessResponse(
            data={
                'cached': True,
                'track_count': len(track_ids),
            }
        )
