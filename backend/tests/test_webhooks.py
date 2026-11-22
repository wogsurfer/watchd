import os
import unittest
from unittest import IsolatedAsyncioTestCase

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")

from routers import webhooks
from routers.webhooks import _is_duplicate_webhook_delivery, _write_watch_event, parse_jellyfin_payload


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _FakeDB:
    """Fakes just enough of AsyncSession for _write_watch_event: every
    execute() call returns the next queued scalar_one_or_none() value, and
    add() is recorded so tests can assert whether a WatchEvent was created."""

    def __init__(self, queued_scalars):
        self._queued = list(queued_scalars)
        self.added = []

    async def execute(self, stmt):
        value = self._queued.pop(0) if self._queued else None
        return _ScalarResult(value)

    def add(self, obj):
        self.added.append(obj)


class DuplicateWebhookDeliveryTests(unittest.TestCase):
    def setUp(self):
        webhooks._recent_webhook_deliveries.clear()

    def test_second_call_with_same_key_is_flagged_as_duplicate(self):
        key = "plex:1:session-abc:media.stop"
        self.assertFalse(_is_duplicate_webhook_delivery(key))
        self.assertTrue(_is_duplicate_webhook_delivery(key))

    def test_distinct_keys_are_never_duplicates(self):
        self.assertFalse(_is_duplicate_webhook_delivery("plex:1:session-abc:media.stop"))
        self.assertFalse(_is_duplicate_webhook_delivery("plex:1:session-abc:media.scrobble"))
        self.assertFalse(_is_duplicate_webhook_delivery("plex:2:session-xyz:media.stop"))


class WriteWatchEventDedupTests(IsolatedAsyncioTestCase):
    async def test_first_completed_event_is_recorded(self):
        db = _FakeDB(queued_scalars=[None])  # no recent WatchEvent found
        await _write_watch_event(db, user_id=1, media_id=2, progress_percent=1.0, progress_seconds=120, completed=True)
        self.assertEqual(len(db.added), 1)

    async def test_second_completed_event_for_same_media_within_window_is_skipped(self):
        # Simulates media.scrobble having already written a WatchEvent moments
        # ago, then media.stop firing for the same viewing.
        db = _FakeDB(queued_scalars=[123])  # a recent WatchEvent id is found
        await _write_watch_event(db, user_id=1, media_id=2, progress_percent=1.0, progress_seconds=120, completed=True)
        self.assertEqual(len(db.added), 0)


class ParseJellyfinUserDataSavedPayloadTests(unittest.TestCase):
    """Regression test for #69: Jellyfin's official Webhook plugin has no
    "MarkPlayed" event — manually toggling watched/unwatched raises
    UserDataSaved with SaveReason=TogglePlayed instead. The parser must
    surface both fields so the handler can tell a real toggle apart from
    the same notification firing on every playback tick/rating/favorite."""

    def test_extracts_played_and_save_reason_on_manual_toggle(self):
        payload = {
            "NotificationType": "UserDataSaved",
            "ItemType": "Episode",
            "ItemId": "abc123",
            "Name": "Pilot",
            "SeriesName": "Some Show",
            "SeasonNumber": 1,
            "EpisodeNumber": 1,
            "Provider_tmdb": "999",
            "SaveReason": "TogglePlayed",
            "Played": True,
        }
        data = parse_jellyfin_payload(payload)
        self.assertIsNotNone(data)
        self.assertEqual(data["save_reason"], "TogglePlayed")
        self.assertIs(data["played"], True)

    def test_extracts_played_false_for_unwatch_toggle(self):
        payload = {
            "NotificationType": "UserDataSaved",
            "ItemType": "Movie",
            "ItemId": "xyz",
            "Name": "A Movie",
            "SaveReason": "TogglePlayed",
            "Played": False,
        }
        data = parse_jellyfin_payload(payload)
        self.assertEqual(data["save_reason"], "TogglePlayed")
        self.assertIs(data["played"], False)

    def test_still_parses_non_toggle_save_reasons(self):
        # UserDataSaved also fires for playback progress, ratings, favorites,
        # etc. — the handler (not the parser) is responsible for ignoring
        # those via save_reason, so parsing itself must not drop them.
        payload = {
            "NotificationType": "UserDataSaved",
            "ItemType": "Movie",
            "ItemId": "xyz",
            "Name": "A Movie",
            "SaveReason": "PlaybackProgress",
            "Played": False,
        }
        data = parse_jellyfin_payload(payload)
        self.assertEqual(data["save_reason"], "PlaybackProgress")


