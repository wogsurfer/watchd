import os
import unittest

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")

from core.alerts import pipeline_changes


def check(key, status, summary=""):
    return {"key": key, "label": key.title(), "status": status, "summary": summary}


class PipelineChangeTests(unittest.TestCase):
    def test_a_new_problem_is_told_once(self):
        checks = [check("unpackerr", "error", "Stopped"), check("bazarr", "ok")]
        broke, fixed, state = pipeline_changes(checks, {})
        self.assertEqual([c["key"] for c in broke], ["unpackerr"])
        broke, fixed, state = pipeline_changes(checks, state)
        self.assertEqual((broke, fixed), ([], []))

    def test_a_changed_problem_is_told_again_and_a_fixed_one_once(self):
        _, _, state = pipeline_changes([check("downloads", "warn", "1 stuck")], {})
        broke, _, state = pipeline_changes([check("downloads", "warn", "3 stuck")], state)
        self.assertEqual(len(broke), 1)
        broke, fixed, state = pipeline_changes([check("downloads", "ok")], state)
        self.assertEqual(([c["key"] for c in fixed], state), (["downloads"], {}))

    def test_arr_apps_and_disk_are_left_to_their_own_alerts(self):
        broke, _, state = pipeline_changes(
            [check("sonarr", "error"), check("radarr", "error"), check("disk", "warn", "92% full")], {})
        self.assertEqual((broke, state), ([], {}))


if __name__ == "__main__":
    unittest.main()
