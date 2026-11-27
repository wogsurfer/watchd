"""The scrobble-only Emby/Jellyfin webhook forwards plays to every connected
tracker (Trakt, MDBList and Simkl), not just Trakt."""
import asyncio
import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")

from routers import webhooks


def _request(event: str, position_ticks: int = 0) -> MagicMock:
    payload = {
        "Event": event,
        "User": {"Id": "abc", "Name": "Rob"},
        "Item": {"Type": "Movie", "Id": "1", "Name": "A Film", "RunTimeTicks": 100,
                 "ProviderIds": {"Tmdb": "123"}},
        "PlaybackInfo": {"PositionTicks": position_ticks},
        "Session": {"Id": "s1"},
    }
    req = MagicMock()
    req.body = AsyncMock(return_value=json.dumps(payload).encode())
    return req


def _db() -> MagicMock:
    user = SimpleNamespace(id=1)
    settings = SimpleNamespace()
    results = [MagicMock(), MagicMock()]
    results[0].scalar_one_or_none.return_value = user
    results[1].scalar_one_or_none.return_value = settings
    db = MagicMock()
    db.execute = AsyncMock(side_effect=results)
    db.commit = AsyncMock()
    return db


class ScrobbleWebhookForwardingTests(unittest.TestCase):
    def _run(self, event: str, position_ticks: int = 0) -> dict[str, AsyncMock]:
        media = SimpleNamespace(id=5, media_type="movie", tmdb_id=123)
        conn = SimpleNamespace(sync_collection=False, sync_playback=False, sync_watched=False,
                               server_user_id=None, server_username=None)
        mocks = {name: AsyncMock() for name in
                 ("_maybe_trakt_scrobble", "_maybe_mdblist_scrobble", "_maybe_simkl_scrobble")}
        with patch.multiple(webhooks, **mocks), \
             patch.object(webhooks, "_get_scrobble_connection_by_id", AsyncMock(return_value=conn)), \
             patch.object(webhooks, "_get_tmdb_key", AsyncMock(return_value=None)), \
             patch.object(webhooks, "find_or_create_media_jellyfin", AsyncMock(return_value=media)), \
             patch.object(webhooks, "_close_session", AsyncMock(return_value=None)), \
             patch.object(webhooks, "_episode_parts", AsyncMock(return_value=[media])):
            asyncio.run(webhooks._handle_jellyfin_scrobble_webhook(
                _request(event, position_ticks), _db(), "key", 1, source="emby"))
        return mocks

    def test_start_goes_to_every_tracker(self):
        mocks = self._run("playback.start")
        for m in mocks.values():
            m.assert_awaited_once()
        self.assertEqual(mocks["_maybe_mdblist_scrobble"].await_args.args[2], "start")

    def test_finished_play_goes_to_every_tracker(self):
        mocks = self._run("playback.stop", position_ticks=100)
        for m in mocks.values():
            m.assert_awaited_once()
        self.assertEqual(mocks["_maybe_mdblist_scrobble"].await_args.args[2], "stop")

    def test_mark_played_goes_to_every_tracker(self):
        mocks = self._run("item.markplayed")
        for m in mocks.values():
            m.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
