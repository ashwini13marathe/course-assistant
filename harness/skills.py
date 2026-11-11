"""Skills: folders with a SKILL.md (frontmatter: name, description, audience).

Course skills live in memory/course/skills/<name>/; per-assignment sub-skills in
<name>/<hwN>/. Students' personal skills live in memory/me/skills/<name>/.
The index sent each turn lists only top-level skills for the user's role.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .access import AccessManifest
from .identity import Identity
from .mdutil import split_frontmatter
from .runtime import RuntimePaths


@dataclass
class Skill:
    name: str
    description: str
    audience: str
    scope: str        # course | personal
    path: Path


def _read(path: Path, scope: str, name: str) -> Skill | None:
    if not path.is_file():
        return None
    meta, _ = split_frontmatter(path.read_text())
    return Skill(name=name, description=str(meta.get("description", "")).strip(),
                 audience=str(meta.get("audience", "all")), scope=scope, path=path)


def _visible_course_rel(rel: str, ident: Identity, manifest: AccessManifest) -> bool:
    return ident.is_professor or not manifest.is_hidden(rel)


def index(rt: RuntimePaths, ident: Identity, manifest: AccessManifest) -> list[Skill]:
    out = []
    root = rt.course / "skills"
    if root.is_dir():
        for d in sorted(root.iterdir()):
            s = _read(d / "SKILL.md", "course", d.name)
            if not s or s.audience not in (ident.role, "all"):
                continue
            if _visible_course_rel(f"skills/{d.name}/SKILL.md", ident, manifest):
                out.append(s)
    if ident.is_student:
        proot = rt.user_dir(ident.username) / "skills"
        if proot.is_dir():
            for d in sorted(proot.iterdir()):
                s = _read(d / "SKILL.md", "personal", d.name)
                if s:
                    out.append(s)
    return out


def index_lines(skills: list[Skill]) -> str:
    if not skills:
        return "No skills."
    lines = []
    for s in skills:
        tag = " (your personal skill)" if s.scope == "personal" else ""
        lines.append(f"- {s.name}{tag}: {s.description}")
    return "\n".join(lines)


def load(rt: RuntimePaths, ident: Identity, manifest: AccessManifest, name: str) -> str:
    name = (name or "").strip().strip("/")
    if not name or ".." in name or name.count("/") > 1:
        return "Give a skill name from the skill index, e.g. 'whats-due' or 'assignment-review/hw3'."
    top, _, sub = name.partition("/")
    path, scope = rt.course / "skills" / name / "SKILL.md", "course"
    if not path.is_file() and ident.is_student:
        path, scope = rt.user_dir(ident.username) / "skills" / name / "SKILL.md", "personal"
    if not path.is_file():
        return f"No skill named '{name}'. Check the skill index."
    if scope == "course":
        if top == "hints" and sub and ident.is_student:
            return "Hint levels are released one at a time; call get_hint instead of loading them."
        if not _visible_course_rel(f"skills/{name}/SKILL.md", ident, manifest):
            return f"No skill named '{name}'. Check the skill index."
        meta, _ = split_frontmatter(path.read_text())
        aud = str(meta.get("audience", "all"))
        if not sub and aud not in (ident.role, "all"):
            return f"'{name}' is a {aud} skill, not for this user."
    _, body = split_frontmatter(path.read_text())
    out = [f"<skill name=\"{name}\">", body.strip(), "</skill>"]
    subs = []
    for d in sorted(path.parent.iterdir()):
        s = _read(d / "SKILL.md", scope, f"{name}/{d.name}")
        if not s:
            continue
        if scope == "course" and not _visible_course_rel(f"skills/{name}/{d.name}/SKILL.md", ident, manifest):
            continue
        subs.append(f"- {s.name}: {s.description}")
    if subs:
        out.append("Sub-skills (load the one you need with load_skill):\n" + "\n".join(subs))
    return "\n".join(out)
