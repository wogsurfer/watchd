"""Collections Watchd puts together itself where TMDB splits a franchise up.

The Marvel Cinematic Universe is several TMDB collections (Iron Man,
Avengers, Thor...), with some films in none (Black Widow, Eternals). Here it
is one collection of every MCU feature film, in release order: the films TMDB
tags with its MCU keyword, leaving out the shorts, specials and making-of
documentaries that carry the tag too. It's shaped like a TMDB collection, so
film pages and the collection page use it as they would one of TMDB's.
"""

import time

from core import disk_cache, tmdb

# A collection id TMDB never uses (theirs are positive), for /collection/-1.
MCU_ID = -1
_MCU_KEYWORD = "180547"
_FRESH = 7 * 86400
_mcu: tuple[float, dict] | None = None


async def _fetch_mcu(tmdb_key: str | None) -> dict:
    films, page = [], 1
    while True:
        data = await tmdb._get(
            f"{tmdb.TMDB_BASE}/discover/movie", headers=tmdb.get_headers(tmdb_key),
            params={
                "with_keywords": _MCU_KEYWORD, "with_runtime.gte": 70, "without_genres": "99",
                "sort_by": "primary_release_date.asc", "page": page,
            },
        )
        films += data.get("results", [])
        if page >= min(data.get("total_pages", 1), 10):
            break
        page += 1
    # Undated films are only announcements; a dated one coming soon stays.
    films = [f for f in films if f.get("release_date")]
    avengers = next((f for f in films if f["id"] == 24428), None)
    return {
        "id": MCU_ID,
        "name": "Marvel Cinematic Universe",
        "overview": "Every film in the Marvel Cinematic Universe, in release order, from Iron Man to today.",
        "poster_path": (avengers or films[0]).get("poster_path") if films else None,
        "backdrop_path": (avengers or films[0]).get("backdrop_path") if films else None,
        "parts": films,
    }


async def mcu(tmdb_key: str | None) -> dict | None:
    """The MCU as one collection, refreshed weekly (a stale copy if TMDB is down)."""
    global _mcu
    if _mcu is None:
        hit = disk_cache.load("franchises", "mcu", float("inf"))
        if hit:
            _mcu = hit
    if _mcu is None or time.time() - _mcu[0] > _FRESH:
        try:
            fresh = await _fetch_mcu(tmdb_key)
            if fresh["parts"]:
                disk_cache.save("franchises", "mcu", fresh)
                _mcu = (time.time(), fresh)
        except Exception as e:
            print(f"MCU collection didn't refresh: {e!r}")
    return _mcu[1] if _mcu else None


async def collection_for(tmdb_id: int, tmdb_key: str | None) -> dict | None:
    """Watchd's own collection for this film, if it's in one."""
    data = await mcu(tmdb_key)
    if data and any(p["id"] == tmdb_id for p in data["parts"]):
        return data
    return None
