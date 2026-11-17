import io
import json
import os
import unittest
import zipfile
from unittest import IsolatedAsyncioTestCase

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")

from core.trakt_export import TraktExport, TraktExportError, read_export

MOVIE = {"title": "Heat", "year": 1995, "ids": {"trakt": 1, "tmdb": 949}}
OTHER_MOVIE = {"title": "Ronin", "year": 1998, "ids": {"trakt": 2, "tmdb": 8195}}
SHOW = {"title": "Bones", "year": 2005, "ids": {"trakt": 3, "tmdb": 1911}}


def play_movie(i, when, movie=MOVIE):
    return {"id": i, "watched_at": when, "action": "watch", "type": "movie", "movie": movie}


def play_episode(i, when, season, number):
    return {"id": i, "watched_at": when, "action": "watch", "type": "episode",
            "episode": {"season": season, "number": number, "title": "x", "ids": {}}, "show": SHOW}


def zip_of(files: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, data in files.items():
            z.writestr(name, json.dumps(data))
    return buf.getvalue()


class ReadingTests(IsolatedAsyncioTestCase):
    async def test_items_are_recognised_by_shape_across_numbered_files(self):
        export = TraktExport([
            ("watched-history-1.json", [play_movie(1, "2020-01-01T20:00:00.000Z"), play_episode(2, "2020-01-02T20:00:00.000Z", 4, 1)]),
            ("watched-history-2.json", [play_episode(3, "2020-01-03T20:00:00.000Z", 4, 2)]),
            ("ratings-movies.json", [{"rated_at": "2020-01-04T00:00:00.000Z", "rating": 8, "type": "movie", "movie": MOVIE}]),
            ("ratings-seasons.json", [{"rated_at": "2020-01-04T00:00:00.000Z", "rating": 7, "type": "season", "season": {"number": 4}, "show": SHOW}]),
            ("ratings-episodes.json", [{"rated_at": "2020-01-04T00:00:00.000Z", "rating": 9, "type": "episode", "episode": {"season": 4, "number": 1}, "show": SHOW}]),
            ("watchlist-movies.json", [{"listed_at": "2020-01-05T00:00:00.000Z", "type": "movie", "movie": OTHER_MOVIE}]),
        ])
        self.assertEqual(len(await export.get_history_movies(None, None)), 1)
        self.assertEqual(len(await export.get_history_episodes(None, None)), 2)
        ratings = await export.get_ratings(None, None)
        self.assertEqual((len(ratings["movies"]), len(ratings["shows"]), len(ratings["seasons"])), (1, 0, 1))
        self.assertEqual([w["movie"]["title"] for w in await export.get_watchlist(None, None)], ["Ronin"])

    async def test_the_same_play_in_two_files_counts_once(self):
        p = play_movie(1, "2020-01-01T20:00:00.000Z")
        export = TraktExport([("history.json", [p]), ("watched-history-1.json", [p])])
        self.assertEqual(len(await export.get_history_movies(None, None)), 1)

    async def test_repeat_viewings_are_kept(self):
        export = TraktExport([("history.json", [play_movie(1, "2020-01-01T20:00:00.000Z"), play_movie(2, "2021-06-01T20:00:00.000Z")])])
        self.assertEqual(len(await export.get_history_movies(None, None)), 2)

    async def test_watched_titles_without_plays_get_one_play(self):
        export = TraktExport([
            ("history.json", [play_movie(1, "2020-01-01T20:00:00.000Z")]),
            ("watched-movies.json", [
                {"plays": 3, "last_watched_at": "2020-01-01T20:00:00.000Z", "movie": MOVIE},
                {"plays": 1, "last_watched_at": "2019-03-03T20:00:00.000Z", "movie": OTHER_MOVIE},
            ]),
            ("watched-shows.json", [{"plays": 2, "last_watched_at": "2020-02-02T00:00:00.000Z", "show": SHOW, "seasons": [
                {"number": 1, "episodes": [{"number": 1, "plays": 1, "last_watched_at": "2020-02-01T00:00:00.000Z"},
                                           {"number": 2, "plays": 1, "last_watched_at": "2020-02-02T00:00:00.000Z"}]},
            ]}]),
        ])
        movies = await export.get_history_movies(None, None)
        # Heat already has its play; Ronin gets one on its last-watched date.
        self.assertEqual(sorted(m["movie"]["title"] for m in movies), ["Heat", "Ronin"])
        eps = await export.get_history_episodes(None, None)
        self.assertEqual(sorted((e["episode"]["season"], e["episode"]["number"]) for e in eps), [(1, 1), (1, 2)])

    async def test_personal_lists_are_named_and_filled(self):
        export = TraktExport([
            ("lists.json", [{"name": "Heist films", "description": "Best ones", "ids": {"trakt": 9, "slug": "heist-films"}}]),
            ("lists-heist-films.json", [{"listed_at": "2020-01-05T00:00:00.000Z", "type": "movie", "movie": MOVIE}]),
        ])
        lists = await export.get_user_lists(None, None)
        self.assertEqual([l["name"] for l in lists], ["Heist films"])
        items = await export.get_list_items(None, None, lists[0]["ids"]["slug"])
        self.assertEqual([i["movie"]["title"] for i in items], ["Heat"])


class FileTests(unittest.TestCase):
    def test_reads_a_zip(self):
        export = read_export("trakt-backup.zip", zip_of({"trakt/watched-history-1.json": [play_movie(1, "2020-01-01T20:00:00.000Z")]}))
        self.assertEqual(export.summary()["movie_plays"], 1)

    def test_reads_a_single_json_file(self):
        export = read_export("watched-history-1.json", json.dumps([play_movie(1, "2020-01-01T20:00:00.000Z")]).encode())
        self.assertEqual(export.summary()["movie_plays"], 1)

    def test_rejects_something_that_isnt_an_export(self):
        with self.assertRaises(TraktExportError):
            read_export("photo.jpg", b"not a zip")
        with self.assertRaises(TraktExportError):
            read_export("empty.zip", zip_of({"user.json": {"user": {"username": "x"}}}))


if __name__ == "__main__":
    unittest.main()
