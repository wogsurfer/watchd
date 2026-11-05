"""OMDb fills in a Rotten Tomatoes critics' score that MDBList lacks."""

import asyncio

import pytest

from core import mdb_scores


@pytest.fixture
def setup(monkeypatch):
    saved = {}
    calls = []
    answer = {"value": (True, 30)}

    async def omdb(imdb_id, key):
        calls.append(imdb_id)
        return answer["value"]

    async def nothing(*args):
        return None

    async def no_page(path, critics):
        return True, None

    monkeypatch.setattr(mdb_scores, "_omdb_tomatoes", omdb)
    # No test reaches the real MDBList or Rotten Tomatoes.
    monkeypatch.setattr(mdb_scores, "_lookup", nothing)
    monkeypatch.setattr(mdb_scores, "_rt_audience", no_page)
    monkeypatch.setattr(mdb_scores.settings, "omdb_api_key", "key")
    monkeypatch.setattr(mdb_scores.disk_cache, "save", lambda ns, k, v: saved.update({k: v}))
    return saved, calls, answer


@pytest.fixture
def page(monkeypatch):
    paths = []
    answer = {"value": (True, 63)}

    async def read(path, critics):
        paths.append(path)
        return answer["value"]

    monkeypatch.setattr(mdb_scores, "_rt_audience", read)
    return paths, answer


def test_a_missing_audience_score_is_read_from_the_page(setup, page, monkeypatch):
    saved, _, _ = setup
    paths, _ = page
    _cached(monkeypatch, _gap(rt_path="/m/passengers_2016"))
    out = asyncio.run(mdb_scores.film_scores(1, "mdb"))
    assert out["scores"]["popcorn"] == {"value": 63, "votes": None}
    assert paths == ["/m/passengers_2016"]
    assert saved[1]["rt_checked"] is True


def test_mdblists_own_audience_score_wins(setup, page, monkeypatch):
    paths, _ = page
    own = {"value": 94, "votes": 173380}
    _cached(monkeypatch, {"scores": {"tomatoes": {"value": 94}, "popcorn": own}, "imdb_id": "tt1", "rt_path": "/m/x"})
    assert asyncio.run(mdb_scores.film_scores(1, "mdb"))["scores"]["popcorn"] == own
    assert paths == []


def test_a_page_with_no_score_is_only_read_once(setup, page, monkeypatch):
    paths, answer = page
    answer["value"] = (True, None)
    _cached(monkeypatch, _gap(rt_path="/m/x"))
    asyncio.run(mdb_scores.film_scores(1, "mdb"))
    asyncio.run(mdb_scores.film_scores(1, "mdb"))
    assert paths == ["/m/x"]


def test_a_page_that_cant_be_reached_is_tried_again(setup, page, monkeypatch):
    paths, answer = page
    answer["value"] = (False, None)
    _cached(monkeypatch, _gap(rt_path="/m/x", omdb_checked=True))
    asyncio.run(mdb_scores.film_scores(1, "mdb"))
    asyncio.run(mdb_scores.film_scores(1, "mdb"))
    assert len(paths) == 2


def test_an_address_that_isnt_a_film_page_is_never_read(setup, page, monkeypatch):
    paths, _ = page
    _cached(monkeypatch, _gap(rt_path="https://elsewhere.example/m/x"))
    out = asyncio.run(mdb_scores.film_scores(1, "mdb"))
    assert "popcorn" not in out["scores"]
    assert paths == []


def test_an_old_cached_film_gets_the_address_from_mdblist(setup, page, monkeypatch):
    paths, _ = page

    async def lookup(tmdb_id, key):
        return {"scores": {}, "imdb_id": "tt1", "rt_path": "/m/passengers_2016"}

    monkeypatch.setattr(mdb_scores, "_lookup", lookup)
    _cached(monkeypatch, _gap())
    out = asyncio.run(mdb_scores.film_scores(1, "mdb"))
    assert out["scores"]["popcorn"]["value"] == 63
    assert paths == ["/m/passengers_2016"]


PAGE = '"audienceScore":{"averageRating":"3.5","certified":false,"scorePercent":"63%","title":"Popcornmeter"},"criticsScore":{"scorePercent":"30%"}'


def test_the_score_is_found_in_the_pages_data():
    assert mdb_scores._audience_on_page(PAGE, 30) == 63


def test_a_page_with_a_different_critics_score_is_another_film():
    assert mdb_scores._audience_on_page(PAGE, 98) is None


def test_a_critics_score_thats_moved_a_little_is_still_the_same_film():
    assert mdb_scores._audience_on_page(PAGE, 33) == 63


def test_a_page_with_no_critics_score_cant_be_confirmed():
    only = '"audienceScore":{"scorePercent":"63%"},"criticsScore":{"title":"Tomatometer"}'
    assert mdb_scores._audience_on_page(only, 98) is None


def test_with_no_critics_score_known_theres_nothing_to_compare():
    assert mdb_scores._audience_on_page(PAGE, None) == 63


def _cached(monkeypatch, value):
    monkeypatch.setattr(mdb_scores.disk_cache, "load", lambda ns, k, ttl: (0.0, value))


def _gap(**extra):
    return {"scores": {"metacritic": {"value": 41, "votes": 48}}, "imdb_id": "tt1355644", **extra}


def test_a_cached_gap_is_filled_and_saved(setup, monkeypatch):
    saved, calls, _ = setup
    _cached(monkeypatch, _gap())
    out = asyncio.run(mdb_scores.film_scores(274870, "mdb"))
    assert out["scores"]["tomatoes"] == {"value": 30, "votes": None}
    assert out["scores"]["metacritic"]["value"] == 41
    assert saved[274870] is out
    assert calls == ["tt1355644"]


def test_mdblists_own_score_wins(setup, monkeypatch):
    _, calls, _ = setup
    own = {"value": 85, "votes": 200}
    _cached(monkeypatch, {"scores": {"tomatoes": own}, "imdb_id": "tt1"})
    out = asyncio.run(mdb_scores.film_scores(1, "mdb"))
    assert out["scores"]["tomatoes"] == own
    assert calls == []


def test_a_film_omdb_has_no_score_for_is_only_asked_about_once(setup, monkeypatch):
    saved, calls, answer = setup
    answer["value"] = (True, None)
    value = _gap()
    _cached(monkeypatch, value)
    asyncio.run(mdb_scores.film_scores(1, "mdb"))
    asyncio.run(mdb_scores.film_scores(1, "mdb"))
    assert calls == ["tt1355644"]
    assert saved[1]["omdb_checked"] is True
    assert "tomatoes" not in value["scores"]


def test_omdb_being_out_of_lookups_is_tried_again(setup, monkeypatch):
    saved, calls, answer = setup
    answer["value"] = (False, None)
    _cached(monkeypatch, _gap())
    asyncio.run(mdb_scores.film_scores(1, "mdb"))
    asyncio.run(mdb_scores.film_scores(1, "mdb"))
    assert len(calls) == 2
    assert saved == {}


def test_no_omdb_key_leaves_the_gap(setup, monkeypatch):
    _, calls, _ = setup
    monkeypatch.setattr(mdb_scores.settings, "omdb_api_key", None)
    _cached(monkeypatch, _gap())
    out = asyncio.run(mdb_scores.film_scores(1, "mdb"))
    assert "tomatoes" not in out["scores"]
    assert calls == []
