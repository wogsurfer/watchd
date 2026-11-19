import unittest
from datetime import date

from core.movie_releases import release_countries, upcoming_releases

START, END = date(2026, 10, 19), date(2026, 11, 22)


def rd(day, kind, note=""):
    return {"release_date": f"{day}T00:00:00.000Z", "type": kind, "note": note}


class MovieReleaseTests(unittest.TestCase):
    def test_countries(self):
        self.assertEqual(release_countries("mt"), ["MT", "GB", "US"])
        self.assertEqual(release_countries("US"), ["US", "GB"])
        self.assertEqual(release_countries(None), ["GB", "US"])

    def test_kinds_and_labels(self):
        results = [{"iso_3166_1": "US", "release_dates": [
            rd("2026-11-17", 4),
            rd("2026-11-17", 5, "4K Ultra HD / Blu-ray / DVD"),
            rd("2026-11-20", 4, "Prime Video"),
            rd("2026-11-01", 4, "Premium rental"),
            rd("2026-10-30", 3, "Re-release"),
            rd("2026-10-27", 1, "Film festival"),
            rd("2026-10-28", 6, "HBO"),
        ]}]
        got = [(r["date"].isoformat(), r["kind"], r["label"]) for r in upcoming_releases(results, START, END, ["US"])]
        self.assertEqual(got, [
            ("2026-10-30", "cinema", "Back in cinemas"),
            ("2026-11-01", "digital", "Digital"),
            ("2026-11-17", "disc", "4K Blu-ray"),
            ("2026-11-20", "streaming", "On Prime Video"),
        ])

    def test_country_priority_and_window(self):
        results = [
            {"iso_3166_1": "US", "release_dates": [rd("2026-10-27", 5, "Blu-ray / DVD (The Criterion Collection)")]},
            {"iso_3166_1": "GB", "release_dates": [rd("2026-10-26", 5, "The Criterion Collection"), rd("2026-06-01", 3)]},
        ]
        got = upcoming_releases(results, START, END, ["MT", "GB", "US"])
        self.assertEqual(len(got), 1)
        self.assertEqual((got[0]["country"], got[0]["label"]), ("GB", "Criterion Blu-ray"))

    def test_nothing_in_window(self):
        results = [{"iso_3166_1": "US", "release_dates": [rd("2025-01-01", 3), rd("2027-01-01", 5)]}]
        self.assertEqual(upcoming_releases(results, START, END, ["US"]), [])


if __name__ == "__main__":
    unittest.main()


class BackInCinemasTests(unittest.TestCase):
    def test_a_cinema_date_months_after_opening_is_back_in_cinemas(self):
        from datetime import date
        from core.movie_releases import upcoming_releases
        results = [{"iso_3166_1": "US", "release_dates": [
            {"release_date": "2026-07-31T00:00:00.000Z", "type": 3, "note": ""},
            {"release_date": "2026-08-06T00:00:00.000Z", "type": 2, "note": "IMAX"},
            {"release_date": "2026-12-04T00:00:00.000Z", "type": 2, "note": "Extended cut"},
        ]}]
        picked = upcoming_releases(results, date(2026, 8, 1), date(2026, 12, 31), ["US"])
        self.assertEqual([(r["date"].isoformat(), r["label"]) for r in picked],
                         [("2026-08-06", "In cinemas")])
        later = upcoming_releases(results, date(2026, 11, 1), date(2026, 12, 31), ["US"])
        self.assertEqual([r["label"] for r in later], ["Back in cinemas"])

    def test_opening_months_later_in_another_country_is_not(self):
        from datetime import date
        from core.movie_releases import upcoming_releases
        results = [
            {"iso_3166_1": "US", "release_dates": [{"release_date": "2026-01-10T00:00:00.000Z", "type": 3, "note": ""}]},
            {"iso_3166_1": "GB", "release_dates": [{"release_date": "2026-05-01T00:00:00.000Z", "type": 3, "note": ""}]},
        ]
        picked = upcoming_releases(results, date(2026, 4, 1), date(2026, 6, 1), ["GB", "US"])
        self.assertEqual([r["label"] for r in picked], ["In cinemas"])
