import os
import unittest
from datetime import date

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")

from routers.profile import _day_highlights


class DayHighlightsTests(unittest.TestCase):
    def test_no_plays(self):
        self.assertEqual(
            _day_highlights({}),
            {"days_watched": 0, "longest_streak": None, "busiest_day": None},
        )

    def test_longest_run_of_days_in_a_row(self):
        days = {
            date(2026, 1, 1): 1,
            date(2026, 1, 2): 2,
            # gap
            date(2026, 1, 5): 1,
            date(2026, 1, 6): 1,
            date(2026, 1, 7): 3,
        }
        out = _day_highlights(days)
        self.assertEqual(out["days_watched"], 5)
        self.assertEqual(out["longest_streak"], {"days": 3, "start": "2026-01-05", "end": "2026-01-07"})
        self.assertEqual(out["busiest_day"], {"date": "2026-01-07", "plays": 3})

    def test_runs_across_a_month_end(self):
        out = _day_highlights({date(2026, 1, 31): 1, date(2026, 2, 1): 1, date(2026, 2, 2): 1})
        self.assertEqual(out["longest_streak"]["days"], 3)

    def test_ties_go_to_the_earliest(self):
        out = _day_highlights({date(2026, 3, 1): 4, date(2026, 3, 10): 4, date(2026, 3, 20): 1})
        self.assertEqual(out["longest_streak"], {"days": 1, "start": "2026-03-01", "end": "2026-03-01"})
        self.assertEqual(out["busiest_day"]["date"], "2026-03-01")

    def test_days_with_no_plays_are_ignored(self):
        out = _day_highlights({date(2026, 4, 1): 1, date(2026, 4, 2): 0, date(2026, 4, 3): 1})
        self.assertEqual(out["days_watched"], 2)
        self.assertEqual(out["longest_streak"]["days"], 1)


if __name__ == "__main__":
    unittest.main()
