"""Reads a Trakt data export (the ZIP of JSON files from Trakt's Settings →
Data → Export) so the Trakt sync can import it without the Trakt API.

Trakt's export files hold the same items its API returns, but the file
names aren't documented and big histories are split across numbered files
("watched-movies-1.json", "-2" ...). So each item is recognised by its
shape, not by which file it came from:

- a play:            {"watched_at", "movie"} or {"watched_at", "episode", "show"}
- a rating:          {"rated_at", "rating", "type", "movie"/"show"/"season"}
- a watched title:   {"last_watched_at", "movie"} or {"show", "seasons": [...]}
                     (used only for titles with no individual plays)
- a list entry:      {"listed_at", "type", "movie"/"show"}; in a file named
                     like "watchlist" it goes on the watchlist, otherwise on
                     the list the file is for
- a list:            {"name", "ids": {"slug"}} (names the list files)

TraktExport offers the same calls the sync makes on core.trakt, so
run_trakt_sync can take one in its place.
"""

from __future__ import annotations

import io
import json
import re
import zipfile
from pathlib import PurePosixPath

MAX_EXPORT_BYTES = 300_000_000  # unzipped JSON, all files together


class TraktExportError(ValueError):
    """The upload isn't a Trakt export Watchd can read."""


def _stem(name: str) -> str:
    """'trakt/lists-my-faves-2.json' -> 'lists-my-faves'."""
    stem = PurePosixPath(name.replace("\\", "/")).stem.lower()
    return re.sub(r"[-_ ]\d+$", "", stem)


def _items(data) -> list[dict]:
    """The item dicts in a file: a list of them, or lists inside an object."""
    if isinstance(data, list):
        return [d for d in data if isinstance(d, dict)]
    if isinstance(data, dict):
        out = []
        for v in data.values():
            if isinstance(v, list):
                out += [d for d in v if isinstance(d, dict)]
        return out
    return []


def _tmdb(obj) -> int | None:
    if not isinstance(obj, dict):
        return None
    tid = (obj.get("ids") or {}).get("tmdb")
    return tid if isinstance(tid, int) else None


