"""can(): the single source of truth for who may touch what.

Tools, uploads, the files panel and the permission-gate middleware all call it.
"""
from __future__ import annotations

from dataclasses import dataclass

from .access import ACCESS_FILE, AccessManifest
from .identity import Identity
from .paths import VPath

READ = "read"
LIST = "list"
WRITE = "write"

# Neutral wording on purpose: a student can't tell a hidden file exists.
NOT_FOUND = "No such file or folder."


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str = ""

    def __bool__(self) -> bool:
        return self.allowed


ALLOW = Decision(True)


def deny(reason: str) -> Decision:
    return Decision(False, reason)


def can(ident: Identity, action: str, vp: VPath, manifest: AccessManifest) -> Decision:
    if action not in (READ, LIST, WRITE):
        raise ValueError(action)

    if vp.root == "course":
        if ident.is_professor:
            if action == WRITE and vp.rel == ACCESS_FILE:
                return deny("Change who can see a file with set_student_access, not by editing ACCESS.yaml.")
            return ALLOW
        if action == WRITE:
            return deny("Course files are read-only for students.")
        is_dir = bool(vp.real and vp.real.is_dir())
        if manifest.is_hidden(vp.rel, is_dir=is_dir):
            return deny(NOT_FOUND)
        return ALLOW

    if vp.root == "me":
        return ALLOW if ident.is_student else deny("memory/me/ exists only for students.")

    if vp.root == "submission":
        return ALLOW

    if vp.root == "submissions":
        if not ident.is_professor:
            return deny("Only the professor can read other students' submissions.")
        if action == WRITE:
            return deny("Student submissions are read-only.")
        return ALLOW

    if vp.root == "uploads":
        if action == WRITE:
            return deny("Uploads come from chat attachments; copy one out with save_upload.")
        return ALLOW

    return deny(f"Unknown location {vp.root}.")
