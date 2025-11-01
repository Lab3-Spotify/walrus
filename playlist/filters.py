import django_filters
from django import forms

from playlist.models import Playlist


class CommaSeparatedMultipleChoiceField(forms.MultipleChoiceField):
    """支援逗號分隔的多選欄位"""

    def to_python(self, value):
        """將逗號分隔的字串轉換為 list"""
        if not value:
            return []
        if isinstance(value, str):
            # 如果是逗號分隔的字串，分割它
            value = [v.strip() for v in value.split(',') if v.strip()]
        elif isinstance(value, (list, tuple)):
            # 如果已經是 list，檢查每個元素是否包含逗號
            result = []
            for item in value:
                if isinstance(item, str) and ',' in item:
                    result.extend([v.strip() for v in item.split(',') if v.strip()])
                else:
                    result.append(item)
            value = result
        return super().to_python(value)


class CommaSeparatedMultipleChoiceFilter(django_filters.MultipleChoiceFilter):
    """支援逗號分隔的多選過濾器"""

    field_class = CommaSeparatedMultipleChoiceField


class PlaylistFilter(django_filters.FilterSet):
    """Playlist 過濾器"""

    type = CommaSeparatedMultipleChoiceFilter(
        field_name='type',
        choices=Playlist.TypeOptions.choices,
        conjoined=False,  # 使用 OR 邏輯（只要符合其中一個即可）
        help_text='Filter by playlist types (comma-separated: experiment,discover_weekly,member_favorite)',
    )

    experiment_phase = django_filters.NumberFilter(
        field_name='experiment_phase',
        help_text='Filter by experiment phase (1 or 2)',
    )

    class Meta:
        model = Playlist
        fields = ['type', 'experiment_phase']
