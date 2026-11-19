"""The canon: well-known "must see" lists of films and of TV series, to track
how much of each you've seen and to badge a film or show page with the lists
it's on.

The lists come from MDBList (kept up to date by their curators) and, for
Best Picture and the Emmy series winners, from the award data Watchd already
has. Each list is saved on disk for a week; posters missing from Watchd's own
library are filled in from TMDB once and kept with it.
"""

import asyncio
import re
import time

import httpx

from core import award_data, disk_cache, tmdb

LISTS = [
    {"slug": "imdb-top-250", "name": "IMDb Top 250", "ranked": True, "mdblist": 101881,
     "blurb": "The 250 highest-rated films on IMDb, as voted by its users."},
    {"slug": "best-picture", "name": "Best Picture", "ranked": False, "oscars": True,
     "blurb": "Every winner of the Academy Award for Best Picture."},
    {"slug": "afi-100", "name": "AFI's 100 Years... 100 Movies", "ranked": True, "mdblist": 214225,
     "blurb": "The American Film Institute's 100 greatest American films."},
    {"slug": "sight-and-sound", "name": "Sight and Sound Greatest Films", "ranked": True, "mdblist": 214226,
     "blurb": "The 2022 critics' poll of the greatest films of all time."},
    {"slug": "1001-movies", "name": "1001 Movies You Must See Before You Die", "ranked": False, "mdblist": 85771,
     "blurb": "The book's running list of essential films, every edition."},
    {"slug": "imdb-top-250-tv", "name": "IMDb Top 250 TV", "ranked": True, "mdblist": 101882, "kind": "tv",
     "blurb": "The highest-rated TV series on IMDb, as voted by its users."},
    {"slug": "emmy-drama", "name": "Emmy Outstanding Drama Series", "ranked": False, "emmys": "drama", "kind": "tv",
     "blurb": "Every series to win the Primetime Emmy for Outstanding Drama Series, since 1966."},
    {"slug": "emmy-comedy", "name": "Emmy Outstanding Comedy Series", "ranked": False, "emmys": "comedy", "kind": "tv",
     "blurb": "Every series to win the Primetime Emmy for Outstanding Comedy Series, since 1966."},
]
for _c in LISTS:
    _c.setdefault("kind", "movie")
BY_SLUG = {c["slug"]: c for c in LISTS}

_FRESH = 7 * 86400
_lists: dict[str, list[dict]] = {}
_saved_at: dict[str, float] = {}
_refreshing: dict[str, asyncio.Task] = {}
_by_film: dict[tuple[str, int], list[dict]] = {}


def _index() -> None:
    global _by_film
    out: dict[tuple[str, int], list[dict]] = {}
    for c in LISTS:
        for item in _lists.get(c["slug"], []):
            out.setdefault((c["kind"], item["tmdb_id"]), []).append(
                {"slug": c["slug"], "name": c["name"], "rank": item.get("rank") if c["ranked"] else None}
            )
    _by_film = out


async def _mdblist_items(list_id: int, api_key: str) -> list[dict]:
    items, cursor = [], None
    async with httpx.AsyncClient(timeout=30) as client:
        for _ in range(20):
            params = {"apikey": api_key, "limit": 500}
            if cursor:
                params["cursor"] = cursor
            r = await client.get(f"https://api.mdblist.com/lists/{list_id}/items", params=params)
            r.raise_for_status()
            data = r.json()
            rows = (data.get("movies", []) + data.get("shows", [])) if isinstance(data, dict) else data
            for m in rows:
                tmdb_id = (m.get("ids") or {}).get("tmdb") or m.get("id")
                if tmdb_id:
                    items.append({"tmdb_id": int(tmdb_id), "title": m.get("title"),
                                  "year": m.get("release_year"), "rank": m.get("rank")})
            cursor = r.headers.get("x-next-cursor")
            if r.headers.get("x-has-more") != "true" or not cursor:
                break
    # The lists come in order, but some number them in steps of 1,000.
    for place, item in enumerate(items, start=1):
        item["rank"] = place
    return items


async def _best_picture(tmdb_key: str | None) -> list[dict]:
    if not await award_data.ensure_loaded():
        return []
    winners = [
        r for r in award_data._records
        if r["award"] == award_data.OSCARS and r["category"] == "Best Picture" and r["winner"]
    ]
    items = []
    for r in sorted(winners, key=lambda r: r["year"]):
        work = next((w for w in r["works"] if w.get("imdb")), None)
        if not work:
            continue
        try:
            found = await tmdb.find_by_external_id(work["imdb"], "imdb_id", api_key=tmdb_key)
        except Exception:
            continue
        movie = (found.get("movie_results") or [None])[0]
        if movie:
            items.append({"tmdb_id": movie["id"], "title": movie.get("title") or work["title"],
                          "year": int((movie.get("release_date") or "0")[:4]) or None, "rank": None,
                          "poster_path": tmdb.poster_url(movie.get("poster_path"), size="w342"),
                          "ceremony": r["year"]})
    return items


