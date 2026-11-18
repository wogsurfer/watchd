import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")

from routers.webhooks import _is_connection_user, parse_jellyfin_payload


def emby_play(user_id, name):
    return {"Event": "playback.stop", "User": {"Id": user_id, "Name": name},
            "Item": {"Type": "Episode", "Id": "1", "ParentIndexNumber": 4, "IndexNumber": 1}}


def conn(uid=None, name=None):
    return SimpleNamespace(server_user_id=uid, server_username=name)


class ConnectionUserTests(unittest.TestCase):
    def test_reads_the_emby_user(self):
        data = parse_jellyfin_payload(emby_play("abc123", "Rob"))
        self.assertEqual((data["user_id"], data["username"]), ("abc123", "Rob"))

    def test_only_the_connections_user_counts(self):
        data = parse_jellyfin_payload(emby_play("abc123", "Rob"))
        self.assertTrue(_is_connection_user(conn("ABC123"), data))
        self.assertTrue(_is_connection_user(conn("rob"), data))
        self.assertFalse(_is_connection_user(conn("def456"), data))
        self.assertFalse(_is_connection_user(conn(None, "Adam"), data))

    def test_ids_with_and_without_dashes_match(self):
        data = {"user_id": "0f8fad5bd9cb469fa16570867728950e", "username": ""}
        self.assertTrue(_is_connection_user(conn("0f8fad5b-d9cb-469f-a165-70867728950e"), data))

    def test_unchecked_when_either_side_has_no_user(self):
        data = parse_jellyfin_payload(emby_play("abc123", "Rob"))
        self.assertTrue(_is_connection_user(conn(), data))
        self.assertTrue(_is_connection_user(conn("def456"), {"user_id": "", "username": ""}))


if __name__ == "__main__":
    unittest.main()
