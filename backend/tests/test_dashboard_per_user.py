"""The dashboard shows the signed-in account's own name and plays, never
another account's."""

import os
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")

from sqlalchemy.dialects import postgresql

from routers import dashboard


class _Result:
    def __init__(self, value=None):
        self._value = value

    def all(self):
        return []

    def one(self):
        return (0, 0, 0, 0) if self._value is None else self._value

    def scalar_one_or_none(self):
        return self._value


class _RecordingDB:
    """Records each query's SQL and bound values, answering with empties."""

    def __init__(self, answers=None):
        self.queries = []
        self._answers = list(answers or [])

    async def execute(self, stmt):
        compiled = stmt.compile(dialect=postgresql.dialect())
        self.queries.append((str(compiled), compiled.params))
        return _Result(self._answers.pop(0) if self._answers else None)


class Last30Tests(IsolatedAsyncioTestCase):
    async def test_counts_only_the_signed_in_accounts_plays(self):
        db = _RecordingDB()
        await dashboard.dashboard_last30(db=db, current_user=SimpleNamespace(id=2))
        sql, params = db.queries[0]
        self.assertIn("watch_events.user_id", sql)
        self.assertIn(2, params.values())
        self.assertNotIn(1, params.values())


class GreetingTests(IsolatedAsyncioTestCase):
    async def _greeting(self, display_name, first_play):
        # stats() runs: tv totals, film totals, owned discs, TV discs,
        # display name, first play.
        db = _RecordingDB([(0, 0, 0, 0), (0, 0, 0), None, None, display_name, first_play])
        user = SimpleNamespace(id=2, username="brother81")
        return (await dashboard.dashboard_stats(db=db, current_user=user))["greeting"]

    async def test_uses_the_display_name_and_first_play_year(self):
        self.assertEqual(await self._greeting("Mark", datetime(2004, 5, 1)), {"name": "Mark", "since": 2004})

    async def test_falls_back_to_the_username_with_no_plays_yet(self):
        self.assertEqual(await self._greeting(None, None), {"name": "brother81", "since": None})


if __name__ == "__main__":
    unittest.main()
