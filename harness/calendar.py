"""The fixed demo calendar plus events each student adds (kept in state/)."""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from pathlib import Path

from .clock import fmt_time, parse_dt
from .runtime import RuntimePaths


@dataclass
class Event:
    id: str
    title: str
    start: datetime
    end: datetime
    added: bool = False

    def as_dict(self) -> dict:
        return {"id": self.id, "title": self.title,
                "start": self.start.strftime("%Y-%m-%dT%H:%M"),
                "end": self.end.strftime("%Y-%m-%dT%H:%M"), "added": self.added}


def _hhmm(value: str) -> time:
    h, m = value.split(":")
    return time(int(h), int(m))


class Calendar:
    def __init__(self, rt: RuntimePaths, username: str):
        self.rt = rt
        self.username = username

    @property
    def _added_file(self) -> Path:
        return self.rt.state / "added_events" / f"{self.username}.json"

    def _load(self) -> list[Event]:
        events = []
        try:
            base = json.loads(self.rt.calendar.read_text())
        except FileNotFoundError:
            base = []
        for e in base:
            events.append(Event(e["id"], e["title"], parse_dt(e["start"]), parse_dt(e["end"])))
        try:
            added = json.loads(self._added_file.read_text())
        except FileNotFoundError:
            added = []
        for e in added:
            events.append(Event(e["id"], e["title"], parse_dt(e["start"]), parse_dt(e["end"]), True))
        return sorted(events, key=lambda e: e.start)

    def list_events(self, start: datetime, end: datetime) -> list[Event]:
        return [e for e in self._load() if e.end > start and e.start < end]

    def overlaps(self, start: datetime, end: datetime) -> list[Event]:
        return self.list_events(start, end)

    def add_event(self, title: str, start: datetime, end: datetime) -> Event:
        if end <= start:
            raise ValueError("The event must end after it starts.")
        ev = Event(f"added-{uuid.uuid4().hex[:8]}", title.strip() or "Study block", start, end, True)
        try:
            added = json.loads(self._added_file.read_text())
        except FileNotFoundError:
            added = []
        added.append(ev.as_dict())
        self._added_file.parent.mkdir(parents=True, exist_ok=True)
        self._added_file.write_text(json.dumps(added, indent=2))
        return ev

    def free_time(self, start: datetime, end: datetime, earliest: str = "09:00",
                  latest: str = "22:00", min_minutes: int = 30) -> list[tuple[datetime, datetime]]:
        """Free blocks of at least min_minutes inside [start, end), only between
        earliest and latest each day."""
        e_t, l_t = _hhmm(earliest), _hhmm(latest)
        events = self._load()
        blocks = []
        day = start.date()
        while day <= end.date():
            w_start = max(start, datetime.combine(day, e_t))
            w_end = min(end, datetime.combine(day, l_t))
            if w_start < w_end:
                busy = sorted((max(e.start, w_start), min(e.end, w_end))
                              for e in events if e.end > w_start and e.start < w_end)
                cursor = w_start
                for b_start, b_end in busy:
                    if b_start > cursor:
                        blocks.append((cursor, b_start))
                    cursor = max(cursor, b_end)
                if cursor < w_end:
                    blocks.append((cursor, w_end))
            day += timedelta(days=1)
        return [(s, e) for s, e in blocks if (e - s) >= timedelta(minutes=min_minutes)]


def describe_blocks(blocks: list[tuple[datetime, datetime]]) -> str:
    if not blocks:
        return "No free blocks in that range."
    lines = []
    total = timedelta()
    longest = timedelta()
    for s, e in blocks:
        d = e - s
        total += d
        longest = max(longest, d)
        lines.append(f"- {s:%a %b} {s.day}: {fmt_time(s)} to {fmt_time(e)} ({int(d.total_seconds() // 60)} min)")
    lines.append(f"Total free: {total.total_seconds() / 3600:.2f} hours; "
                 f"longest block: {int(longest.total_seconds() // 60)} min.")
    return "\n".join(lines)
