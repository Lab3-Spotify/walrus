from dataclasses import dataclass
from datetime import datetime
from typing import Optional


class PlayLogSchemas:
    """HistoryPlayLog 相關的數據結構"""

    @dataclass
    class CreateData:
        """創建 HistoryPlayLog 所需的標準化數據"""

        track_external_id: str
        played_at: datetime
        context_type: Optional[str] = None  # 'playlist', 'album', 'artist'
        context_external_id: Optional[str] = None
