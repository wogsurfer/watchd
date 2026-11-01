"""This install's home time zone, for air times, day boundaries, streaks and
holidays: the TZ setting (Europe/Malta for Watchd's own install), UTC if it
isn't set or isn't a zone name."""

import os
from zoneinfo import ZoneInfo

HOME_TZ_NAME = os.environ.get("TZ") or "UTC"
try:
    HOME_TZ = ZoneInfo(HOME_TZ_NAME)
except Exception:
    HOME_TZ_NAME, HOME_TZ = "UTC", ZoneInfo("UTC")
