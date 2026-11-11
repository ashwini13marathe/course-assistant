"""Reset the demo: rebuild runtime/ from seed/, dated around the reset day.

Seed files are templates. Dates in them are written relative to the reset day D:

    {{D|weekday}}          Tuesday
    {{D-7|iso}}            2026-11-24
    {{D-7|day}}            Tue Nov 24
    {{D-21|long}}          Tuesday Nov 10
    {{D+2@23:59|isodt}}    2026-12-03T23:59
    {{D-28@16:00|dt}}      Tue Nov 3, 2026, 4:00 PM

So "last week's lecture", "due in two days" and Alice's busy week line up with
whatever day you reset on. Lectures fall on D's weekday and the weekday two days
later (Tue/Thu when you reset on a Tuesday).

Presets:
  before_hw3  HW1 and HW2 published; HW3 is published live on stage.
  after_hw3   as above, plus a hand-written HW3 publish, as a fallback.
"""
from __future__ import annotations

import json
import re
import shutil
from datetime import date, datetime, time, timedelta
from pathlib import Path

import yaml

from . import assignments as A
from .clock import MONTHS, WEEKDAY_NAMES, WEEKDAYS, Clock, fmt_dt, pinned_start_from_env
from .gitops import Git
from .runtime import PROJECT_ROOT, RuntimePaths

SEED = PROJECT_ROOT / "seed"
PRESETS = ("before_hw3", "after_hw3")
TEXT_SUFFIXES = {".md", ".yaml", ".yml", ".json", ".txt", ".py"}
TOKEN = re.compile(r"\{\{D([+-]\d+)?(?:@(\d{1,2}:\d{2}))?\|(\w+)\}\}")


def day_of(seed_day: date, offset: int) -> date:
    return seed_day + timedelta(days=offset)


def render(text: str, seed_day: date) -> str:
    def sub(m: re.Match) -> str:
        d = day_of(seed_day, int(m.group(1) or 0))
        hh, mm = (int(x) for x in (m.group(2) or "23:59").split(":"))
        dt = datetime.combine(d, time(hh, mm))
        fmt = m.group(3)
        if fmt == "iso":
            return d.isoformat()
        if fmt == "isodt":
            return dt.strftime("%Y-%m-%dT%H:%M")
        if fmt == "day":
            return f"{WEEKDAYS[d.weekday()]} {MONTHS[d.month - 1]} {d.day}"
        if fmt == "long":
            return f"{WEEKDAY_NAMES[d.weekday()]} {MONTHS[d.month - 1]} {d.day}"
        if fmt == "weekday":
            return WEEKDAY_NAMES[d.weekday()]
        if fmt == "dt":
            return fmt_dt(dt)
        raise ValueError(f"Unknown date format '{fmt}' in seed template")
    return TOKEN.sub(sub, text)


def _copy_tree(src: Path, dest: Path, seed_day: date) -> None:
    for item in src.rglob("*"):
        target = dest / render(str(item.relative_to(src)), seed_day)
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if item.suffix.lower() in TEXT_SUFFIXES:
            target.write_text(render(item.read_text(), seed_day))
        else:
            shutil.copy2(item, target)


def lecture_offsets() -> list[int]:
    """Day offsets of the eight seeded lectures, oldest first (today is the last)."""
    return [-26, -21, -19, -14, -12, -7, -5, 0]


def _write_lectures(course: Path, seed_day: date) -> None:
    specs = yaml.safe_load((SEED / "lectures.yaml").read_text())
    folder = course / "lectures"
    folder.mkdir(parents=True, exist_ok=True)
    for offset, spec in zip(lecture_offsets(), specs):
        d = day_of(seed_day, offset)
        resources = "\n".join(f"- {r}" for r in spec.get("resources") or []) or "_None yet._"
        meta = yaml.safe_dump({"date": d.isoformat(), "number": spec["number"], "title": spec["title"]},
                              sort_keys=False).strip()
        (folder / f"{d.isoformat()}.md").write_text(
            f"---\n{meta}\n---\n# Lecture {spec['number']}: {spec['title']} "
            f"({WEEKDAYS[d.weekday()]} {MONTHS[d.month - 1]} {d.day})\n\n"
            f"## Summary\n\n{spec['summary'].strip()}\n\n## Resources\n\n{resources}\n")


def reset(root: Path, preset: str = "before_hw3", pinned: datetime | None = None) -> RuntimePaths:
    """Rebuild the runtime. pinned=None uses DEMO_NOW from the environment, or the real clock."""
    if preset not in PRESETS:
        raise ValueError(f"preset must be one of {PRESETS}")
    pinned = pinned or pinned_start_from_env()
    seed_day = (pinned or datetime.now()).date()
    rt = RuntimePaths(Path(root).resolve())
    if rt.root.exists():
        shutil.rmtree(rt.root)
    rt.root.mkdir(parents=True)

    _copy_tree(SEED / "memory", rt.memory, seed_day)
    _write_lectures(rt.course, seed_day)
    for sub in ("notes/lectures", "notes/assignments", "notes/general", "skills"):
        (rt.user_dir("alice") / sub).mkdir(parents=True, exist_ok=True)
    rt.calendar.write_text(render((SEED / "calendar.json").read_text(), seed_day))
    rt.uploads.mkdir(parents=True, exist_ok=True)
    Clock(rt.state).start(pinned, seed_day)

    def at(offset: int, hhmm: str) -> datetime:
        hh, mm = (int(x) for x in hhmm.split(":"))
        return datetime.combine(day_of(seed_day, offset), time(hh, mm))

    git = Git(rt)
    git.init_main()
    repo_seed = SEED / "repo"
    shutil.copy2(repo_seed / "main" / "README.md", rt.repo / "README.md")
    _copy_tree(repo_seed / "main" / "hw1", rt.repo / "hw1", seed_day)
    git.commit_all(rt.repo, "Publish HW1: Linked lists", "professor", when=at(-35, "09:00"))
    alice = git.ensure_student_worktree("alice")
    _copy_tree(repo_seed / "alice" / "hw1", alice / "hw1", seed_day)
    git.commit_all(alice, "Submit HW1", "alice", when=at(-22, "21:40"))
    _copy_tree(repo_seed / "main" / "hw2", rt.repo / "hw2", seed_day)
    git.commit_all(rt.repo, "Publish HW2: Stacks and queues", "professor", when=at(-21, "09:00"))
    git.sync_main_into("alice", when=at(-21, "12:00"))
    _copy_tree(repo_seed / "alice" / "hw2", alice / "hw2", seed_day)
    git.commit_all(alice, "Submit HW2", "alice", when=at(-8, "22:15"))

    if preset == "after_hw3":
        _publish_hw3_fallback(rt, git, seed_day, pinned or datetime.now().replace(microsecond=0))
    return rt


def _publish_hw3_fallback(rt: RuntimePaths, git: Git, seed_day: date, when: datetime) -> None:
    src = SEED / "presets" / "hw3"
    args = json.loads(render((src / "args.json").read_text(), seed_day))
    staging = rt.upload_dir("professor")
    staging.mkdir(parents=True, exist_ok=True)
    for f in args["files"]:
        shutil.copy2(src / f["upload"], staging / f["upload"])
    message = args.pop("professor_message")
    plan = A.plan_publish(rt, args, when, [message])
    A.apply_publish(rt, plan, git)
