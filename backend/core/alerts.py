"""Push alerts to the install owner's phone, through ntfy (NTFY_URL in .env,
the same topic the backup and the watchdog use).

What Watchd sends, all to the owner only:

- a Downloads panel check going wrong, and right again (Sonarr, Radarr and
  disk space are left to their own alerts and the watchdog)
- another account's first play arriving through its media server, and a
  week with no plays from an account that had been scrobbling

New episodes and downloaded films are the Android app's own notifications.

Nothing is sent when NTFY_URL isn't set. What has been sent is remembered in
data/alerts.json so a restart doesn't repeat it.
"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

import httpx
from sqlalchemy import extract, func, select


NTFY_URL = os.environ.get("NTFY_URL", "").strip().rstrip("/")
# Where the phone opens Watchd from an alert (the Tailscale address, so it
# works away from home); without it, alerts open nothing.
SITE_URL = os.environ.get("WATCHD_ALERT_URL", "").strip().rstrip("/")
QUIET_DAYS = 7
CHECK_SECONDS = 600
STATE_FILE = Path(__file__).resolve().parent.parent / "data" / "alerts.json"
# Left out of the Downloads panel alerts: the arr apps send their own, and the
# watchdog watches the disks.
PIPELINE_SKIP = {"sonarr", "radarr", "disk"}



def enabled() -> bool:
    return bool(NTFY_URL)


async def send(title: str, message: str, *, tags: list[str] | None = None, priority: int = 3,
               click: str | None = None, actions: list[dict] | None = None) -> bool:
    """Publish one alert. Never raises: an alert that can't be sent is logged."""
    if not enabled():
        return False
    server, topic = NTFY_URL.rsplit("/", 1)
    body: dict = {"topic": topic, "title": title, "message": message, "priority": priority}
    if tags:
        body["tags"] = tags
    if click:
        body["click"] = click
    if actions:
        body["actions"] = actions
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(server, json=body)
            r.raise_for_status()
        return True
    except Exception as e:  # noqa: BLE001
        print(f"alerts: couldn't send '{title}': {e}")
        return False


# ── Remembered state ──────────────────────────────────────────────────────

def _load() -> dict:
    try:
        return json.loads(STATE_FILE.read_text())
    except Exception:  # noqa: BLE001
        return {}


def _save(state: dict) -> None:
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(state, indent=1, sort_keys=True))
    except Exception as e:  # noqa: BLE001
        print(f"alerts: couldn't save state: {e}")


# ── Downloads panel ───────────────────────────────────────────────────────

def pipeline_changes(checks: list[dict], before: dict) -> tuple[list[dict], list[dict], dict]:
    """Checks newly gone wrong, checks put right, and the new state (key ->
    summary of what's wrong)."""
    now = {c["key"]: c.get("summary") or c["status"] for c in checks
           if c["status"] != "ok" and c["key"] not in PIPELINE_SKIP}
    broke = [c for c in checks if c["key"] in now and before.get(c["key"]) != now[c["key"]]]
    fixed = [c for c in checks if c["key"] in before and c["key"] not in now]
    return broke, fixed, now


async def _pipeline(state: dict) -> None:
    from core.pipeline import pipeline_health

    result = await pipeline_health()
    if result.get("status") == "off":
        return
    broke, fixed, now = pipeline_changes(result.get("checks") or [], state.get("pipeline") or {})
    state["pipeline"] = now
    if broke:
        await send("Downloads need a look",
                   "\n".join(f"{c['label']}: {c.get('summary') or c['status']}" for c in broke),
                   tags=["warning"], priority=4, click=f"{SITE_URL}/" if SITE_URL else None)
    if fixed:
        await send("Downloads sorted", "\n".join(f"{c['label']}: OK again" for c in fixed),
                   tags=["white_check_mark"], priority=2)


# ── Other accounts' plays ─────────────────────────────────────────────────

async def _accounts(db, state: dict) -> None:
    from models.scrobble_connection import ScrobbleConnection
    from models.events import WatchEvent
    from models.users import User

    users = (await db.execute(
        select(User).where(User.is_admin.is_(False), User.id.in_(select(ScrobbleConnection.user_id)))
    )).scalars().all()
    seen = state.setdefault("accounts", {})
    now = datetime.utcnow()
    for user in users:
        key = str(user.id)
        mine = seen.setdefault(key, {})
        # Plays sent by a media server carry the second they ended; plays
        # logged by hand or imported are whole minutes, so they don't count.
        last_id = (await db.execute(select(func.max(WatchEvent.id)).where(
            WatchEvent.user_id == user.id,
            extract("microseconds", WatchEvent.watched_at) % 60_000_000 != 0,
        ))).scalar() or 0
        if "baseline" not in mine:
            mine["baseline"] = last_id  # what was already there (imports) doesn't count
            continue
        name = user.username
        if not mine.get("first") and last_id > mine["baseline"]:
            mine["first"] = True
            await send(f"{name}'s plays are reaching Watchd",
                       "Their media server sent its first play. Scrobbling works.", tags=["white_check_mark"])
        if not mine.get("first"):
            continue
        last_at = (await db.execute(
            select(func.max(WatchEvent.watched_at)).where(WatchEvent.user_id == user.id, WatchEvent.watched_at <= now)
        )).scalar()
        quiet = last_at is not None and now - last_at > timedelta(days=QUIET_DAYS)
        if quiet and not mine.get("quiet"):
            await send(f"No plays from {name} for a week",
                       f"Their last play was on {last_at:%d %B}. If they've been watching, check their Emby webhook.",
                       tags=["warning"])
        mine["quiet"] = quiet


# ── The loop ──────────────────────────────────────────────────────────────

async def alerts_loop(session_factory) -> None:
    """Checks every ten minutes while the app runs."""
    if not enabled():
        print("alerts: NTFY_URL not set, phone alerts are off")
        return
    await asyncio.sleep(60)
    while True:
        state = _load()
        for step in ("pipeline", "accounts"):
            try:
                if step == "pipeline":
                    await _pipeline(state)
                else:
                    async with session_factory() as db:
                        await _accounts(db, state)
            except Exception as e:  # noqa: BLE001
                print(f"alerts: {step} check failed: {e}")
        _save(state)
        await asyncio.sleep(CHECK_SECONDS)
