"""Workspace: every tool's real behavior, plus the checks and previews around it.

The LangChain layer (harness/lc) wraps these methods as tools; the UI uses the
same object for the files panel and approval cards. Nothing here imports
LangChain, so all of it is testable without a model.
"""
from __future__ import annotations

import difflib
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from . import assignments as A
from . import hints as H
from . import skills as S
from .access import ACCESS_FILE, HIDDEN, READ, AccessManifest
from .calendar import Calendar, describe_blocks
from .clock import Clock, fmt_dt, fmt_time, parse_dt
from .gitops import Git
from .identity import Identity
from .mdutil import append_under_heading
from .memory_files import remember_text
from .paths import PathError, VPath, available_roots, resolve
from .policy import ALLOW, LIST, NOT_FOUND, READ as R, WRITE, Decision, can, deny
from .runtime import RuntimePaths

MAX_READ = 40_000
PROFESSOR_ONLY = {"publish_assignment", "update_assignment", "save_hints", "set_student_access"}
STUDENT_ONLY = {"get_hint", "list_events", "find_free_time", "add_event"}
ALL_TOOLS = [
    "list_files", "read_file", "write_file", "append_to_file", "save_upload", "remember",
    "load_skill", "list_assignments", "publish_assignment", "update_assignment", "save_hints",
    "set_student_access", "get_hint", "commit_changes", "submission_status", "list_events",
    "find_free_time", "add_event",
]
# Tools that always pause for approval, and those that pause only for course memory.
ALWAYS_APPROVE = {"publish_assignment", "update_assignment", "save_hints", "set_student_access",
                  "commit_changes", "add_event"}
COURSE_WRITE_TOOLS = {"write_file", "append_to_file", "save_upload"}


class ToolRefusal(Exception):
    """A refusal the model should read and explain, not retry around."""


def tools_for_role(role: str) -> list[str]:
    if role == "professor":
        return [t for t in ALL_TOOLS if t not in STUDENT_ONLY]
    return [t for t in ALL_TOOLS if t not in PROFESSOR_ONLY]


def needs_approval(name: str, args: dict) -> bool:
    """The conditional-pause predicate. Path or scope alone: the permission gate has
    already denied any student write to course memory before this is asked."""
    if name in ALWAYS_APPROVE:
        return True
    if name in COURSE_WRITE_TOOLS:
        return str(args.get("path", "")).strip().lstrip("./").startswith("memory/course")
    if name == "remember":
        return str(args.get("scope", "")).strip() == "course"
    return False


def _wrap(vpath: str, text: str) -> str:
    return f'<file path="{vpath}" trust="untrusted">\n{text}\n</file>'


def _read_text(path: Path) -> str | None:
    if path.suffix.lower() == ".pdf":
        try:
            from pypdf import PdfReader  # optional dependency
            return "\n\n".join((p.extract_text() or "") for p in PdfReader(str(path)).pages)
        except Exception:
            return None
    try:
        return path.read_text()
    except UnicodeDecodeError:
        return None


def _commit_meta(b: dict) -> str:
    """'Submit HW2, Nov 23' for a branch's last commit."""
    if not b.get("date"):
        return ""
    try:
        d = datetime.fromisoformat(b["date"])
        return f"{b['subject']}, {d:%b} {d.day}"
    except ValueError:
        return b["subject"]


def _sort_dirs_first(node: dict) -> None:
    node["children"].sort(key=lambda c: (not c["is_dir"], c["name"].lower()))
    for c in node["children"]:
        _sort_dirs_first(c)


