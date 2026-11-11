"""COURSE.md and MEMORY.md: a fixed top section plus an Updates section.

`remember` appends to Updates; the prompt keeps the top whole and trims only
the oldest Updates lines, so core course facts are never cut.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .clock import fmt_dt
from .mdutil import append_under_heading

UPDATES = "Updates"


def remember_text(current: str, text: str, now: datetime) -> str:
    line = f"- {fmt_dt(now)}: {' '.join(text.split())}"
    return append_under_heading(current, UPDATES, line)


def for_prompt(path: Path, max_update_lines: int = 15) -> str:
    if not path.exists():
        return ""
    text = path.read_text().strip()
    marker = f"## {UPDATES}"
    idx = text.find(marker)
    if idx == -1:
        return text
    top, updates = text[:idx].rstrip(), text[idx + len(marker):]
    lines = [l for l in updates.splitlines() if l.strip()]
    if len(lines) > max_update_lines:
        dropped = len(lines) - max_update_lines
        lines = [f"({dropped} older updates not shown)"] + lines[-max_update_lines:]
    return f"{top}\n\n{marker}\n" + "\n".join(lines) if lines else top
