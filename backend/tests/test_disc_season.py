import os
import unittest

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")

from core.episode_files import episode_span
from core.physical import disc_season

SEVEN = list(range(1, 8))


class DiscSeasonTests(unittest.TestCase):
    def test_numbers_words_and_ordinals(self):
        self.assertEqual(disc_season("Game of Thrones: Season Three", SEVEN), 3)
        self.assertEqual(disc_season("red vs. blue: SEASON 6", SEVEN), 6)
        self.assertEqual(disc_season("Sherlock: Series Two", [1, 2, 3, 4]), 2)
        self.assertEqual(disc_season("Justified: The Complete Fifth Season", SEVEN), 5)

    def test_final_season_is_the_last(self):
        self.assertEqual(disc_season("Mad Men: The Final Season Part 1", SEVEN), 7)

    def test_one_season_show_and_sets(self):
        self.assertEqual(disc_season("Firefly", [1]), 1)
        self.assertIsNone(disc_season("Sherlock: Complete Series One & Two", [1, 2, 3, 4]))
        self.assertIsNone(disc_season("Battlestar Galactica: The Complete Series", [1, 2, 3, 4]))
        self.assertIsNone(disc_season("Lost: Seasons 1-3", SEVEN))

    def test_a_season_the_show_doesnt_have(self):
        self.assertIsNone(disc_season("Show: Season Nine", SEVEN))


class EpisodeSpanTests(unittest.TestCase):
    def test_spans(self):
        self.assertEqual(episode_span(1, 2), [1, 2])
        self.assertEqual(episode_span(3, None), [3])
        self.assertEqual(episode_span(1, 40), [1])


if __name__ == "__main__":
    unittest.main()
