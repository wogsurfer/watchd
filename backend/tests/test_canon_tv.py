"""The TV canon: Emmy titles matched to the right series, and film and series
badges kept apart when their TMDB numbers are the same."""

from core import canon


def test_pick_show_prefers_the_exact_title_that_had_started():
    results = [
        {"id": 1, "name": "The Wonder Years", "first_air_date": "2021-09-22"},
        {"id": 2, "name": "The Wonder Years", "first_air_date": "1988-01-31"},
    ]
    assert canon.pick_show(results, "The Wonder Years", 1988)["id"] == 2


def test_pick_show_matches_ignoring_punctuation():
    results = [
        {"id": 5, "name": "Mash Up", "first_air_date": "1970-01-01"},
        {"id": 7, "name": "M*A*S*H", "first_air_date": "1972-09-17"},
    ]
    assert canon.pick_show(results, "M*A*S*H", 1974)["id"] == 7


def test_pick_show_falls_back_to_the_first_series_that_had_started():
    results = [
        {"id": 9, "name": "Later Show", "first_air_date": "2030-01-01"},
        {"id": 3, "name": "Something Else", "first_air_date": "1990-01-01"},
    ]
    assert canon.pick_show(results, "No Match", 1995)["id"] == 3
    assert canon.pick_show([], "Anything", 1995) is None


def test_film_and_series_badges_stay_apart(monkeypatch):
    monkeypatch.setattr(canon, "_lists", {
        "imdb-top-250": [{"tmdb_id": 1396, "rank": 1}],
        "imdb-top-250-tv": [{"tmdb_id": 1396, "rank": 1}],
    })
    canon._index()
    assert [b["slug"] for b in canon.badges(1396)] == ["imdb-top-250"]
    assert [b["slug"] for b in canon.badges(1396, "tv")] == ["imdb-top-250-tv"]
    monkeypatch.setattr(canon, "_lists", {})
    canon._index()
