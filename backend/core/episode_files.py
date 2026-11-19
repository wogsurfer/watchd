"""Which episodes share a file in the Emby library: a double episode such as
"S04E01-E02" is one file Emby lists once, as episode 1 to 2 (IndexNumberEnd).
Plays from Emby already record every episode in the file (see
routers/webhooks.py); this lets an episode marked by hand do the same."""

from __future__ import annotations

import time

from core.config import settings

_series: dict[int, tuple[float, str | None]] = {}  # TMDB id -> (when, Emby id)
_TTL = 6 * 3600


def episode_span(start: int, end) -> list[int]:
    """The episodes a file from [start] to [end] holds, when it's more than one
    and a sane count (2 to 10); otherwise just [start]."""
    if isinstance(end, int) and 1 <= end - start <= 9:
        return list(range(start, end + 1))
    return [start]


async def _emby_series_id(client, series_tmdb_id: int) -> str | None:
    hit = _series.get(series_tmdb_id)
    if hit and time.time() - hit[0] < _TTL:
        return hit[1]
    found = await client.get("/Items", Recursive="true", IncludeItemTypes="Series",
                             AnyProviderIdEquals=f"tmdb.{series_tmdb_id}")
    items = found.get("Items") or []
    sid = items[0]["Id"] if items else None
    _series[series_tmdb_id] = (time.time(), sid)
    return sid


async def file_mates(series_tmdb_id: int, season: int, episode: int) -> list[int]:
    """The other episode numbers in the same Emby file as this one, or []
    (also when Emby isn't set up or can't be reached)."""
    if not (settings.emby_server and settings.emby_api_key):
        return []
    try:
        from services.emby.client import EmbyClient

        client = EmbyClient()
        sid = await _emby_series_id(client, series_tmdb_id)
        if not sid:
            return []
        eps = await client.get(f"/Shows/{sid}/Episodes", Season=season)
        for item in eps.get("Items") or []:
            start = item.get("IndexNumber")
            if not isinstance(start, int):
                continue
            span = episode_span(start, item.get("IndexNumberEnd"))
            if episode in span and len(span) > 1:
                return [n for n in span if n != episode]
    except Exception as e:  # noqa: BLE001
        print(f"episode_files: couldn't ask Emby about {series_tmdb_id} S{season}E{episode}: {e}")
    return []
