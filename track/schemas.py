from dataclasses import dataclass
from typing import List, Optional


class ArtistSchemas:
    """Artist 相關的資料結構"""

    @dataclass
    class CreateData:
        """創建 Artist 所需的標準化資料"""

        external_id: str
        name: str
        popularity: Optional[int] = None
        followers_count: Optional[int] = None


class TrackSchemas:
    """Track 相關的資料結構"""

    @dataclass
    class CreateData:
        """創建 Track 所需的標準化資料"""

        external_id: str
        name: str
        artist_external_ids: List[str]  # Artist 的 external_id 列表
        popularity: Optional[int] = None
        is_playable: bool = True
        isrc: Optional[str] = None
