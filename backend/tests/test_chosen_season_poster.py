"""A season poster picked by hand survives a refresh from TMDB."""

from routers.shows import keep_chosen_season_posters


def test_a_locked_poster_is_kept():
    old = [{"season_number": 1, "poster_path": "en.jpg", "poster_locked": True}]
    new = [{"season_number": 1, "poster_path": "hu.jpg"}, {"season_number": 2, "poster_path": "s2.jpg"}]
    out = keep_chosen_season_posters(old, new)
    assert out[0] == {"season_number": 1, "poster_path": "en.jpg", "poster_locked": True}
    assert out[1] == {"season_number": 2, "poster_path": "s2.jpg"}


def test_unlocked_posters_follow_tmdb():
    old = [{"season_number": 1, "poster_path": "old.jpg"}]
    new = [{"season_number": 1, "poster_path": "new.jpg"}]
    assert keep_chosen_season_posters(old, new)[0]["poster_path"] == "new.jpg"
    assert keep_chosen_season_posters(None, new)[0]["poster_path"] == "new.jpg"


def test_a_hidden_season_is_left_out():
    from routers.shows import outside_hidden
    assert outside_hidden({"season_number": 19}, [19]) is None
    assert outside_hidden({"season_number": 18}, [19]) == {"season_number": 18}
    assert outside_hidden(None, [19]) is None
    assert outside_hidden({"season_number": 19}, []) == {"season_number": 19}


def test_aired_counts_skip_a_hidden_last_season():
    from routers.media import without_hidden_seasons
    show = {
        "seasons": [{"season_number": 0, "episode_count": 5}, {"season_number": 18, "episode_count": 8},
                    {"season_number": 19, "episode_count": 11}],
        "last_episode_to_air": {"season_number": 19, "episode_number": 11},
    }
    out = without_hidden_seasons(show, [19])
    assert [s["season_number"] for s in out["seasons"]] == [0, 18]
    assert out["last_episode_to_air"] == {"season_number": 18, "episode_number": 8}
    assert without_hidden_seasons(show, []) is show
