"""Assignments: guidelines files, file naming, publishing and updates.

The model supplies content (title, notes, checklist) and tags each upload as
handout, starter or solution; this module decides every stored name and checks
the deadline, so a model slip can't misname a file or invent a deadline.
"""
from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from .clock import fmt_dt, iso_minutes, parse_dt
from .mdutil import append_under_heading, join_frontmatter, section, split_frontmatter
from .runtime import RuntimePaths

ASSIGNMENT_ID = re.compile(r"^hw([1-9]\d?)$")
LATE_DAYS = 2
KINDS = ("handout", "starter", "solution")
HINT_STATES = ("coming", "available", "none")
CODE_EXTS = {".py", ".java", ".c", ".cpp", ".h", ".js", ".ts", ".go", ".rs", ".ipynb"}
_COPY_MARKERS = re.compile(r"(?i)(?:^|[\s_\-.])(?:\(\d+\)|copy|final|v\d+)(?=$|[\s_\-.])")


class AssignmentError(Exception):
    """A request the tool refuses, with a message the model can act on."""


@dataclass
class Assignment:
    id: str
    title: str
    due: datetime
    published_at: datetime | None
    hints: str
    overview: str
    notes: str
    updates: list[str]
    files: dict
    dir: Path

    def status(self, now: datetime) -> str:
        if now < self.due:
            return "open"
        if now < self.due + timedelta(days=LATE_DAYS):
            return "late window"
        return "closed"

    @property
    def number(self) -> int:
        return int(self.id[2:])


def normalize_id(value: str) -> str:
    v = re.sub(r"[\s_\-]", "", (value or "").lower())
    v = v.replace("homework", "hw").replace("assignment", "hw")
    if ASSIGNMENT_ID.match(v):
        return v
    if v.isdigit():
        return f"hw{int(v)}"
    raise AssignmentError(f"'{value}' is not an assignment id. Use hw1, hw2, hw3 …")


def guidelines_path(course: Path, aid: str) -> Path:
    return course / "assignments" / aid / "guidelines.md"


def load(course: Path, aid: str) -> Assignment | None:
    path = guidelines_path(course, aid)
    if not path.exists():
        return None
    meta, body = split_frontmatter(path.read_text())
    updates_text = section(body, "Updates") or ""
    return Assignment(
        id=aid,
        title=str(meta.get("title", aid.upper())),
        due=parse_dt(str(meta["due"])),
        published_at=parse_dt(str(meta["published_at"])) if meta.get("published_at") else None,
        hints=str(meta.get("hints", "none")),
        overview=section(body, "Overview") or "",
        notes=section(body, "Professor notes") or "",
        updates=[l[2:].strip() for l in updates_text.splitlines() if l.startswith("- ")],
        files=dict(meta.get("files") or {}),
        dir=path.parent,
    )


def all_assignments(course: Path) -> list[Assignment]:
    root = course / "assignments"
    out = []
    if root.is_dir():
        for d in sorted(root.iterdir()):
            if d.is_dir() and ASSIGNMENT_ID.match(d.name):
                a = load(course, d.name)
                if a:
                    out.append(a)
    return sorted(out, key=lambda a: a.number)


def describe(a: Assignment, now: datetime, detail: bool = True) -> str:
    left = a.due - now
    if a.status(now) == "open":
        days, rem = divmod(int(left.total_seconds()), 86400)
        hours = rem // 3600
        when = f"{days}d {hours}h left" if days else f"{hours}h left"
    else:
        when = a.status(now)
    lines = [f"{a.id.upper()}: {a.title}. Due {fmt_dt(a.due)} ({when}). Hints: {a.hints}."]
    if a.published_at:
        lines[0] += f" Published {fmt_dt(a.published_at)}."
    if detail:
        if a.notes and a.notes != "_None._":
            lines.append(f"  Professor notes: {a.notes}")
        for u in a.updates:
            lines.append(f"  Update: {u}")
        lines.append(f"  Files: memory/course/assignments/{a.id}/")
    return "\n".join(lines)


# -- naming ---------------------------------------------------------------
def clean_name(original: str) -> str:
    """'CS201 HW3 FINAL (2).PDF' -> 'cs201-hw3.pdf'; code keeps import-safe names."""
    name = Path(original).name
    stem, ext = Path(name).stem, Path(name).suffix.lower()
    prev = None
    while prev != stem:
        prev = stem
        stem = _COPY_MARKERS.sub("", stem).strip(" _-.")
    stem = stem.lower()
    if ext in CODE_EXTS:
        stem = re.sub(r"[^a-z0-9]+", "_", stem).strip("_") or "file"
        if stem[0].isdigit():
            stem = "f_" + stem
    else:
        stem = re.sub(r"[^a-z0-9]+", "-", stem).strip("-") or "file"
    return stem + ext


def _numbered(base: str, ext: str, n: int) -> str:
    return f"{base}{ext}" if n == 1 else f"{base}-{n}{ext}"


def quote_found(quote: str, texts: list[str]) -> bool:
    q = " ".join((quote or "").lower().split()).strip(" .,!?:;\"'")
    if len(q) < 3:
        return False
    return any(q in " ".join(t.lower().split()) for t in texts)


