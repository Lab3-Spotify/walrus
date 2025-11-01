"""
實驗歌單配置常數

歌單規則：
- SHORT: 10 首歌
- LONG: 20 首歌

喜愛歌曲位置（來自 MEMBER_FAVORITE playlist）：
- SHORT + EDGE: 位置 1, 2, 9, 10（共 4 首）
- SHORT + MIDDLE: 位置 4, 5, 6, 7（共 4 首）
- LONG + EDGE: 位置 1, 2, 3, 18, 19, 20（共 6 首）
- LONG + MIDDLE: 位置 8, 9, 10, 11, 12, 13（共 6 首）

歌曲分配策略：
- Phase 1 從來源 playlist 取奇數 order（1, 3, 5, 7...）
- Phase 2 從來源 playlist 取偶數 order（2, 4, 6, 8...），不足時連續取
- 確保每首歌最多只在兩個實驗歌單中出現一次，以平衡兩個歌單的喜愛程度

最少歌曲需求：
- MEMBER_FAVORITE: 至少 12 首（LONG 需要 6 首喜愛歌曲，取偶數 order 需要 2*6=12）
- DISCOVER_WEEKLY: 至少 20 首（LONG 扣除 MIDDLE 6 首，需要 14 首發現歌曲，取偶數 order 最多需要 20）
"""


class PlaylistConfig:
    """實驗歌單配置"""

    # 歌單長度配置
    LENGTH_CONFIG = {
        'short': 10,
        'long': 20,
    }

    # 喜愛歌曲位置配置 (1-indexed)
    # key: (length_type, favorite_position_type)
    # value: 喜愛歌曲應該出現的位置列表
    FAVORITE_POSITIONS = {
        ('short', 'edge'): [1, 2, 9, 10],
        ('short', 'middle'): [4, 5, 6, 7],
        ('long', 'edge'): [1, 2, 3, 18, 19, 20],
        ('long', 'middle'): [8, 9, 10, 11, 12, 13],
    }

    # 最少歌曲需求
    MIN_FAVORITE_TRACKS = 12
    MIN_DISCOVER_TRACKS = 20
