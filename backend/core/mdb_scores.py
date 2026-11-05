"""Rotten Tomatoes, Metacritic, Letterboxd and Roger Ebert scores for a
film, from MDBList. Each film's scores are kept on disk for two weeks, so
a page view costs at most one of the key's 1,000 daily lookups.

MDBList has no Rotten Tomatoes scores for some well-known films (Passengers,
Rogue One). OMDb fills in the critics' score for those when a key is set. It
has no audience score, so that's read from the film's Rotten Tomatoes page,
which MDBList does point to; if the page's layout changes, the score just
stays blank.
"""

import re

import httpx

from core import disk_cache
from core.config import settings

_TTL = 14 * 86400
# MDBList's names for them: critics and audience on Rotten Tomatoes (the
# audience score is "popcorn"), critics and users on Metacritic.
SOURCES = ("tomatoes", "popcorn", "metacritic", "metacriticuser", "letterboxd", "rogerebert")

_RT_PATH = re.compile(r"^/m/[\w-]+$")
_RT_AUDIENCE = re.compile(r'"audienceScore":\{[^{}]*?"scorePercent":"(\d+)%"')
_RT_CRITICS = re.compile(r'"criticsScore":\{[^{}]*?"scorePercent":"(\d+)%"')
_CRITICS_LEEWAY = 5


async def _omdb_tomatoes(imdb_id: str, api_key: str) -> tuple[bool, int | None]:
    """(whether OMDb answered, its Rotten Tomatoes critics' score if it has one)."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get("https://www.omdbapi.com/", params={"apikey": api_key, "i": imdb_id})
        if r.status_code != 200:
            # Out of lookups for today, or OMDb is down: try again next time.
            return False, None
        ratings = r.json().get("Ratings") or []
    except (httpx.HTTPError, ValueError):
        return False, None
    value = next((x.get("Value") for x in ratings if x.get("Source") == "Rotten Tomatoes"), None)
    try:
        return True, int(value.rstrip("%")) if value else None
    except ValueError:
        return True, None


def _audience_on_page(html: str, critics: float | None) -> int | None:
    """The page's audience score. MDBList's address can be another film's
    (Zootopia's goes to Zootopia 3's page), so where the critics' score is
    known, the page's has to agree with it, allowing for it having moved a bit."""
    audience = _RT_AUDIENCE.search(html)
    if not audience:
        return None
    if critics is not None:
        on_page = _RT_CRITICS.search(html)
        if not on_page or abs(int(on_page.group(1)) - critics) > _CRITICS_LEEWAY:
            return None
    return int(audience.group(1))


async def _rt_audience(path: str, critics: float | None) -> tuple[bool, int | None]:
    """(whether the page gave an answer, the audience score on it if any)."""
    try:
        async with httpx.AsyncClient(
            timeout=15, follow_redirects=True, headers={"User-Agent": "Watchd/1.0 (self-hosted film tracker)"},
        ) as client:
            r = await client.get(f"https://www.rottentomatoes.com{path}")
    except httpx.HTTPError:
        return False, None
    if r.status_code == 404:
        return True, None
    if r.status_code != 200:
        return False, None
    return True, _audience_on_page(r.text, critics)


async def _fill_tomatoes(out: dict) -> bool:
    """Ask OMDb for a critics' score MDBList lacks. True if out changed."""
    if "tomatoes" in out["scores"] or out.get("omdb_checked"):
        return False
    if not settings.omdb_api_key or not out.get("imdb_id"):
        return False
    answered, value = await _omdb_tomatoes(out["imdb_id"], settings.omdb_api_key)
    if not answered:
        return False
    out["omdb_checked"] = True
    if value is not None:
        out["scores"]["tomatoes"] = {"value": value, "votes": None}
    return True


async def _fill_audience(out: dict) -> bool:
    """Read an audience score MDBList lacks off the film's page. True if out changed."""
    if "popcorn" in out["scores"] or out.get("rt_checked"):
        return False
    path = out.get("rt_path")
    if not path or not _RT_PATH.match(path):
        return False
    critics = (out["scores"].get("tomatoes") or {}).get("value")
    answered, value = await _rt_audience(path, critics)
    if not answered:
        return False
    out["rt_checked"] = True
    if value is not None:
        out["scores"]["popcorn"] = {"value": value, "votes": None}
    return True


async def _lookup(tmdb_id: int, api_key: str) -> dict | None:
    """The film's scores from MDBList, or None if it can't say right now."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(f"https://api.mdblist.com/tmdb/movie/{tmdb_id}", params={"apikey": api_key})
    except httpx.HTTPError:
        return None
    if r.status_code != 200:
        # Out of lookups for today, or MDBList is down: try again next time.
        return None
    data = r.json()
    ratings = data.get("ratings") or []
    scores = {
        x["source"]: {"value": x.get("value"), "votes": x.get("votes")}
        for x in ratings
        if x.get("source") in SOURCES and x.get("value") is not None
    }
    rt_path = next((x.get("url") for x in ratings if x.get("source") == "popcorn" and x.get("url")), None)
    return {"scores": scores, "imdb_id": (data.get("ids") or {}).get("imdb"), "rt_path": rt_path}


async def film_scores(tmdb_id: int, api_key: str) -> dict | None:
    hit = disk_cache.load("mdb_scores", tmdb_id, _TTL)
    if hit:
        out, changed = hit[1], False
        # Saved before the page's address was kept: MDBList has it.
        if "popcorn" not in out["scores"] and "rt_path" not in out:
            fresh = await _lookup(tmdb_id, api_key)
            if fresh:
                out["rt_path"] = fresh["rt_path"]
                changed = True
    else:
        out = await _lookup(tmdb_id, api_key)
        if out is None:
            return None
        changed = True
    # Either may have been saved missing because its source couldn't be reached.
    changed = await _fill_tomatoes(out) or changed
    changed = await _fill_audience(out) or changed
    if changed:
        disk_cache.save("mdb_scores", tmdb_id, out)
    return out