# -- publishing -----------------------------------------------------------
@dataclass
class FileMove:
    upload: str
    kind: str
    dest_vpath: str
    dest_real: Path
    visible_to_students: bool


@dataclass
class PublishPlan:
    id: str
    title: str
    due: datetime
    due_quote: str
    published_at: datetime
    hints: str
    overview: str
    notes: str
    checklist: str
    moves: list[FileMove] = field(default_factory=list)
    guidelines_text: str = ""
    checklist_text: str = ""

    def card(self) -> dict:
        return {
            "assignment": self.id, "title": self.title,
            "due": fmt_dt(self.due), "due_iso": iso_minutes(self.due), "due_quote": self.due_quote,
            "files": [{"original": m.upload, "role": m.kind, "stored_as": m.dest_vpath,
                       "students": "see it" if m.visible_to_students else "hidden"} for m in self.moves],
            "guidelines": self.guidelines_text, "checklist": self.checklist_text,
        }


def _require_deadline(due: str | None, due_quote: str | None, now: datetime,
                      professor_texts: list[str]) -> datetime:
    if not due:
        raise AssignmentError("No deadline given. Ask the professor for the deadline (date and time) "
                              "before publishing; never guess it.")
    if not due_quote or not quote_found(due_quote, professor_texts):
        raise AssignmentError(
            "due_quote must be the professor's own words for the deadline, copied from their message "
            f"(got {due_quote!r}, which isn't in any professor message). If the professor hasn't "
            "given a deadline, ask for one.")
    try:
        when = parse_dt(due)
    except ValueError as err:
        raise AssignmentError(f"Couldn't read the deadline {due!r}; use YYYY-MM-DDTHH:MM.") from err
    if when <= now:
        raise AssignmentError(f"The deadline {fmt_dt(when)} is already past (now {fmt_dt(now)}). "
                              "Ask the professor to confirm the date.")
    return when


def plan_publish(rt: RuntimePaths, args: dict, now: datetime,
                 professor_texts: list[str]) -> PublishPlan:
    aid = normalize_id(str(args.get("assignment_id", "")))
    if load(rt.course, aid):
        raise AssignmentError(f"{aid.upper()} already exists. To change it, use update_assignment.")
    title = (args.get("title") or "").strip()
    if not title:
        raise AssignmentError("Missing title. Take it from the handout, or ask the professor.")
    due = _require_deadline(args.get("due"), args.get("due_quote"), now, professor_texts)
    hints = (args.get("hints_status") or "coming").strip().lower()
    if hints not in ("coming", "none"):
        raise AssignmentError("hints_status must be 'coming' or 'none'; hints are added later with save_hints.")

    files = args.get("files") or []
    overview = (args.get("overview") or "").strip()
    if not files and not overview:
        raise AssignmentError("Nothing to publish: attach the assignment file or describe it.")

    moves: list[FileMove] = []
    upload_dir = rt.upload_dir("professor")
    counts = {"handout": 0, "solution_total": sum(1 for f in files if f.get("kind") == "solution")}
    taken: set[str] = set()
    for f in files:
        upload, kind = str(f.get("upload", "")).strip(), str(f.get("kind", "")).strip().lower()
        if kind not in KINDS:
            raise AssignmentError(f"File {upload!r}: kind must be one of {', '.join(KINDS)}.")
        src = upload_dir / Path(upload).name
        if not upload or not src.is_file():
            raise AssignmentError(f"No attachment named {upload!r}. Attached files are listed under uploads/.")
        ext = Path(upload).suffix.lower()
        if kind == "handout":
            counts["handout"] += 1
            name = _numbered("handout", ext, counts["handout"])
            vp = f"memory/course/assignments/{aid}/{name}"
            real = rt.course / "assignments" / aid / name
            visible = True
        elif kind == "solution":
            name = f"solution{ext}" if counts["solution_total"] == 1 else clean_name(upload)
            vp = f"memory/course/solutions/{aid}/{name}"
            real = rt.course / "solutions" / aid / name
            visible = False
        else:
            name = clean_name(upload)
            vp = f"submission/{aid}/{name}"
            real = rt.repo / aid / name
            visible = True
        if vp in taken:
            raise AssignmentError(f"Two files would both be stored as {vp}; rename one or tag it differently.")
        taken.add(vp)
        moves.append(FileMove(upload, kind, vp, real, visible))

    plan = PublishPlan(
        id=aid, title=title, due=due, due_quote=str(args.get("due_quote")).strip(),
        published_at=now, hints=hints, overview=overview or f"See the handout for {aid.upper()}.",
        notes=(args.get("professor_notes") or "").strip(),
        checklist=(args.get("review_checklist") or "").strip(),
        moves=moves,
    )
    if not plan.checklist:
        raise AssignmentError("Missing review_checklist: list what a correct submission must do "
                              "(requirements only, never solution code).")
    plan.guidelines_text = render_guidelines(plan)
    plan.checklist_text = render_checklist(aid, title, plan.checklist)
    return plan


