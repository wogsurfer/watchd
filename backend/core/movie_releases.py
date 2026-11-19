"""Film release dates for the calendar: cinema, digital, streaming and disc,
picked from TMDB's per-country release dates."""

from datetime import date, timedelta

# TMDB release types.
_LIMITED, _THEATRICAL, _DIGITAL, _PHYSICAL = 2, 3, 4, 5

# Notes on digital releases that mean rental or purchase, not a streaming
# service.
_DIGITAL_NOTES = ("rental", "digital", "vod", "purchase", "itunes")

COUNTRY_NAMES = {"GB": "UK"}

# A cinema date this long after the film first opened in that country is a
# return to cinemas (a re-release or a new cut), even when TMDB's note
# doesn't say so. By country, as films often open months apart abroad.
BACK_IN_CINEMAS_AFTER = timedelta(days=42)


def release_countries(user_country: str | None) -> list[str]:
    """Countries to take dates from, best first: the user's own, then the UK
    and the US, which TMDB covers most fully."""
    countries = [c for c in (user_country, "GB", "US") if c]
    return list(dict.fromkeys(c.upper() for c in countries))


def _first_in_cinemas(releases: list) -> date | None:
    """The earliest limited or wide cinema release among a country's releases."""
    days = []
    for release in releases or []:
        if release.get("type") in (_LIMITED, _THEATRICAL):
            try:
                days.append(date.fromisoformat((release.get("release_date") or "")[:10]))
            except ValueError:
                pass
    return min(days, default=None)


def _kind_and_label(release: dict, first_cinema: date | None = None) -> tuple[str | None, str | None]:
    kind = release.get("type")
    note = (release.get("note") or "").strip()
    low = note.lower()
    if kind in (_LIMITED, _THEATRICAL):
        back = "re-release" in low or "rerelease" in low
        if not back and first_cinema:
            try:
                day = date.fromisoformat((release.get("release_date") or "")[:10])
                back = day - first_cinema > BACK_IN_CINEMAS_AFTER
            except ValueError:
                pass
        return "cinema", "Back in cinemas" if back else "In cinemas"
    if kind == _DIGITAL:
        if not note or any(word in low for word in _DIGITAL_NOTES):
            return "digital", "Digital"
        return "streaming", f"On {note}"
    if kind == _PHYSICAL:
        if "4k" in low:
            label = "4K Blu-ray"
        elif "blu" in low or not note:
            label = "Blu-ray"
        elif "dvd" in low:
            label = "DVD"
        else:
            label = "Blu-ray"
        if "criterion" in low:
            label = f"Criterion {label}"
        return "disc", label
    return None, None


def upcoming_releases(results: list, start: date, end: date, countries: list[str]) -> list[dict]:
    """Releases between start and end, one per kind (one per service for
    streaming). For each kind the first country in `countries` with a date in
    the window wins, and within a country the earliest date."""
    by_country = {e.get("iso_3166_1"): e.get("release_dates") or [] for e in results or []}
    picked: dict[tuple, dict] = {}
    for country in countries:
        best: dict[tuple, dict] = {}
        first_cinema = _first_in_cinemas(by_country.get(country, []))
        for release in by_country.get(country, []):
            kind, label = _kind_and_label(release, first_cinema)
            if not kind:
                continue
            try:
                day = date.fromisoformat((release.get("release_date") or "")[:10])
            except ValueError:
                continue
            if not start <= day <= end:
                continue
            key = (kind, label) if kind == "streaming" else (kind,)
            if key in picked:
                continue
            if key not in best or day < best[key]["date"]:
                best[key] = {"date": day, "kind": kind, "label": label, "country": country}
        picked.update(best)
    return sorted(picked.values(), key=lambda r: (r["date"], r["kind"]))
