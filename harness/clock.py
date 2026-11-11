"""The clock every tool and prompt uses.

By default it is the real current time. Set DEMO_NOW (e.g. 2026-12-01T14:00) to
pin a demo day instead: the clock then starts there on reset and runs forward in
real time. Either way the demo world (lectures, deadlines, calendar) is built
around the reset day, so the scripted scenarios line up with "today".
"""
from __future__ import annotations

import json
import os
import time
from datetime import date, datetime, timedelta
from pathlib import Path

DEMO_START = datetime(2026, 12, 1, 14, 0)   # the fixed day the tests use
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def pinned_start_from_env() -> datetime | None:
    value = os.environ.get("DEMO_NOW", "").strip()
    if not value or value.lower() == "now":
        return None
    return datetime.fromisoformat(value).replace(tzinfo=None, microsecond=0)


class Clock:
    def __init__(self, state_dir: Path, frozen: datetime | None = None):
        self._file = Path(state_dir) / "clock.json"
        self._frozen = frozen

    def start(self, pinned: datetime | None = None, seed_day: date | None = None) -> None:
        """Record the clock mode at reset. pinned=None means real time."""
        data = {"seed_day": (seed_day or (pinned or datetime.now()).date()).isoformat()}
        if pinned is not None:
            data.update(mode="pinned", demo_start=pinned.isoformat(), real_start=time.time())
        else:
            data["mode"] = "real"
        self._file.parent.mkdir(parents=True, exist_ok=True)
        self._file.write_text(json.dumps(data))

    def _data(self) -> dict:
        try:
            return json.loads(self._file.read_text())
        except (FileNotFoundError, ValueError):
            return {}

    @property
    def mode(self) -> str:
        if self._frozen is not None:
            return "pinned"
        return self._data().get("mode", "real")

    def seed_day(self) -> date | None:
        """The day the demo world was built around (the reset day)."""
        value = self._data().get("seed_day")
        return date.fromisoformat(value) if value else None

    def now(self) -> datetime:
        if self._frozen is not None:
            return self._frozen
        data = self._data()
        if data.get("mode") == "pinned":
            elapsed = max(0.0, time.time() - float(data["real_start"]))
            return (datetime.fromisoformat(data["demo_start"]) + timedelta(seconds=elapsed)).replace(microsecond=0)
        return datetime.now().replace(microsecond=0)


def fmt_time(dt: datetime) -> str:
    hour = dt.hour % 12 or 12
    ampm = "AM" if dt.hour < 12 else "PM"
    return f"{hour}:{dt.minute:02d} {ampm}"


def fmt_date(d: date) -> str:
    return f"{WEEKDAYS[d.weekday()]} {MONTHS[d.month - 1]} {d.day}, {d.year}"


def fmt_dt(dt: datetime) -> str:
    """'Tue Dec 1, 2026, 2:07 PM'"""
    return f"{fmt_date(dt.date())}, {fmt_time(dt)}"


def parse_dt(value: str) -> datetime:
    """Parse an ISO date or date-time. A bare date means 11:59 PM that day."""
    value = value.strip().replace(" ", "T")
    if len(value) == 10:
        return datetime.fromisoformat(value).replace(hour=23, minute=59)
    dt = datetime.fromisoformat(value)
    return dt.replace(tzinfo=None, microsecond=0)


def iso_minutes(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M")


def fmt_delta(delta: timedelta) -> str:
    """'2 days 9 hours' / '5 hours' / 'past due'."""
    secs = int(delta.total_seconds())
    if secs <= 0:
        return "past due"
    days, rem = divmod(secs, 86400)
    hours = rem // 3600
    parts = []
    if days:
        parts.append(f"{days} day{'s' if days != 1 else ''}")
    if hours or not days:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    return " ".join(parts)
