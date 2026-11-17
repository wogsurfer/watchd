"""The download apps belong to the install's owner: other accounts can't send
films or shows to the shared Radarr/Sonarr, or see the pipeline panel."""

import os
import unittest
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")

from routers import pipeline as pipeline_router
from routers.media import _effective_radarr, _effective_sonarr, _shared_settings

SHARED = SimpleNamespace(
    radarr_url="http://radarr", radarr_token="k", radarr_root_folder="/films", radarr_quality_profile=1,
    sonarr_url="http://sonarr", sonarr_token="k", sonarr_root_folder="/tv", sonarr_quality_profile=1,
)
NO_OWN = SimpleNamespace(
    radarr_url=None, radarr_token=None, radarr_root_folder=None, radarr_quality_profile=None,
    sonarr_url=None, sonarr_token=None, sonarr_root_folder=None, sonarr_quality_profile=None,
)
ADMIN = SimpleNamespace(is_admin=True)
MEMBER = SimpleNamespace(is_admin=False)


class SharedRadarrSonarrTests(unittest.TestCase):
    def test_admin_falls_back_to_the_shared_connection(self):
        gs = _shared_settings(ADMIN, SHARED)
        self.assertIs(_effective_radarr(NO_OWN, gs), SHARED)
        self.assertIs(_effective_sonarr(NO_OWN, gs), SHARED)

    def test_other_accounts_get_no_shared_connection(self):
        gs = _shared_settings(MEMBER, SHARED)
        self.assertIsNone(_effective_radarr(NO_OWN, gs))
        self.assertIsNone(_effective_sonarr(NO_OWN, gs))
        self.assertIsNone(_shared_settings(None, SHARED))

    def test_an_account_with_its_own_connection_still_uses_it(self):
        own = SimpleNamespace(**{**vars(SHARED), "radarr_url": "http://mine"})
        self.assertIs(_effective_radarr(own, _shared_settings(MEMBER, SHARED)), own)


class PipelinePanelTests(IsolatedAsyncioTestCase):
    async def test_other_accounts_are_told_there_are_no_download_apps(self):
        with patch.object(pipeline_router, "pipeline_health", AsyncMock()) as health:
            res = await pipeline_router.health(refresh=False, current_user=MEMBER)
        self.assertEqual(res["status"], "off")
        health.assert_not_called()

    async def test_admin_sees_the_real_panel(self):
        with patch.object(pipeline_router, "pipeline_health", AsyncMock(return_value={"status": "ok"})):
            res = await pipeline_router.health(refresh=False, current_user=ADMIN)
        self.assertEqual(res, {"status": "ok"})


if __name__ == "__main__":
    unittest.main()
