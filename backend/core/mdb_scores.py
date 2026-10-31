"""Rotten Tomatoes, Metacritic, Letterboxd and Roger Ebert scores for a
film, from MDBList. Each film's scores are kept on disk for two weeks, so
a page view costs at most one of the key's 1,000 daily lookups.
"""

import httpx

from core import disk_cache

_TTL = 14 * 86400
# MDBList's names for them: critics and audience on Rotten Tomatoes (the
# audience score is "popcorn"), critics and users on Metacritic.
SOURCES = ("tomatoes", "popcorn", "metacritic", "metacriticuser", "letterboxd", "rogerebert")


async def film_scores(tmdb_id: int, api_key: str) -> dict | None:
    hit = disk_cache.load("mdb_scores", tmdb_id, _TTL)
    if hit:
        return hit[1]
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(f"https://api.mdblist.com/tmdb/movie/{tmdb_id}", params={"apikey": api_key})
    except httpx.HTTPError:
        return None
    if r.status_code != 200:
        # Out of lookups for today, or MDBList is down: try again next time.
        return None
    data = r.json()
    scores = {
        x["source"]: {"value": x.get("value"), "votes": x.get("votes")}
        for x in data.get("ratings") or []
        if x.get("source") in SOURCES and x.get("value") is not None
    }
    out = {"scores": scores, "imdb_id": (data.get("ids") or {}).get("imdb")}
    disk_cache.save("mdb_scores", tmdb_id, out)
    return out