class Workspace:
    def __init__(self, rt: RuntimePaths, ident: Identity, enforce: bool = True,
                 clock: Clock | None = None, user_texts: list[str] | None = None):
        self.rt = rt
        self.ident = ident
        self.enforce = enforce
        self.clock = clock or Clock(rt.state)
        self.git = Git(rt)
        self.user_texts = list(user_texts or [])

    # ------------------------------------------------------------------ basics
    @property
    def manifest(self) -> AccessManifest:
        return AccessManifest(self.rt.course)  # re-read on every check, never cached

    def now(self) -> datetime:
        return self.clock.now()

    def _vp(self, path: str) -> VPath:
        try:
            return resolve(self.rt, self.ident, path)
        except PathError as err:
            raise ToolRefusal(str(err)) from err

    def _need(self, decision: Decision) -> None:
        if self.enforce and not decision:
            raise ToolRefusal(decision.reason)

    def _can(self, action: str, vp: VPath) -> Decision:
        return can(self.ident, action, vp, self.manifest)

    def assignment_visible(self, aid: str) -> bool:
        if self.ident.is_professor or not self.enforce:
            return True
        m = self.manifest
        return not (m.is_hidden(f"assignments/{aid}", is_dir=True)
                    or m.is_hidden(f"assignments/{aid}/guidelines.md"))

    # ------------------------------------------------------------------ checks
    def check(self, name: str, args: dict) -> Decision:
        """What the permission-gate middleware asks before any tool runs."""
        if not self.enforce:
            return ALLOW
        if name not in ALL_TOOLS:
            return deny(f"Unknown tool {name}.")
        if self.ident.is_student and name in PROFESSOR_ONLY:
            return deny("Only the professor can do that.")
        if self.ident.is_professor and name in STUDENT_ONLY:
            return deny("That tool is for students.")
        try:
            if name == "list_files":
                path = (args.get("path") or "").strip()
                if path in ("", ".", "/", "memory"):
                    return ALLOW
                return self._can(LIST, resolve(self.rt, self.ident, path))
            if name == "read_file":
                return self._can(R, resolve(self.rt, self.ident, args.get("path", "")))
            if name in ("write_file", "append_to_file"):
                return self._can(WRITE, resolve(self.rt, self.ident, args.get("path", "")))
            if name == "save_upload":
                src = resolve(self.rt, self.ident, "uploads/" + Path(str(args.get("upload", ""))).name)
                d = self._can(R, src)
                return d if not d else self._can(WRITE, resolve(self.rt, self.ident, args.get("path", "")))
            if name == "remember":
                scope = str(args.get("scope", "me"))
                if scope == "course" and not self.ident.is_professor:
                    return deny("Only the professor can add to course memory.")
                if scope == "me" and not self.ident.is_student:
                    return deny("The professor has no personal memory here; use scope 'course'.")
                if scope not in ("me", "course"):
                    return deny("scope must be 'me' or 'course'.")
            if name == "set_student_access":
                vp = resolve(self.rt, self.ident, args.get("path", ""))
                if vp.root != "course" or not vp.rel or vp.rel == ACCESS_FILE:
                    return deny("Only files and folders inside memory/course/ have student access settings.")
        except PathError as err:
            return deny(str(err))
        return ALLOW

    # ------------------------------------------------------------------ user setup
    def ensure_user(self) -> str | None:
        """Create a student's memory folder and branch on first login; sync main."""
        if self.ident.is_professor:
            return None
        udir = self.rt.user_dir(self.ident.username)
        if not udir.exists():
            for sub in ("notes/lectures", "notes/assignments", "notes/general", "skills"):
                (udir / sub).mkdir(parents=True, exist_ok=True)
            (udir / "MEMORY.md").write_text(
                f"# Memory for {self.ident.username}\n\n"
                "Preferences and facts I asked the assistant to remember.\n\n## Updates\n")
        self.git.ensure_student_worktree(self.ident.username)
        return self.git.sync_main_into(self.ident.username)

    def stage_upload(self, filename: str, data: bytes) -> str:
        name = Path(filename.replace("\\", "/")).name.strip() or "upload"
        dest = self.rt.upload_dir(self.ident.username)
        dest.mkdir(parents=True, exist_ok=True)
        (dest / name).write_bytes(data)
        return name

    # ------------------------------------------------------------------ files
    def list_files(self, path: str = "") -> str:
        path = (path or "").strip()
        if path in ("", ".", "/", "memory"):
            return "Top-level folders:\n" + "\n".join(f"- {r}/" for r in available_roots(self.ident))
        vp = self._vp(path)
        self._need(self._can(LIST, vp))
        if vp.root == "submissions":
            return self._list_submissions(vp)
        if not vp.real or not vp.real.exists():
            return NOT_FOUND
        if vp.real.is_file():
            return f"{vp.vpath} is a file ({vp.real.stat().st_size} bytes)."
        m = self.manifest
        lines = []
        for child in sorted(vp.real.iterdir()):
            if child.name.startswith(".") or child.name == "__pycache__":
                continue
            rel = f"{vp.rel}/{child.name}".strip("/")
            hidden = vp.root == "course" and m.is_hidden(rel, is_dir=child.is_dir())
            if hidden and self.ident.is_student and self.enforce:
                continue
            tag = " [hidden from students]" if hidden else ""
            lines.append(f"- {child.name}{'/' if child.is_dir() else ''}{tag}")
        return f"{vp.vpath}/\n" + ("\n".join(lines) if lines else "(empty)")

    def _list_submissions(self, vp: VPath) -> str:
        if not vp.branch:
            rows = [b for b in self.git.branches() if b["branch"] != "main"]
            if not rows:
                return "No student branches yet."
            return "Student branches:\n" + "\n".join(
                f"- submissions/{b['branch']}/ (last commit {b['date'][:16]}: {b['subject']})" for b in rows)
        try:
            entries = self.git.ls_tree(vp.branch, vp.rel)
        except FileNotFoundError:
            return NOT_FOUND
        return f"{vp.vpath}/ (last commit)\n" + "\n".join(
            f"- {n}{'/' if k == 'dir' else ''}" for n, k in entries)

    def read_file(self, path: str) -> str:
        vp = self._vp(path)
        self._need(self._can(R, vp))
        if vp.root == "submissions":
            if not vp.branch or not vp.rel:
                return self._list_submissions(vp)
            try:
                return _wrap(vp.vpath, self.git.show(vp.branch, vp.rel)[:MAX_READ])
            except FileNotFoundError:
                return NOT_FOUND
        if not vp.real or not vp.real.exists():
            return NOT_FOUND
        if vp.real.is_dir():
            return self.list_files(path)
        text = _read_text(vp.real)
        if text is None:
            return f"{vp.vpath} is a binary file ({vp.real.stat().st_size} bytes) and can't be shown as text."
        note = "\n[truncated]" if len(text) > MAX_READ else ""
        return _wrap(vp.vpath, text[:MAX_READ] + note)

    def _writable(self, path: str) -> VPath:
        vp = self._vp(path)
        self._need(self._can(WRITE, vp))
        if vp.real is None or not vp.rel:
            raise ToolRefusal("Give a file path, not a folder.")
        if vp.real.is_dir():
            raise ToolRefusal(f"{vp.vpath} is a folder; give a file path.")
        return vp

    def write_file(self, path: str, content: str) -> str:
        vp = self._writable(path)
        existed = vp.real.exists()
        vp.real.parent.mkdir(parents=True, exist_ok=True)
        vp.real.write_text(content)
        return f"{'Replaced' if existed else 'Created'} {vp.vpath} ({len(content)} characters)."

    def append_to_file(self, path: str, text: str, under_heading: str | None = None) -> str:
        vp = self._writable(path)
        current = vp.real.read_text() if vp.real.exists() else ""
        vp.real.parent.mkdir(parents=True, exist_ok=True)
        vp.real.write_text(append_under_heading(current, under_heading, text))
        where = f" under '{under_heading}'" if under_heading else ""
        return f"Appended to {vp.vpath}{where}."

    def save_upload(self, upload: str, path: str) -> str:
        name = Path(str(upload)).name
        src_vp = self._vp(f"uploads/{name}")
        self._need(self._can(R, src_vp))
        if not src_vp.real or not src_vp.real.is_file():
            raise ToolRefusal(f"No attachment named {name!r} in uploads/.")
        vp = self._vp(path)
        self._need(self._can(WRITE, vp))
        dest = vp.real / name if (vp.real.is_dir() or path.endswith("/")) else vp.real
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_vp.real, dest)
        shown = f"{vp.vpath}/{name}" if dest.name == name and dest != vp.real else vp.vpath
        return f"Saved attachment {name} as {shown}."

    # ------------------------------------------------------------------ memory & skills
    def _memory_file(self, scope: str) -> tuple[Path, str]:
        if scope == "course":
            if not self.ident.is_professor and self.enforce:
                raise ToolRefusal("Only the professor can add to course memory.")
            return self.rt.course / "COURSE.md", "memory/course/COURSE.md"
        if scope == "me":
            if not self.ident.is_student:
                raise ToolRefusal("The professor has no personal memory here; use scope 'course'.")
            return self.rt.user_dir(self.ident.username) / "MEMORY.md", "memory/me/MEMORY.md"
        raise ToolRefusal("scope must be 'me' or 'course'.")

    def remember(self, text: str, scope: str = "me") -> str:
        path, vpath = self._memory_file(scope)
        current = path.read_text() if path.exists() else ""
        path.write_text(remember_text(current, text, self.now()))
        return f"Remembered in {vpath}."

    def load_skill(self, name: str) -> str:
        return S.load(self.rt, self.ident, self.manifest, name)

    # ------------------------------------------------------------------ assignments
    def list_assignments(self, published_after: str | None = None, open_only: bool = False) -> str:
        now = self.now()
        after = None
        if published_after:
            try:
                after = parse_dt(published_after) if len(published_after.strip()) > 10 \
                    else datetime.fromisoformat(published_after.strip())
            except ValueError:
                raise ToolRefusal("published_after must be an ISO date or date-time, e.g. 2026-11-30T00:00.")
        rows = []
        for a in A.all_assignments(self.rt.course):
            if not self.assignment_visible(a.id):
                continue
            if after and (a.published_at is None or a.published_at < after):
                continue
            if open_only and a.status(now) != "open":
                continue
            rows.append(a)
        rows.sort(key=lambda a: a.due)
        if not rows:
            what = "open " if open_only else ""
            since = f" published since {fmt_dt(after)}" if after else ""
            return f"No {what}assignments{since}."
        header = f"Now: {fmt_dt(now)}."
        return header + "\n" + "\n".join(A.describe(a, now) for a in rows)

    def publish_assignment(self, **args) -> str:
        self._need(Decision(self.ident.is_professor, "Only the professor can publish assignments."))
        try:
            plan = A.plan_publish(self.rt, args, self.now(), self.user_texts)
            return A.apply_publish(self.rt, plan, self.git)
        except A.AssignmentError as err:
            raise ToolRefusal(str(err)) from err

    def update_assignment(self, **args) -> str:
        self._need(Decision(self.ident.is_professor, "Only the professor can change assignments."))
        try:
            plan = A.plan_update(self.rt, args, self.now(), self.user_texts)
            return A.apply_update(self.rt, plan)
        except A.AssignmentError as err:
            raise ToolRefusal(str(err)) from err

    def save_hints(self, assignment_id: str, levels: list[str]) -> str:
        self._need(Decision(self.ident.is_professor, "Only the professor can add hints."))
        try:
            aid, _, text = H.plan_save(self.rt, assignment_id, levels)
        except A.AssignmentError as err:
            raise ToolRefusal(str(err)) from err
        return H.apply_save(self.rt, aid, text, self.now())

    def get_hint(self, assignment_id: str) -> str:
        if not self.ident.is_student:
            raise ToolRefusal("Hints are released to students.")
        try:
            aid = A.normalize_id(assignment_id)
        except A.AssignmentError as err:
            raise ToolRefusal(str(err)) from err
        if not self.assignment_visible(aid):
            return f"There is no {aid.upper()}."
        return H.next_hint(self.rt, self.ident.username, aid)

    def set_student_access(self, path: str, access: str) -> str:
        self._need(self.check("set_student_access", {"path": path}))
        vp = self._vp(path)
        if access not in (READ, HIDDEN):
            raise ToolRefusal("access must be 'read' or 'hidden'.")
        if not vp.real or not vp.real.exists():
            raise ToolRefusal(f"{vp.vpath} doesn't exist.")
        key = self.manifest.set(vp.rel, access, is_dir=vp.real.is_dir())
        state = "visible to students" if access == READ else "hidden from students"
        return f"{vp.vpath} is now {state} (rule '{key}: {access}')."

    # ------------------------------------------------------------------ submissions
    def commit_changes(self, message: str) -> str:
        wt = self.rt.worktree(self.ident.branch)
        if self.ident.is_student:
            problem = self.git.sync_main_into(self.ident.username, when=self.now())
            if problem:
                raise ToolRefusal(problem)
        msg = (message or "").strip() or "Update"
        sha = self.git.commit_all(wt, msg, self.ident.username, when=self.now())
        if not sha:
            return "Nothing to commit: no changes in your submission folder."
        files = self.git.run("show", "--name-only", "--format=", "HEAD", cwd=wt).split()
        return f"Committed {sha} on branch {self.ident.branch}: {msg}. Files: {', '.join(files)}."

    def submission_status(self, assignment_id: str) -> str:
        try:
            aid = A.normalize_id(assignment_id)
        except A.AssignmentError as err:
            raise ToolRefusal(str(err)) from err
        a = A.load(self.rt.course, aid)
        if not a or not self.assignment_visible(aid):
            return f"There is no {aid.upper()}."
        now = self.now()
        head = f"{aid.upper()} is due {fmt_dt(a.due)} ({a.status(now)}; late policy: 10%/day, {A.LATE_DAYS} days max)."
        prefix = f"{aid}/"
        if self.ident.is_professor:
            rows = []
            for branch in self.git.student_branches():
                files = [f for f in self.git.committed_changes(branch, prefix)]
                last = self.git.last_commit_touching(branch, prefix) if files else None
                if files and last:
                    rows.append(f"- {branch}: submitted ({', '.join(files)}), last commit {last['date']} "
                                f"\"{last['subject']}\"")
                else:
                    rows.append(f"- {branch}: nothing committed for {aid.upper()}")
            return head + "\n" + ("\n".join(rows) if rows else "No students yet.")
        wt = self.rt.worktree(self.ident.username)
        committed = self.git.committed_changes(self.ident.username, prefix)
        pending = [l[3:] for l in self.git.run("status", "--porcelain", "-uall", "--", prefix,
                                                cwd=wt).splitlines() if l.strip()]
        differs = self.git.worktree_differs_from_main(wt, prefix)
        parts = [head]
        parts.append(f"Committed for {aid.upper()}: {', '.join(committed) if committed else 'nothing yet'}.")
        parts.append(f"Uncommitted changes: {', '.join(pending) if pending else 'none'}.")
        parts.append("Your files differ from the starter." if differs
                     else "Your folder matches the starter files exactly (nothing of yours yet).")
        return "\n".join(parts)

    # ------------------------------------------------------------------ calendar
    def _calendar(self) -> Calendar:
        if not self.ident.is_student:
            raise ToolRefusal("The calendar belongs to students.")
        return Calendar(self.rt, self.ident.username)

    @staticmethod
    def _range(start: str, end: str) -> tuple[datetime, datetime]:
        try:
            s, e = parse_dt(start), parse_dt(end)
        except ValueError:
            raise ToolRefusal("Use ISO date-times like 2026-12-01T14:00.")
        if len(start.strip()) == 10:
            s = s.replace(hour=0, minute=0)
        if e <= s:
            raise ToolRefusal("end must be after start.")
        return s, e

    def list_events(self, start: str, end: str) -> str:
        s, e = self._range(start, end)
        events = self._calendar().list_events(s, e)
        if not events:
            return f"No events between {fmt_dt(s)} and {fmt_dt(e)}."
        lines, day = [], None
        for ev in events:
            if ev.start.date() != day:
                day = ev.start.date()
                lines.append(f"{ev.start:%a %b} {ev.start.day}:")
            tag = " (added by you)" if ev.added else ""
            lines.append(f"- {fmt_time(ev.start)} to {fmt_time(ev.end)}: {ev.title}{tag}")
        return "\n".join(lines)

    def find_free_time(self, start: str, end: str, earliest: str = "09:00", latest: str = "22:00") -> str:
        s, e = self._range(start, end)
        try:
            blocks = self._calendar().free_time(s, e, earliest, latest)
        except ValueError:
            raise ToolRefusal("earliest and latest must look like 09:00 and 22:00.")
        return f"Free time between {earliest} and {latest} each day:\n" + describe_blocks(blocks)

    def add_event(self, title: str, start: str, end: str) -> str:
        cal = self._calendar()
        s, e = parse_dt(start), parse_dt(end)
        clashes = [x for x in cal.overlaps(s, e)]
        ev = cal.add_event(title, s, e)
        note = f" It overlaps: {', '.join(x.title for x in clashes)}." if clashes else ""
        return f"Added '{ev.title}' on {fmt_dt(ev.start)} to {fmt_time(ev.end)}.{note}"

    # ------------------------------------------------------------------ dispatch
    def call(self, name: str, args: dict) -> str:
        """Run a tool by name; refusals come back as text the model can read."""
        fn = getattr(self, name, None)
        if name not in ALL_TOOLS or fn is None:
            return f"Error: unknown tool {name}."
        try:
            return fn(**args)
        except ToolRefusal as err:
            return f"Refused: {err}"
        except (TypeError, ValueError) as err:
            return f"Error: bad arguments for {name}: {err}"

    # ------------------------------------------------------------------ approval previews
    def preview(self, name: str, args: dict) -> dict:
        """What the approval card shows, computed by the app rather than described
        by the model."""
        try:
            if name == "publish_assignment":
                plan = A.plan_publish(self.rt, args, self.now(), self.user_texts)
                return {"kind": "publish", **plan.card()}
            if name == "update_assignment":
                plan = A.plan_update(self.rt, args, self.now(), self.user_texts)
                return {"kind": "update", **plan.card()}
            if name == "save_hints":
                aid, old, new = H.plan_save(self.rt, args.get("assignment_id", ""), args.get("levels") or [])
                return self._file_change(f"memory/course/skills/hints/{aid}/SKILL.md", old, new,
                                         note="Hidden from students; released one level at a time.")
            if name in ("write_file", "append_to_file", "save_upload", "remember"):
                return self._preview_write(name, args)
            if name == "set_student_access":
                return self._preview_access(args)
            if name == "commit_changes":
                wt = self.rt.worktree(self.ident.branch)
                return {"kind": "commit", "branch": self.ident.branch,
                        "message": args.get("message", ""), **self.git.preview_commit(wt)}
            if name == "add_event":
                s, e = parse_dt(args.get("start", "")), parse_dt(args.get("end", ""))
                overlaps = Calendar(self.rt, self.ident.username).overlaps(s, e)
                return {"kind": "event", "title": args.get("title", ""), "start": fmt_dt(s),
                        "end": fmt_time(e), "overlaps": [f"{x.title} ({fmt_time(x.start)} to "
                                                         f"{fmt_time(x.end)})" for x in overlaps]}
        except (A.AssignmentError, ToolRefusal, PathError, ValueError) as err:
            return {"kind": "error", "error": str(err)}
        return {"kind": "generic", "args": args}

    def _file_change(self, vpath: str, before: str, after: str, note: str = "") -> dict:
        diff = "".join(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                                            fromfile=f"{vpath} (before)", tofile=f"{vpath} (after)"))
        return {"kind": "file_change", "path": vpath, "is_new": before == "", "before": before,
                "after": after, "diff": diff, "note": note}

    def _preview_write(self, name: str, args: dict) -> dict:
        if name == "remember":
            path, vpath = self._memory_file(str(args.get("scope", "me")))
            before = path.read_text() if path.exists() else ""
            return self._file_change(vpath, before, remember_text(before, args.get("text", ""), self.now()))
        vp = self._vp(args.get("path", ""))
        if vp.real is None:
            raise ToolRefusal("Not a writable path.")
        if name == "save_upload":
            src = self.rt.upload_dir(self.ident.username) / Path(str(args.get("upload", ""))).name
            dest = vp.real / src.name if vp.real.is_dir() else vp.real
            before = (_read_text(dest) or "") if dest.exists() else ""
            after = _read_text(src) if src.exists() else None
            change = self._file_change(vp.vpath if dest == vp.real else f"{vp.vpath}/{src.name}",
                                       before, after if after is not None else "[binary file]")
            change["note"] = f"Copied from attachment {src.name}."
            return change
        before = vp.real.read_text() if vp.real.is_file() else ""
        if name == "write_file":
            after = args.get("content", "")
        else:
            after = append_under_heading(before, args.get("under_heading"), args.get("text", ""))
        return self._file_change(vp.vpath, before, after)

    def _preview_access(self, args: dict) -> dict:
        vp = self._vp(args.get("path", ""))
        access = args.get("access", "")
        info = None
        parts = vp.rel.split("/")
        if access == READ and len(parts) >= 2 and parts[0] == "solutions":
            a = A.load(self.rt.course, parts[1])
            if a:
                now = self.now()
                closes = a.due + timedelta(days=A.LATE_DAYS)
                info = (f"{a.id.upper()} was due {fmt_dt(a.due)}; the late window "
                        f"{'closed' if now >= closes else 'closes'} {fmt_dt(closes)}.")
                if now < closes:
                    info += " Students can still submit."
        return {"kind": "access", "path": vp.vpath, "access": access,
                "is_dir": bool(vp.real and vp.real.is_dir()), "deadline_info": info}

    # ------------------------------------------------------------------ files panel
    def tree(self) -> list[dict]:
        """Nodes for the files panel, filtered exactly like list_files.

        Students never get nodes for files hidden from them; the professor gets
        them with locked=True so the UI can show a lock.
        """
        course = self._tree_node("memory/course", self.rt.course, "course", "")
        course.update(label="Course memory", readonly=self.ident.is_student)
        nodes = [course]
        if self.ident.is_student:
            me = self._tree_node("memory/me", self.rt.user_dir(self.ident.username), "me", "")
            me["label"] = "My memory"
            sub = self._tree_node("submission", self.rt.worktree(self.ident.username), "submission", "")
            sub["label"] = f"My submission (branch {self.ident.username})"
            nodes += [me, sub]
        else:
            users = sorted(p.name for p in self.rt.users.iterdir()) if self.rt.users.exists() else []
            nodes.append({"vpath": "memory/users", "name": "users", "label": "Students' memory",
                          "is_dir": True, "locked": False,
                          "children": [{"vpath": f"memory/users/{u}", "name": u, "is_dir": True,
                                        "locked": False, "children": [], "opaque": True,
                                        "meta": "private"} for u in users]})
            main = self._tree_node("submission", self.rt.repo, "submission", "")
            main["label"] = "Starter code (branch main)"
            nodes.append(main)
            nodes.append(self._submissions_node())
        return nodes

    def _tree_node(self, vpath: str, real: Path, root: str, rel: str) -> dict:
        m = self.manifest
        node = {"vpath": vpath, "name": vpath.rsplit("/", 1)[-1], "is_dir": real.is_dir(),
                "locked": False, "children": []}
        if real.is_dir():
            for child in sorted(real.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
                if child.name.startswith(".") or child.name == "__pycache__":
                    continue
                crel = f"{rel}/{child.name}".strip("/")
                hidden = root == "course" and m.is_hidden(crel, is_dir=child.is_dir())
                if hidden and self.ident.is_student:
                    continue
                sub = self._tree_node(f"{vpath}/{child.name}", child, root, crel)
                sub["locked"] = hidden
                node["children"].append(sub)
        return node

    def _submissions_node(self) -> dict:
        """Professor only: each student's last commit, read from git."""
        root = {"vpath": "submissions", "name": "submissions", "label": "Student submissions",
                "is_dir": True, "locked": False, "children": []}
        for b in self.git.branches():
            if b["branch"] == "main":
                continue
            branch = {"vpath": f"submissions/{b['branch']}", "name": b["branch"], "is_dir": True,
                      "locked": False, "children": [],
                      "meta": _commit_meta(b)}
            for path, _sha in self.git.ls_tree_recursive(b["branch"]):
                parts = path.split("/")
                parent = branch
                for i, part in enumerate(parts):
                    vpath = f"submissions/{b['branch']}/" + "/".join(parts[:i + 1])
                    is_dir = i < len(parts) - 1
                    found = next((c for c in parent["children"] if c["vpath"] == vpath), None)
                    if not found:
                        found = {"vpath": vpath, "name": part, "is_dir": is_dir, "locked": False, "children": []}
                        parent["children"].append(found)
                    parent = found
            _sort_dirs_first(branch)
            root["children"].append(branch)
        return root

    def read_for_ui(self, vpath: str) -> str | None:
        """File text for the viewer, or None if the user can't see it (or it's binary)."""
        try:
            vp = resolve(self.rt, self.ident, vpath)
        except PathError:
            return None
        if not self._can(R, vp):
            return None
        if vp.root == "submissions":
            if not vp.branch or not vp.rel:
                return None
            try:
                return self.git.show(vp.branch, vp.rel)
            except FileNotFoundError:
                return None
        if not vp.real or not vp.real.is_file():
            return None
        return _read_text(vp.real)

    def snapshot(self) -> dict[str, str]:
        """vpath -> a change signature for every file the user can see, so the UI
        can mark what the last turn changed."""
        out = {}

        def walk(nodes):
            for n in nodes:
                if n.get("opaque") or n["vpath"].startswith("submissions"):
                    continue
                if n["is_dir"]:
                    walk(n["children"])
                else:
                    try:
                        vp = resolve(self.rt, self.ident, n["vpath"])
                        st = vp.real.stat()
                        out[n["vpath"]] = f"{st.st_mtime_ns}:{st.st_size}"
                    except (PathError, OSError, AttributeError):
                        pass
        walk(self.tree())
        return out
