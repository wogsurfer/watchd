import os
import unittest

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")

from core.tmdb import credits_scenes
from routers.shows import heatmap_seasons


class CreditsScenesTests(unittest.TestCase):
    def kw(self, *names):
        return {"keywords": {"keywords": [{"id": i, "name": n} for i, n in enumerate(names)]}}

    def test_reads_tmdb_keywords(self):
        self.assertEqual(credits_scenes(self.kw("aftercreditsstinger")), (False, True))
        self.assertEqual(credits_scenes(self.kw("duringcreditsstinger", "aftercreditsstinger")), (True, True))

    def test_none_when_untagged_or_missing(self):
        self.assertEqual(credits_scenes(self.kw("heist")), (False, False))
        self.assertEqual(credits_scenes({}), (False, False))


class HeatmapSeasonsTests(unittest.TestCase):
    def ep(self, n, rating=7.0, votes=10, air="2020-01-01"):
        return {"episode_number": n, "name": f"Ep {n}", "vote_average": rating, "vote_count": votes, "air_date": air}

    def test_rounds_ratings_and_keeps_order(self):
        out = heatmap_seasons([1], [{"episodes": [self.ep(1, 8.456), self.ep(2, 6.0)]}], "2026-11-28")
        self.assertEqual([e["rating"] for e in out[0]["episodes"]], [8.5, 6.0])
        self.assertEqual(out[0]["season_number"], 1)

    def test_unrated_episodes_have_no_rating(self):
        out = heatmap_seasons([1], [{"episodes": [self.ep(1, 0.0, 0), self.ep(2, 7.5, 0)]}], "2026-11-28")
        self.assertEqual([e["rating"] for e in out[0]["episodes"]], [None, None])

    def test_unaired_episodes_and_failed_or_empty_seasons_are_left_out(self):
        fetched = [
            {"episodes": [self.ep(1), self.ep(2, air="2027-01-01"), self.ep(3, air=None)]},
            RuntimeError("TMDB down"),
            {"episodes": [self.ep(1, air="2027-02-01")]},
        ]
        out = heatmap_seasons([1, 2, 3], fetched, "2026-11-28")
        self.assertEqual([s["season_number"] for s in out], [1])
        self.assertEqual([e["episode_number"] for e in out[0]["episodes"]], [1])


if __name__ == "__main__":
    unittest.main()
