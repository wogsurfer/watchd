import os
import unittest

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")

from routers.history import milestone_label


class MilestoneTests(unittest.TestCase):
    def test_round_numbers(self):
        self.assertEqual(milestone_label("episode", 1000), "1,000th episode")
        self.assertEqual(milestone_label("episode", 5000), "5,000th episode")
        self.assertEqual(milestone_label("episode", 10000), "10,000th episode")
        self.assertEqual(milestone_label("film", 100), "100th film")
        self.assertEqual(milestone_label("film", 500), "500th film")
        self.assertEqual(milestone_label("film", 1500), "1,500th film")
        self.assertEqual(milestone_label("play", 1000), "1,000th film play")

    def test_other_plays_are_not(self):
        self.assertIsNone(milestone_label("episode", 500))
        self.assertIsNone(milestone_label("episode", 2000))
        self.assertIsNone(milestone_label("episode", 6000))
        self.assertIsNone(milestone_label("film", 150))
        self.assertIsNone(milestone_label("film", 200))
        self.assertIsNone(milestone_label("film", 1200))
        self.assertIsNone(milestone_label("film", 0))


if __name__ == "__main__":
    unittest.main()
