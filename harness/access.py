"""Per-file student access for memory/course/, kept in memory/course/ACCESS.yaml.

    default: read
    rules:
      solutions/**: hidden
      assignments/hw4.md: hidden

The most specific match wins: an exact path beats any pattern, and among patterns
the one with more literal characters wins. Hidden means not listed and not
readable for students, including through the agent.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

ACCESS_FILE = "ACCESS.yaml"
READ = "read"
HIDDEN = "hidden"
LEVELS = (READ, HIDDEN)


def _pattern_regex(pattern: str) -> re.Pattern:
    out = []
    i = 0
    while i < len(pattern):
        if pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile("".join(out))


def _is_pattern(p: str) -> bool:
    return any(c in p for c in "*?")


def _specificity(p: str) -> tuple[int, int]:
    literal = len(p.replace("*", "").replace("?", ""))
    return (0 if _is_pattern(p) else 1, literal)


class AccessManifest:
    def __init__(self, course_dir: Path):
        self.path = Path(course_dir) / ACCESS_FILE
        self.default = READ
        self.rules: dict[str, str] = {}
        self.reload()

    def reload(self) -> None:
        try:
            data = yaml.safe_load(self.path.read_text()) or {}
        except FileNotFoundError:
            data = {}
        self.default = data.get("default", READ)
        self.rules = {str(k).strip("/"): str(v) for k, v in (data.get("rules") or {}).items()}

    def save(self) -> None:
        data = {"default": self.default, "rules": dict(self.rules)}
        header = (
            "# Which course files students can see. Most specific rule wins;\n"
            "# an exact path beats a pattern. Change it from the files panel or\n"
            "# with set_student_access; don't edit by hand during the demo.\n"
        )
        self.path.write_text(header + yaml.safe_dump(data, sort_keys=False))

    def level(self, rel: str) -> str:
        rel = rel.strip("/")
        best: tuple[tuple[int, int], str] | None = None
        for pattern, level in self.rules.items():
            if _pattern_regex(pattern).fullmatch(rel):
                key = _specificity(pattern)
                # On a tie, hidden wins: the safer choice.
                if best is None or key > best[0] or (key == best[0] and level == HIDDEN):
                    best = (key, level)
        return best[1] if best else self.default

    def is_hidden(self, rel: str, is_dir: bool = False) -> bool:
        rel = rel.strip("/")
        if not rel:
            return False
        if not is_dir:
            return self.level(rel) == HIDDEN
        if rel in self.rules:
            return self.rules[rel] == HIDDEN and not self._readable_inside(rel)
        hidden_inside = self.level(rel + "/\0probe") == HIDDEN
        return hidden_inside and not self._readable_inside(rel)

    def _readable_inside(self, rel: str) -> bool:
        prefix = rel + "/"
        return any(p.startswith(prefix) and lvl == READ for p, lvl in self.rules.items())

    def set(self, rel: str, level: str, is_dir: bool) -> str:
        if level not in LEVELS:
            raise ValueError(f"access must be one of {LEVELS}")
        rel = rel.strip("/")
        key = f"{rel}/**" if is_dir else rel
        # A folder rule replaces any narrower rules inside it, so the folder's
        # new setting really applies to everything in it.
        if is_dir:
            for p in list(self.rules):
                if p.startswith(rel + "/") and p != key:
                    del self.rules[p]
        self.rules[key] = level
        self.save()
        return key
