import os
import unittest
from datetime import date
from types import SimpleNamespace as NS

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")

from models.base import MediaType
from routers.dashboard import on_this_day_entries, years_ago


def ep(show, s, e):
    return (NS(), NS(media_type=MediaType.episode, season_number=s, episode_number=e, title=f"Ep {e}"), show)


class OnThisDayTests(unittest.TestCase):
    def test_years_ago(self):
        self.assertEqual(years_ago(date(2026, 11, 19), 20), date(2006, 11, 19))
        self.assertEqual(years_ago(date(2028, 2, 29), 1), date(2027, 2, 28))

    def test_a_binge_is_one_entry_per_show(self):
        bones = NS(id=1, title="Bones", tmdb_id=1911, poster_path=None)
        film = (NS(), NS(media_type=MediaType.movie, title="Heat", tmdb_id=949, poster_path=None, release_date="1995-12-15"), None)
        entries = on_this_day_entries([ep(bones, 4, 5), film, ep(bones, 4, 6)])
        self.assertEqual([e["title"] for e in entries], ["Bones", "Heat"])
        self.assertEqual([x["episode"] for x in entries[0]["episodes"]], [5, 6])
        self.assertEqual(entries[1]["year"], "1995")


if __name__ == "__main__":
    unittest.main()