def render_guidelines(plan: PublishPlan) -> str:
    meta = {
        "id": plan.id, "title": plan.title, "due": iso_minutes(plan.due),
        "published_at": iso_minutes(plan.published_at), "hints": plan.hints,
        "files": {Path(m.dest_vpath).name: m.upload
                  for m in plan.moves if m.kind == "handout"},
    }
    notes = plan.notes or "_None._"
    body = (f"# {plan.id.upper()}: {plan.title}\n\n## Overview\n\n{plan.overview}\n\n"
            f"## Professor notes\n\n{notes}\n\n## Updates\n")
    return join_frontmatter(meta, body)


def render_checklist(aid: str, title: str, checklist: str) -> str:
    meta = {"name": f"assignment-review/{aid}",
            "description": f"Review checklist for {aid.upper()} ({title}). Loaded by assignment-review; "
                           "not used on its own.",
            "audience": "student"}
    return join_frontmatter(meta, f"# {aid.upper()} review checklist\n\n{checklist}\n")


def apply_publish(rt: RuntimePaths, plan: PublishPlan, git) -> str:
    gdir = rt.course / "assignments" / plan.id
    gdir.mkdir(parents=True, exist_ok=True)
    (gdir / "guidelines.md").write_text(plan.guidelines_text)
    cdir = rt.course / "skills" / "assignment-review" / plan.id
    cdir.mkdir(parents=True, exist_ok=True)
    (cdir / "SKILL.md").write_text(plan.checklist_text)

    src_dir = rt.upload_dir("professor")
    starter = False
    for m in plan.moves:
        m.dest_real.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_dir / Path(m.upload).name, m.dest_real)
        starter = starter or m.kind == "starter"
    main_dir = rt.repo / plan.id
    main_dir.mkdir(parents=True, exist_ok=True)
    if not starter:
        (main_dir / "README.md").write_text(
            f"# {plan.id.upper()}: {plan.title}\n\nPut your {plan.id.upper()} files in this folder. "
            f"The handout and guidelines are in memory/course/assignments/{plan.id}/.\n")
    sha = git.commit_all(rt.repo, f"Publish {plan.id.upper()}: {plan.title}", "professor",
                         when=plan.published_at)
    stored = "; ".join(f"{m.upload} -> {m.dest_vpath}" for m in plan.moves) or "no files"
    return (f"Published {plan.id.upper()} ({plan.title}), due {fmt_dt(plan.due)}. Stored: {stored}. "
            f"Guidelines at memory/course/assignments/{plan.id}/guidelines.md. "
            f"Commit {sha or '(no starter changes)'} on main.")


# -- updates --------------------------------------------------------------
@dataclass
class UpdatePlan:
    id: str
    old_due: datetime
    new_due: datetime | None
    due_quote: str | None
    note: str | None
    new_text: str
    old_text: str

    def card(self) -> dict:
        return {"assignment": self.id, "old_due": fmt_dt(self.old_due),
                "new_due": fmt_dt(self.new_due) if self.new_due else None,
                "due_quote": self.due_quote, "note": self.note,
                "before": self.old_text, "after": self.new_text}


def plan_update(rt: RuntimePaths, args: dict, now: datetime, professor_texts: list[str]) -> UpdatePlan:
    aid = normalize_id(str(args.get("assignment_id", "")))
    a = load(rt.course, aid)
    if not a:
        raise AssignmentError(f"{aid.upper()} doesn't exist. To create it, use publish_assignment.")
    new_due = None
    if args.get("due"):
        new_due = _require_deadline(args.get("due"), args.get("due_quote"), now, professor_texts)
    note = (args.get("note") or "").strip() or None
    if not new_due and not note:
        raise AssignmentError("Nothing to change: give a new deadline (with due_quote) or a note.")
    path = guidelines_path(rt.course, aid)
    old_text = path.read_text()
    meta, body = split_frontmatter(old_text)
    stamp = fmt_dt(now)
    lines = []
    if new_due:
        meta["due"] = iso_minutes(new_due)
        lines.append(f"- {stamp}: Deadline moved from {fmt_dt(a.due)} to {fmt_dt(new_due)}.")
    if note:
        lines.append(f"- {stamp}: {note}")
    body = append_under_heading(body, "Updates", "\n".join(lines))
    return UpdatePlan(aid, a.due, new_due, args.get("due_quote"), note,
                      join_frontmatter(meta, body), old_text)


def apply_update(rt: RuntimePaths, plan: UpdatePlan) -> str:
    guidelines_path(rt.course, plan.id).write_text(plan.new_text)
    parts = []
    if plan.new_due:
        parts.append(f"deadline is now {fmt_dt(plan.new_due)}")
    if plan.note:
        parts.append("note added")
    return f"Updated {plan.id.upper()}: " + "; ".join(parts) + ". Logged under Updates in guidelines.md."


def set_hints_status(rt: RuntimePaths, aid: str, status: str, now: datetime, message: str) -> None:
    path = guidelines_path(rt.course, aid)
    meta, body = split_frontmatter(path.read_text())
    meta["hints"] = status
    body = append_under_heading(body, "Updates", f"- {fmt_dt(now)}: {message}")
    path.write_text(join_frontmatter(meta, body))
