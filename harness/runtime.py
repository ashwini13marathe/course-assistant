"""Where live demo data sits on disk. Rebuilt from seed/ by scripts/reset.py."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def default_runtime_root() -> Path:
    return Path(os.environ.get("COURSE_RUNTIME", PROJECT_ROOT / "runtime")).resolve()


@dataclass(frozen=True)
class RuntimePaths:
    root: Path

    @property
    def memory(self) -> Path:
        return self.root / "memory"

    @property
    def course(self) -> Path:
        return self.memory / "course"

    @property
    def users(self) -> Path:
        return self.memory / "users"

    @property
    def worktrees(self) -> Path:
        return self.root / "worktrees"

    @property
    def repo(self) -> Path:
        """The professor's checkout of `main`; it holds the .git directory."""
        return self.worktrees / "main"

    @property
    def uploads(self) -> Path:
        return self.root / "uploads"

    @property
    def state(self) -> Path:
        return self.root / "state"

    @property
    def calendar(self) -> Path:
        return self.root / "calendar.json"

    def user_dir(self, username: str) -> Path:
        return self.users / username

    def worktree(self, branch: str) -> Path:
        return self.worktrees / branch

    def upload_dir(self, username: str) -> Path:
        return self.uploads / username

    def exists(self) -> bool:
        return self.course.is_dir() and (self.repo / ".git").exists()
