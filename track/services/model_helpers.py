from provider.models import Provider
from track.models import Genre


def bulk_create_genres(genre_dicts, provider_id):
    """
    批次將 genre_dicts 插入 DB，並回傳 {name: Genre instance} 的 mapping。
    genre_dicts: List[dict]，每個 dict 至少有 name，可選 category
    """
    if not genre_dicts:
        return {}

    provider = Provider.objects.get(id=provider_id)

    genre_name_set = set(g['name'] for g in genre_dicts if 'name' in g)

    existing_genres = Genre.objects.filter(name__in=genre_name_set, provider=provider)
    genre_map = {g.name: g for g in existing_genres}

    new_genre_dicts = [g for g in genre_dicts if g['name'] not in genre_map]
    new_genres = [
        Genre(name=g['name'], category=g.get('category', None), provider=provider)
        for g in new_genre_dicts
    ]
    if new_genres:
        Genre.objects.bulk_create(new_genres, ignore_conflicts=True)
        genre_map.update(
            {
                g.name: g
                for g in Genre.objects.filter(
                    name__in=[g['name'] for g in new_genre_dicts], provider=provider
                )
            }
        )

    return genre_map
