"""Virtual paths: the only paths the model ever sees.

    memory/course/...          the course memory tree (everyone; students read-only)
    memory/me/...              the student's own memory folder (students only)
    submission/...             the user's own worktree (professor: main)
    submissions/<student>/...  a student's last commit, read-only (professor only)
    uploads/...                files the user attached in chat

A virtual path can never name another student's folder or escape its root.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .identity import Identity
from .runtime import RuntimePaths

ROOTS = {
    "memory/course": "course",
    "memory/me": "me",
    "submission": "submission",
    "submissions": "submissions",
    "uploads": "uploads",
}


class PathError(Exception):
    """A path the user's role can't name at all."""


@dataclass(frozen=True)
class VPath:
    vpath: str          # normalized virtual path
    root: str           # course | me | submission | submissions | uploads
    rel: str            # path inside the root; "" is the root itself
    real: Path | None   # on-disk path; None for submissions/<student> (read from git)
    branch: str | None = None  # the student branch, for submissions/<student>

    @property
    def name(self) -> str:
        return self.rel.rsplit("/", 1)[-1] if self.rel else self.vpath.rsplit("/", 1)[-1]

    def child(self, name: str) -> str:
        return f"{self.vpath}/{name}"


def normalize(vpath: str) -> str:
    raw = (vpath or "").strip().replace("\\", "/")
    if raw.startswith("/"):
        raise PathError("Use a virtual path such as memory/course/COURSE.md, not an absolute path.")
    parts = []
    for part in raw.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            raise PathError("'..' is not allowed in paths.")
        parts.append(part)
    return "/".join(parts)


def available_roots(ident: Identity) -> list[str]:
    roots = ["memory/course"]
    if ident.is_student:
        roots.append("memory/me")
    roots.append("submission")
    if ident.is_professor:
        roots.append("submissions")
    roots.append("uploads")
    return roots


def resolve(rt: RuntimePaths, ident: Identity, vpath: str) -> VPath:
    norm = normalize(vpath)
    parts = norm.split("/") if norm else []
    if not parts:
        raise PathError("Empty path. Start from one of: " + ", ".join(available_roots(ident)))

    if parts[0] == "memory":
        if len(parts) < 2 or parts[1] not in ("course", "me"):
            raise PathError("Inside memory/ use memory/course/ or memory/me/.")
        if parts[1] == "me":
            if not ident.is_student:
                raise PathError("memory/me/ exists only for students.")
            base = rt.user_dir(ident.username)
            return _inside(norm, "me", base, parts[2:])
        return _inside(norm, "course", rt.course, parts[2:])

    if parts[0] == "submission":
        return _inside(norm, "submission", rt.worktree(ident.branch), parts[1:])

    if parts[0] == "submissions":
        if not ident.is_professor:
            raise PathError("Only the professor can read other students' submissions.")
        if len(parts) == 1:
            return VPath(norm, "submissions", "", None, None)
        student = parts[1]
        return VPath(norm, "submissions", "/".join(parts[2:]), None, student)

    if parts[0] == "uploads":
        return _inside(norm, "uploads", rt.upload_dir(ident.username), parts[1:])

    raise PathError(
        f"Unknown location '{parts[0]}'. Paths start with one of: "
        + ", ".join(available_roots(ident))
    )


def _inside(norm: str, root: str, base: Path, rest: list[str]) -> VPath:
    real = base.joinpath(*rest) if rest else base
    # Block symlinks that point outside the root.
    base_resolved = base.resolve()
    real_resolved = real.resolve()
    if real_resolved != base_resolved and base_resolved not in real_resolved.parents:
        raise PathError("That path leaves its folder.")
    return VPath(norm, root, "/".join(rest), real, None)