class MultiEpisodeFileTests(IsolatedAsyncioTestCase):
    """A file Emby files as S04E01-E02 (IndexNumberEnd) is one play of two
    episodes, and both should be tracked."""

    def _emby_payload(self, start, end=None, position=0, runtime=600):
        item = {"Type": "Episode", "Id": "e1", "Name": "Yanks in the U.K. (1)", "SeriesName": "Bones",
                "ParentIndexNumber": 4, "IndexNumber": start, "RunTimeTicks": runtime * 10_000_000}
        if end is not None:
            item["IndexNumberEnd"] = end
        return {"Event": "playback.stop", "Item": item,
                "PlaybackInfo": {"PositionTicks": position * 10_000_000}}

    def test_parser_keeps_the_last_episode_number(self):
        data = parse_jellyfin_payload(self._emby_payload(1, 2))
        self.assertEqual(data["episode_number_end"], 2)
        self.assertEqual(webhooks._episode_span(data), 2)

    def test_single_episode_files_span_one(self):
        self.assertEqual(webhooks._episode_span(parse_jellyfin_payload(self._emby_payload(3))), 1)
        self.assertEqual(webhooks._episode_span(parse_jellyfin_payload(self._emby_payload(3, 3))), 1)
        self.assertEqual(webhooks._episode_span({"media_type": "movie", "episode_number": 1, "episode_number_end": 2}), 1)

    def test_progress_is_split_evenly_between_the_episodes(self):
        # 60% through a two-parter: the first is finished, the second 20% in.
        self.assertEqual(webhooks._part_progress(0.6, 3600, 0, 2), (1.0, 3000))
        self.assertEqual(webhooks._part_progress(0.6, 3600, 1, 2), (0.2, 600))
        # Fully watched: both finished.
        self.assertEqual(webhooks._part_progress(1.0, 6000, 1, 2)[0], 1.0)
        # Single-episode files are unchanged.
        self.assertEqual(webhooks._part_progress(0.42, 100, 0, 1), (0.42, 100))

    async def test_parts_are_found_by_show_season_and_number(self):
        first = type("M", (), {"id": 10, "show_id": None})()
        second = type("M", (), {"id": 11, "show_id": None})()
        asked = []

        async def fake_find(data, db, api_key=None):
            asked.append((data["season_number"], data["episode_number"], data["jellyfin_id"], data["tmdb_id"]))
            return second

        original = webhooks.find_or_create_media_jellyfin
        webhooks.find_or_create_media_jellyfin = fake_find
        try:
            data = parse_jellyfin_payload(self._emby_payload(1, 2))
            parts = await webhooks._episode_parts(None, first, data, None)
        finally:
            webhooks.find_or_create_media_jellyfin = original
        self.assertEqual([p.id for p in parts], [10, 11])
        # The second episode is looked up by number, not by the first one's ids.
        self.assertEqual(asked, [(4, 2, None, None)])

    async def test_a_film_is_its_own_only_part(self):
        # Films have no episode number; stopping one must not crash.
        film = type("M", (), {"id": 7, "show_id": None})()
        data = {"media_type": "movie", "episode_number": None, "episode_number_end": None}
        parts = await webhooks._episode_parts(None, film, data, None)
        self.assertEqual([p.id for p in parts], [7])


if __name__ == "__main__":
    unittest.main()
