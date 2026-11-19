"""Premiere and finale labels for episodes, from TMDB's episode types."""

ENDED_STATUSES = {"ended", "canceled", "cancelled"}


def episode_badge(
    season_number: int | None,
    episode_number: int | None,
    episode_type: str | None,
    previous_type: str | None = None,
    show_status: str | None = None,
    last_season: int | None = None,
) -> str | None:
    """ "Series premiere", "Season premiere", "Mid-season premiere",
    "Mid-season finale", "Season finale" or "Series finale", or None.

    `episode_type` is TMDB's ("standard", "mid_season" or "finale"), which it
    sets once a finale is announced; `previous_type` is the previous
    episode's, so the episode after a mid-season finale is the mid-season
    premiere. A finale of a show that has ended is the series finale, but
    only in its last season (`last_season`, when known): TMDB marks every
    season's last episode a finale. Specials (season 0) get no label.
    """
    if not season_number or not episode_number:
        return None
    if episode_number == 1:
        return "Series premiere" if season_number == 1 else "Season premiere"
    if previous_type == "mid_season":
        return "Mid-season premiere"
    if episode_type == "mid_season":
        return "Mid-season finale"
    if episode_type == "finale":
        ended = (show_status or "").strip().lower() in ENDED_STATUSES
        if last_season and season_number < last_season:
            ended = False
        return "Series finale" if ended else "Season finale"
    return None


def last_season(show_data: dict | None) -> int | None:
    """The number of a TMDB show's last season (specials aside), or None."""
    numbers = [s.get("season_number") or 0 for s in (show_data or {}).get("seasons") or []]
    return max(numbers, default=0) or (show_data or {}).get("number_of_seasons") or None


# A break this long before the season's next episode makes the one before it
# a mid-season finale, when TMDB hasn't (or no longer) marked it.
MID_SEASON_GAP_DAYS = 28


def season_types(episodes: list[dict]) -> dict[int, str | None]:
    """TMDB's episode types for a season's episodes, by episode number, with a
    mid-season finale filled in before any break of four weeks or more."""
    from datetime import date

    ordered = sorted((e for e in episodes if e.get("episode_number")), key=lambda e: e["episode_number"])
    types = {e["episode_number"]: e.get("episode_type") for e in ordered}
    for this, nxt in zip(ordered, ordered[1:]):
        if types[this["episode_number"]] not in (None, "standard"):
            continue
        try:
            gap = (date.fromisoformat(nxt["air_date"][:10]) - date.fromisoformat(this["air_date"][:10])).days
        except (TypeError, ValueError, KeyError):
            continue
        if gap >= MID_SEASON_GAP_DAYS:
            types[this["episode_number"]] = "mid_season"
    return types


def schedule_types(tmdb_types: dict[int, str | None], air_dates: dict[int, str]) -> dict[int, str | None]:
    """A season's episode types checked against a schedule's air dates (every
    dated episode of the season, by number). TMDB's mid-season finale is
    dropped where the schedule has the next episode under four weeks later
    (TMDB can be out of date or numbered differently), and one is added
    before any break of four weeks or more."""
    from datetime import date

    numbers = sorted(set(air_dates) | set(tmdb_types))
    types = {n: tmdb_types.get(n) for n in numbers}
    dated = sorted(air_dates)
    for this, nxt in zip(dated, dated[1:]):
        if types.get(this) != "mid_season":
            continue
        try:
            gap = (date.fromisoformat(air_dates[nxt][:10]) - date.fromisoformat(air_dates[this][:10])).days
        except (TypeError, ValueError):
            continue
        if gap < MID_SEASON_GAP_DAYS:
            types[this] = "standard"
    return season_types([
        {"episode_number": n, "air_date": air_dates.get(n), "episode_type": types[n]} for n in numbers
    ])


def season_badges(season_data: dict, show_status: str | None = None, last: int | None = None) -> dict[int, str]:
    """Labels for the episodes of a TMDB season response, by episode number."""
    episodes = sorted(season_data.get("episodes") or [], key=lambda e: e.get("episode_number") or 0)
    types = season_types(episodes)
    badges = {}
    for e in episodes:
        number = e.get("episode_number")
        badge = episode_badge(
            e.get("season_number", season_data.get("season_number")),
            number,
            types.get(number),
            types.get(number - 1) if number else None,
            show_status,
            last,
        )
        if badge:
            badges[number] = badge
    return badges
