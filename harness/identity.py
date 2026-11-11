"""Who is using the app. Set by the sidebar, never by anything typed in chat."""
from __future__ import annotations

import re
from dataclasses import dataclass

PROFESSOR = "professor"
STUDENT = "student"
ROLES = (PROFESSOR, STUDENT)

USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,19}$")
RESERVED = {"professor", "main", "me", "course", "admin", "root", "head"}


def username_error(name: str) -> str | None:
    """Return why a student username is invalid, or None if it's fine."""
    if not USERNAME_RE.match(name or ""):
        return "Use 2 to 20 lowercase letters, digits or hyphens, starting with a letter or digit."
    if name in RESERVED:
        return f"'{name}' is reserved."
    return None


@dataclass(frozen=True)
class Identity:
    role: str
    username: str

    def __post_init__(self):
        if self.role not in ROLES:
            raise ValueError(f"Unknown role {self.role!r}")
        if self.role == STUDENT:
            err = username_error(self.username)
            if err:
                raise ValueError(err)

    @classmethod
    def professor(cls) -> "Identity":
        return cls(PROFESSOR, PROFESSOR)

    @classmethod
    def student(cls, username: str) -> "Identity":
        return cls(STUDENT, username)

    @property
    def is_professor(self) -> bool:
        return self.role == PROFESSOR

    @property
    def is_student(self) -> bool:
        return self.role == STUDENT

    @property
    def branch(self) -> str:
        return "main" if self.is_professor else self.username

    @property
    def display(self) -> str:
        return "Professor" if self.is_professor else f"Student: {self.username}"
