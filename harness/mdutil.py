"""Small Markdown helpers: frontmatter and heading sections."""
from __future__ import annotations

import re

import yaml

_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")


def split_frontmatter(text: str) -> tuple[dict, str]:
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        if end != -1:
            try:
                meta = yaml.safe_load(text[4:end]) or {}
            except yaml.YAMLError:
                meta = {}  # a malformed header must never break the prompt
            rest = text[end + 4:]
            return (meta if isinstance(meta, dict) else {}), rest.lstrip("\n")
    return {}, text


def join_frontmatter(meta: dict, body: str) -> str:
    head = yaml.safe_dump(meta, sort_keys=False, allow_unicode=True).strip()
    return f"---\n{head}\n---\n{body.lstrip(chr(10))}"


def _headings(lines: list[str]) -> list[tuple[int, int, str]]:
    """[(line_index, level, title)] skipping fenced code blocks."""
    out, fenced = [], False
    for i, line in enumerate(lines):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if fenced:
            continue
        m = _HEADING.match(line)
        if m:
            out.append((i, len(m.group(1)), m.group(2).strip()))
    return out


def section(text: str, heading: str) -> str | None:
    """Text under a heading (any level), up to the next heading of the same or higher level."""
    lines = text.splitlines()
    hs = _headings(lines)
    for n, (i, level, title) in enumerate(hs):
        if title.lower() == heading.strip().lower():
            end = len(lines)
            for j, lvl, _ in hs[n + 1:]:
                if lvl <= level:
                    end = j
                    break
            return "\n".join(lines[i + 1:end]).strip()
    return None


def append_under_heading(text: str, heading: str | None, addition: str) -> str:
    """Append `addition` at the end of a heading's section, creating it if missing."""
    addition = addition.strip("\n")
    if not heading:
        base = text.rstrip("\n")
        return f"{base}\n\n{addition}\n" if base else f"{addition}\n"
    lines = text.splitlines()
    hs = _headings(lines)
    for n, (i, level, title) in enumerate(hs):
        if title.lower() == heading.strip().lstrip("#").strip().lower():
            end = len(lines)
            for j, lvl, _ in hs[n + 1:]:
                if lvl <= level:
                    end = j
                    break
            # Insert after the section's last non-blank line.
            insert_at = end
            while insert_at > i + 1 and not lines[insert_at - 1].strip():
                insert_at -= 1
            block = addition.splitlines()
            if insert_at == i + 1:  # empty section
                block = [""] + block
            new = lines[:insert_at] + block + ([""] if end < len(lines) else []) + lines[end:] \
                if end < len(lines) else lines[:insert_at] + block
            # Avoid doubled blank lines before the next heading.
            out = "\n".join(new)
            out = re.sub(r"\n{3,}", "\n\n", out)
            return out.rstrip("\n") + "\n"
    title = heading.strip().lstrip("#").strip()
    base = text.rstrip("\n")
    return f"{base}\n\n## {title}\n\n{addition}\n"
