"""Lecture files: memory/course/lectures/YYYY-MM-DD.md with Summary and Resources."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .clock import fmt_date
from .mdutil import split_frontmatter


@dataclass
class Lecture:
    date: date
    number: int
    title: str
    path: Path

    @property
    def vpath(self) -> str:
        return f"memory/course/lectures/{self.path.name}"


def all_lectures(course: Path) -> list[Lecture]:
    out = []
    root = course / "lectures"
    if not root.is_dir():
        return out
    for p in sorted(root.glob("*.md")):
        meta, _ = split_frontmatter(p.read_text())
        try:
            d = date.fromisoformat(str(meta.get("date", p.stem)))
        except ValueError:
            continue
        out.append(Lecture(d, int(meta.get("number", 0)), str(meta.get("title", p.stem)), p))
    return sorted(out, key=lambda l: l.date)


def index_lines(lectures: list[Lecture]) -> str:
    if not lectures:
        return "No lectures yet."
    return "\n".join(f"- Lecture {l.number}, {fmt_date(l.date)}: {l.title} ({l.vpath})" for l in lectures)
