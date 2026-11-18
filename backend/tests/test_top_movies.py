import os
import unittest

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")

from routers.profile import _top_movie_order


def card(title, rating=None, plays=1, imdb=None):
    return {"title": title, "rating": rating, "plays": plays, "imdb_rating": imdb}


class TopMovieOrderTests(unittest.TestCase):
    def order(self, cards):
        return [c["title"] for c in sorted(cards, key=_top_movie_order)]

    def test_highest_rated_first_not_alphabetical(self):
        self.assertEqual(
            self.order([card("Alien", 7), card("Zodiac", 10), card("Memento", 8.5)]),
            ["Zodiac", "Memento", "Alien"],
        )

    def test_plays_break_ties_then_title(self):
        self.assertEqual(
            self.order([card("B", 9, 1), card("C", 9, 3), card("A", 9, 1)]),
            ["C", "A", "B"],
        )

    def test_imdb_score_orders_films_you_rated_the_same(self):
        self.assertEqual(
            self.order([card("Ghostbusters", 10, 1, 7.8), card("Dog Day Afternoon", 10, 1, 8.0), card("A Simple Plan", 10, 1, None)]),
            ["Dog Day Afternoon", "Ghostbusters", "A Simple Plan"],
        )

    def test_unrated_films_come_last(self):
        self.assertEqual(
            self.order([card("Unrated", None, 5), card("Low", 2), card("Mid", 6)]),
            ["Mid", "Low", "Unrated"],
        )


if __name__ == "__main__":
    unittest.main()