class TraktExport:
    def __init__(self, files: list[tuple[str, object]]):
        self.history_movies: list[dict] = []
        self.history_episodes: list[dict] = []
        self.ratings: dict[str, list[dict]] = {"movies": [], "shows": [], "seasons": []}
        self.watchlist: list[dict] = []
        self._list_meta: dict[str, dict] = {}            # slug -> list
        self._list_files: dict[str, list[dict]] = {}     # file stem -> entries
        watched_movies: list[dict] = []
        watched_shows: list[dict] = []
        seen_plays: set = set()
        seen_ratings: set = set()
        seen_listed: set = set()

        for name, data in files:
            stem = _stem(name)
            for item in _items(data):
                if item.get("watched_at") and (item.get("movie") or item.get("episode")):
                    key = item.get("id") or (
                        _tmdb(item.get("movie")) or _tmdb(item.get("show")),
                        (item.get("episode") or {}).get("season"),
                        (item.get("episode") or {}).get("number"),
                        item["watched_at"],
                    )
                    if key in seen_plays:
                        continue
                    seen_plays.add(key)
                    if item.get("movie"):
                        self.history_movies.append(item)
                    elif item.get("show"):
                        self.history_episodes.append(item)
                elif "rating" in item and item.get("rated_at"):
                    kind = {"movie": "movies", "show": "shows", "season": "seasons"}.get(item.get("type"))
                    if not kind:
                        continue  # episode ratings aren't imported (nor by the live sync)
                    target = item.get(item["type"]) or {}
                    key = (kind, _tmdb(item.get("movie") or item.get("show")), target.get("number"))
                    if key in seen_ratings:
                        continue
                    seen_ratings.add(key)
                    self.ratings[kind].append(item)
                elif item.get("listed_at") and item.get("type") in ("movie", "show"):
                    key = (stem if "watchlist" not in stem else "watchlist", item["type"], _tmdb(item.get(item["type"])))
                    if key in seen_listed:
                        continue
                    seen_listed.add(key)
                    if "watchlist" in stem:
                        self.watchlist.append(item)
                    else:
                        self._list_files.setdefault(stem, []).append(item)
                elif item.get("last_watched_at") and item.get("movie"):
                    watched_movies.append(item)
                elif item.get("show") and isinstance(item.get("seasons"), list):
                    watched_shows.append(item)
                elif item.get("name") and (item.get("ids") or {}).get("slug"):
                    self._list_meta[item["ids"]["slug"]] = item
                    for entry in item.get("items") or []:
                        if isinstance(entry, dict) and entry.get("type") in ("movie", "show"):
                            self._list_files.setdefault(f"list:{item['ids']['slug']}", []).append(entry)

        self._add_unplayed_watched(watched_movies, watched_shows)

    def _add_unplayed_watched(self, watched_movies: list[dict], watched_shows: list[dict]) -> None:
        """Titles marked watched with no individual plays in the export get
        one play on their last-watched date, so they still count."""
        played_movies = {_tmdb(p.get("movie")) for p in self.history_movies}
        for w in watched_movies:
            if _tmdb(w.get("movie")) not in played_movies:
                self.history_movies.append({"watched_at": w["last_watched_at"], "type": "movie", "movie": w["movie"]})
        played_eps = {
            (_tmdb(p.get("show")), (p.get("episode") or {}).get("season"), (p.get("episode") or {}).get("number"))
            for p in self.history_episodes
        }
        for w in watched_shows:
            show_id = _tmdb(w.get("show"))
            for season in w["seasons"]:
                for ep in season.get("episodes") or []:
                    key = (show_id, season.get("number"), ep.get("number"))
                    if key in played_eps or not ep.get("last_watched_at"):
                        continue
                    self.history_episodes.append({
                        "watched_at": ep["last_watched_at"], "type": "episode", "show": w["show"],
                        "episode": {"season": season.get("number"), "number": ep.get("number")},
                    })

    # ── What the sync calls on core.trakt ──────────────────────────────────

    async def validate_token(self, *_args) -> bool:
        return True

    async def get_history_movies(self, *_args, **_kwargs) -> list[dict]:
        return self.history_movies

    async def get_history_episodes(self, *_args, **_kwargs) -> list[dict]:
        return self.history_episodes

    async def get_ratings(self, *_args) -> dict:
        return self.ratings

    async def get_watchlist(self, *_args) -> list[dict]:
        return self.watchlist

    async def get_user_lists(self, *_args) -> list[dict]:
        lists = []
        for stem in self._list_files:
            if stem.startswith("list:"):
                meta = self._list_meta[stem[5:]]
                lists.append({"name": meta["name"], "description": meta.get("description"), "ids": {"slug": stem}})
                continue
            meta = next((m for slug, m in self._list_meta.items() if slug in stem), None)
            name = meta["name"] if meta else re.sub(r"^lists?[-_]", "", stem).replace("-", " ").replace("_", " ").strip().title()
            lists.append({"name": name or stem, "description": (meta or {}).get("description"), "ids": {"slug": f"export:{stem}"}})
        return lists

    async def get_list_items(self, _client_id, _token, list_slug: str) -> list[dict]:
        stem = list_slug[len("export:"):] if list_slug.startswith("export:") else list_slug
        return self._list_files.get(stem, [])

    def summary(self) -> dict:
        return {
            "movie_plays": len(self.history_movies),
            "episode_plays": len(self.history_episodes),
            "ratings": sum(len(v) for v in self.ratings.values()),
            "watchlist": len(self.watchlist),
            "lists": len(self._list_files),
        }


def read_export(filename: str, data: bytes) -> TraktExport:
    """A TraktExport from an uploaded ZIP or single JSON file."""
    files: list[tuple[str, object]] = []
    if (filename or "").lower().endswith(".json"):
        try:
            files.append((filename, json.loads(data)))
        except ValueError:
            raise TraktExportError("That JSON file couldn't be read.")
    else:
        try:
            zf = zipfile.ZipFile(io.BytesIO(data))
        except zipfile.BadZipFile:
            raise TraktExportError("Please choose the ZIP file Trakt emailed you, or one of the JSON files in it.")
        total = 0
        with zf:
            for info in zf.infolist():
                if info.is_dir() or not info.filename.lower().endswith(".json"):
                    continue
                total += info.file_size
                if total > MAX_EXPORT_BYTES:
                    raise TraktExportError("The export is too big to import in one go.")
                try:
                    files.append((info.filename, json.loads(zf.read(info))))
                except ValueError:
                    continue  # not JSON after all: skip it
    export = TraktExport(files)
    if not any(export.summary().values()):
        raise TraktExportError("No watch history, ratings or lists were found in that file.")
    return export
