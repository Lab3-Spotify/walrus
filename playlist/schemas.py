from dataclasses import dataclass
from typing import List, Optional


class PlaylistSchemas:
    """Playlist 相關的數據結構"""

    @dataclass
    class TrackInfo:
        """歌曲信息（用於驗證和顯示）"""

        order: int
        name: str
        artists: List[str]  # Artist 名稱列表
        external_id: str
        image_url: Optional[str] = None
        is_duplicated: bool = False

    @dataclass
    class ValidationResult:
        """歌單驗證結果"""

        is_valid: bool
        track_count: int  # 總歌曲數
        valid_track_count: int  # 有效歌曲數（不重複）
        required_minimum: int  # 最低要求數量
        playlist_type: str  # 'member_favorite' 或 'discover_weekly'
        tracks: List['PlaylistSchemas.TrackInfo']
        validation_errors: List[str]  # 驗證錯誤信息