# The Emmy series categories over the years, from 1966 when they settled.
_EMMY_CATEGORIES = {
    "drama": {"Outstanding Drama Series", "Outstanding Dramatic Series", "Outstanding Series - Drama",
              "Outstanding Series – Drama", "Outstanding Drama Series - Continuing"},
    "comedy": {"Outstanding Comedy Series", "Outstanding Series - Comedy", "Outstanding Series – Comedy"},
}


def _plain(title: str | None) -> str:
    return re.sub(r"[^a-z0-9]", "", (title or "").lower().replace("&", "and"))


def pick_show(results: list[dict], title: str, by_year: int) -> dict | None:
    """The TMDB series an award title means: one that had started by the
    ceremony, the exact title first, else the best-known such series."""
    started = [r for r in results if (r.get("first_air_date") or "9999")[:4] <= str(by_year)]
    exact = [r for r in started if _plain(title) in (_plain(r.get("name")), _plain(r.get("original_name")))]
    return (exact or started or [None])[0]


async def _emmy_winners(which: str, tmdb_key: str | None) -> list[dict]:
    if not await award_data.ensure_loaded():
        return []
    wins: dict[str, list[int]] = {}
    for r in award_data._records:
        if r["award"] == award_data.EMMYS and r["winner"] and r["category"] in _EMMY_CATEGORIES[which] and r["year"]:
            wins.setdefault(r["works"][0]["title"], []).append(r["year"])
    items, seen = [], set()
    for title, years in sorted(wins.items(), key=lambda kv: min(kv[1])):
        try:
            found = await tmdb.search_shows(title, api_key=tmdb_key)
        except Exception:
            continue
        show = pick_show(found.get("results") or [], title, min(years))
        if not show or show["id"] in seen:
            continue
        seen.add(show["id"])
        items.append({"tmdb_id": show["id"], "title": show.get("name") or title,
                      "year": int((show.get("first_air_date") or "0")[:4]) or None, "rank": None,
                      "poster_path": tmdb.poster_url(show.get("poster_path"), size="w342"),
                      "wins": sorted(set(years))})
    return items


async def _fill_posters(items: list[dict], tmdb_key: str | None, kind: str = "movie") -> None:
    """Posters for titles Watchd doesn't have yet, so a list page shows them all."""
    sem = asyncio.Semaphore(8)

    async def one(item):
        async with sem:
            try:
                if kind == "tv":
                    movie = await tmdb.get_show_light(item["tmdb_id"], api_key=tmdb_key)
                else:
                    movie = await tmdb.get_movie(item["tmdb_id"], api_key=tmdb_key)
                item["poster_path"] = tmdb.poster_url(movie.get("poster_path"), size="w342")
            except Exception:
                pass

    await asyncio.gather(*(one(i) for i in items if not i.get("poster_path")))


async def _refresh(slug: str, mdblist_key: str | None, tmdb_key: str | None) -> None:
    c = BY_SLUG[slug]
    try:
        if c.get("oscars"):
            items = await _best_picture(tmdb_key)
        elif c.get("emmys"):
            items = await _emmy_winners(c["emmys"], tmdb_key)
        elif mdblist_key:
            items = await _mdblist_items(c["mdblist"], mdblist_key)
        else:
            return
    except Exception as e:
        print(f"Canon list {slug} didn't refresh: {e!r}")
        return
    if not items:
        return
    known = {i["tmdb_id"]: i.get("poster_path") for i in _lists.get(slug, [])}
    for i in items:
        i.setdefault("poster_path", known.get(i["tmdb_id"]))
    await _fill_posters(items, tmdb_key, c["kind"])
    disk_cache.save("canon", slug, items)
    _lists[slug], _saved_at[slug] = items, time.time()
    _index()


async def ensure_loaded(mdblist_key: str | None, tmdb_key: str | None, wait: bool = False) -> None:
    """Load every list from disk; fetch any that are missing or a week old in
    the background (or, with wait, the missing ones before returning)."""
    for c in LISTS:
        slug = c["slug"]
        if slug not in _lists:
            hit = await asyncio.to_thread(disk_cache.load, "canon", slug, float("inf"))
            if hit:
                _saved_at[slug], _lists[slug] = hit
                if c["ranked"]:
                    for place, item in enumerate(_lists[slug], start=1):
                        item["rank"] = place
        stale = time.time() - _saved_at.get(slug, 0) > _FRESH
        running = _refreshing.get(slug)
        if stale and (running is None or running.done()):
            _refreshing[slug] = asyncio.create_task(_refresh(slug, mdblist_key, tmdb_key))
    _index()
    if wait:
        missing = [t for s, t in _refreshing.items() if s not in _lists and not t.done()]
        if missing:
            await asyncio.wait(missing, timeout=60)


def items(slug: str) -> list[dict]:
    return _lists.get(slug, [])


def badges(tmdb_id: int | None, kind: str = "movie") -> list[dict]:
    """The canon lists a film (or, with kind "tv", a series) is on, with its
    place where the list is ranked."""
    return list(_by_film.get((kind, tmdb_id), [])) if tmdb_id else []
