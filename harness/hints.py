"""Hints: three levels per assignment, hidden from students and released one
level at a time. Progress lives in state/, which no tool can write to."""
from __future__ import annotations

import json
from datetime import datetime

from . import assignments as A
from .mdutil import join_frontmatter, section, split_frontmatter
from .runtime import RuntimePaths

LEVEL_NAMES = ["Level 1 (nudge)", "Level 2 (approach)", "Level 3 (near-pseudocode)"]


def hints_path(rt: RuntimePaths, aid: str):
    return rt.course / "skills" / "hints" / aid / "SKILL.md"


def render_hints(aid: str, title: str, levels: list[str]) -> str:
    meta = {"name": f"hints/{aid}", "description": f"Three hint levels for {aid.upper()} ({title}). "
            "Served one level at a time by get_hint; never shown whole to students.",
            "audience": "student"}
    body = f"# {aid.upper()} hints\n\n" + "\n\n".join(
        f"## {name}\n\n{text.strip()}" for name, text in zip(LEVEL_NAMES, levels)) + "\n"
    return join_frontmatter(meta, body)


def plan_save(rt: RuntimePaths, aid: str, levels: list[str]) -> tuple[str, str, str]:
    aid = A.normalize_id(aid)
    a = A.load(rt.course, aid)
    if not a:
        raise A.AssignmentError(f"{aid.upper()} doesn't exist yet. Publish it first.")
    levels = [str(l).strip() for l in (levels or [])]
    if len(levels) != 3 or not all(levels):
        raise A.AssignmentError("Give exactly three non-empty hint levels: nudge, approach, near-pseudocode.")
    path = hints_path(rt, aid)
    old = path.read_text() if path.exists() else ""
    return aid, old, render_hints(aid, a.title, levels)


def apply_save(rt: RuntimePaths, aid: str, text: str, now: datetime) -> str:
    path = hints_path(rt, aid)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    A.set_hints_status(rt, aid, "available", now, "Hints are now available (three levels).")
    return f"Saved three hint levels for {aid.upper()} (hidden from students); hints are now available."


def _progress_file(rt: RuntimePaths):
    return rt.state / "hint_progress.json"


def _load_progress(rt: RuntimePaths) -> dict:
    try:
        return json.loads(_progress_file(rt).read_text())
    except (FileNotFoundError, ValueError):
        return {}


def used_levels(rt: RuntimePaths, username: str, aid: str) -> int:
    return int(_load_progress(rt).get(username, {}).get(aid, 0))


def next_hint(rt: RuntimePaths, username: str, aid: str) -> str:
    aid = A.normalize_id(aid)
    a = A.load(rt.course, aid)
    if not a:
        return f"There is no {aid.upper()}."
    if a.hints != "available":
        extra = f" Professor's note: {a.notes}" if a.notes and a.notes != "_None._" else ""
        return f"Hints for {aid.upper()} aren't available yet (status: {a.hints}).{extra}"
    _, body = split_frontmatter(hints_path(rt, aid).read_text())
    used = used_levels(rt, username, aid)
    if used >= 3:
        return (f"All three {aid.upper()} hint levels are already unlocked. Level 3 again:\n\n"
                + (section(body, LEVEL_NAMES[2]) or ""))
    level = used + 1
    text = section(body, LEVEL_NAMES[level - 1]) or ""
    progress = _load_progress(rt)
    progress.setdefault(username, {})[aid] = level
    _progress_file(rt).parent.mkdir(parents=True, exist_ok=True)
    _progress_file(rt).write_text(json.dumps(progress, indent=2))
    remaining = 3 - level
    return (f"{aid.upper()} hint, level {level} of 3:\n\n{text}\n\n"
            + (f"{remaining} more level{'s' if remaining != 1 else ''} available after another try."
               if remaining else "That was the last level."))
