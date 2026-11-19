import os
import unittest

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")

from core.episode_badges import season_badges, season_types


def ep(n, day, kind="standard"):
    return {"episode_number": n, "air_date": day, "episode_type": kind, "season_number": 15}


class MidSeasonGapTests(unittest.TestCase):
    def test_a_winter_break_makes_a_mid_season_finale_and_premiere(self):
        season = {"season_number": 15, "episodes": [
            ep(6, "2026-11-11"), ep(7, "2026-11-18"), ep(8, "2027-01-06"), ep(9, "2027-01-13"),
        ]}
        badges = season_badges(season)
        self.assertEqual(badges.get(7), "Mid-season finale")
        self.assertEqual(badges.get(8), "Mid-season premiere")
        self.assertNotIn(6, badges)

    def test_a_short_break_is_not_one(self):
        types = season_types([ep(2, "2026-11-18"), ep(3, "2026-12-09")])
        self.assertEqual(types[2], "standard")

    def test_tmdbs_own_marks_are_kept(self):
        types = season_types([ep(9, "2027-03-01", "finale"), ep(10, "2027-09-01")])
        self.assertEqual(types[9], "finale")

    def test_undated_episodes_are_left_alone(self):
        types = season_types([ep(7, "2026-11-18"), {"episode_number": 8, "air_date": None}])
        self.assertEqual(types[7], "standard")


if __name__ == "__main__":
    unittest.main()


class ScheduleTypesTests(unittest.TestCase):
    """The schedule's dates against TMDB's types (Chicago P.D. 14, Nov 2026)."""

    DATES = {6: "2026-11-12", 7: "2026-11-19", 8: "2027-01-07", 9: "2027-01-14"}

    def test_the_break_in_the_schedule_marks_the_finale(self):
        from core.episode_badges import schedule_types
        types = schedule_types({7: None}, self.DATES)
        self.assertEqual(types[7], "mid_season")
        self.assertNotEqual(types[8], "mid_season")

    def test_an_out_of_date_tmdb_finale_is_dropped(self):
        from core.episode_badges import schedule_types
        # TMDB has 14x08 as the finale; the schedule airs 14x09 a week later.
        types = schedule_types({7: "standard", 8: "mid_season", 9: "standard"}, self.DATES)
        self.assertEqual(types[7], "mid_season")
        self.assertEqual(types[8], "standard")

    def test_without_schedule_dates_tmdb_stands(self):
        from core.episode_badges import schedule_types
        self.assertEqual(schedule_types({8: "mid_season", 12: "finale"}, {}), {8: "mid_season", 12: "finale"})
