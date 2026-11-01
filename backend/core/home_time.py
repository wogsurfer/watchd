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


# Where watches were logged before a move (WATCHD_EARLIER_HOME="Perth:2015-10-25"):
# their times are that place's clock, which the site and app say.
_earlier = (os.environ.get("WATCHD_EARLIER_HOME") or "").rsplit(":", 1)
EARLIER_HOME = (
    {"name": _earlier[0].strip(), "until": _earlier[1].strip()}
    if len(_earlier) == 2 and _earlier[0].strip() and len(_earlier[1].strip()) == 10 else None
)
