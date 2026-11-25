"""The Homepage dashboard's Watchd tile: only the right key gets figures,
and they're the owner's week at a glance."""

import os
import unittest
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")

from fastapi import HTTPException

from core.config import settings
from routers import dashboard


class _OwnerDB:
    def __init__(self, owner):
        self.owner = owner

    async def execute(self, stmt):
        return SimpleNamespace(scalar_one_or_none=lambda: self.owner)


GLANCE = {
    "week": {"episodes": 9, "movies": 2, "minutes": 500},
    "previous_week": {}, "month": {}, "previous_month": {},
    "streak_days": 4,
    "top_show": {"title": "Severance", "episodes": 5},
}


class HomepageWidgetTests(IsolatedAsyncioTestCase):
    async def test_refuses_without_the_right_key(self):
        with patch.object(settings, "homepage_key", "right"):
            for key in (None, "", "wrong"):
                with self.assertRaises(HTTPException) as ctx:
                    await dashboard.homepage_widget(x_api_key=key, db=_OwnerDB(None))
                self.assertEqual(ctx.exception.status_code, 401)

    async def test_off_when_no_key_is_set(self):
        with patch.object(settings, "homepage_key", None):
            with self.assertRaises(HTTPException) as ctx:
                await dashboard.homepage_widget(x_api_key="anything", db=_OwnerDB(None))
            self.assertEqual(ctx.exception.status_code, 401)

    async def test_returns_the_owners_week(self):
        owner = SimpleNamespace(id=1)
        with patch.object(settings, "homepage_key", "right"), \
             patch.object(dashboard, "dashboard_glance", AsyncMock(return_value=GLANCE)) as glance:
            out = await dashboard.homepage_widget(x_api_key="right", db=_OwnerDB(owner))
        self.assertIs(glance.call_args.kwargs["current_user"], owner)
        self.assertEqual(out, {
            "episodes_week": 9, "movies_week": 2, "hours_week": 8.3,
            "streak_days": 4, "top_show": "Severance",
        })


if __name__ == "__main__":
    unittest.main()
