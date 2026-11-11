"""Git for submissions. `main` is the professor's; each student has a branch,
each user a worktree, so no tool ever switches branches. Local commits only.
"""
from __future__ import annotations

import contextlib
import os
import subprocess
from datetime import datetime
from pathlib import Path

from .runtime import RuntimePaths

try:  # file locking: macOS and Linux
    import fcntl
except ImportError:  # pragma: no cover - Windows
    fcntl = None

BOT_NAME = "Course Assistant"
BOT_EMAIL = "assistant@cs201.local"


class GitError(Exception):
    pass


def author_for(username: str) -> tuple[str, str]:
    if username == "professor":
        return ("Professor", "professor@cs201.local")
    return (username, f"{username}@cs201.local")


class Git:
    def __init__(self, rt: RuntimePaths):
        self.rt = rt

    # -- plumbing ---------------------------------------------------------
    @contextlib.contextmanager
    def lock(self):
        self.rt.state.mkdir(parents=True, exist_ok=True)
        with open(self.rt.state / "git.lock", "w") as fh:
            if fcntl:
                fcntl.flock(fh, fcntl.LOCK_EX)
            try:
                yield
            finally:
                if fcntl:
                    fcntl.flock(fh, fcntl.LOCK_UN)

    def run(self, *args: str, cwd: Path | None = None, env: dict | None = None,
            check: bool = True) -> str:
        full_env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "LC_ALL": "C"}
        # Keep the user's global git config (hooks, signing) out of demo commits.
        full_env["GIT_CONFIG_GLOBAL"] = os.devnull
        full_env["GIT_CONFIG_NOSYSTEM"] = "1"
        if env:
            full_env.update(env)
        proc = subprocess.run(
            ["git", *args], cwd=str(cwd or self.rt.repo), env=full_env,
            capture_output=True, text=True,
        )
        if check and proc.returncode != 0:
            raise GitError((proc.stderr or proc.stdout).strip() or f"git {' '.join(args)} failed")
        return proc.stdout

    @staticmethod
    def _who(name: str, email: str, when: datetime | None) -> dict:
        env = {
            "GIT_AUTHOR_NAME": name, "GIT_AUTHOR_EMAIL": email,
            "GIT_COMMITTER_NAME": name, "GIT_COMMITTER_EMAIL": email,
        }
        if when is not None:
            stamp = when.strftime("%Y-%m-%dT%H:%M:%S")
            env["GIT_AUTHOR_DATE"] = stamp
            env["GIT_COMMITTER_DATE"] = stamp
        return env

    # -- setup -------------------------------------------------------------
    def init_main(self) -> None:
        self.rt.repo.mkdir(parents=True, exist_ok=True)
        self.run("init", "-q", "-b", "main", cwd=self.rt.repo)

    def ensure_student_worktree(self, username: str) -> Path:
        path = self.rt.worktree(username)
        if (path / ".git").exists():
            return path
        with self.lock():
            branches = self.run("branch", "--list", username).strip()
            if branches:
                self.run("worktree", "add", "-q", str(path), username)
            else:
                self.run("worktree", "add", "-q", "-b", username, str(path), "main")
        return path

    # -- commits -----------------------------------------------------------
    def commit_all(self, worktree: Path, message: str, username: str,
                   when: datetime | None = None) -> str | None:
        """Stage everything in the worktree and commit. None if nothing changed."""
        name, email = author_for(username)
        with self.lock():
            self.run("add", "-A", cwd=worktree)
            staged = self.run("diff", "--cached", "--name-only", cwd=worktree).strip()
            if not staged:
                return None
            self.run("commit", "-q", "-m", message, cwd=worktree, env=self._who(name, email, when))
            return self.run("rev-parse", "--short", "HEAD", cwd=worktree).strip()

    def preview_commit(self, worktree: Path, max_bytes: int = 20000) -> dict:
        """What commit_all would commit, without staging anything."""
        status = self.run("status", "--porcelain", "-uall", cwd=worktree)
        files = []
        for line in status.splitlines():
            if not line.strip():
                continue
            code, path = line[:2], line[3:]
            files.append({"status": code.strip() or "M", "path": path})
        diff = self.run("diff", "HEAD", cwd=worktree, check=False)
        new_files = {}
        for f in files:
            if f["status"] == "??":
                p = worktree / f["path"]
                try:
                    new_files[f["path"]] = p.read_text()[:max_bytes]
                except (UnicodeDecodeError, OSError):
                    new_files[f["path"]] = "[binary file]"
        return {"files": files, "diff": diff[:max_bytes], "new_files": new_files}

    def head(self, worktree: Path) -> str:
        return self.run("rev-parse", "--short", "HEAD", cwd=worktree).strip()

    # -- students ---------------------------------------------------------
    def sync_main_into(self, username: str, when: datetime | None = None) -> str | None:
        """Merge new starter files from main into a student's branch.

        Returns a message if the merge couldn't happen, None on success or no-op.
        """
        wt = self.rt.worktree(username)
        if not (wt / ".git").exists():
            return None
        with self.lock():
            up_to_date = subprocess.run(
                ["git", "merge-base", "--is-ancestor", "main", "HEAD"], cwd=str(wt),
                capture_output=True,
            ).returncode == 0
            if up_to_date:
                return None
            try:
                self.run("merge", "-q", "--no-edit", "-m", "Sync new course files from main", "main",
                         cwd=wt, env=self._who(BOT_NAME, BOT_EMAIL, when))
            except GitError as err:
                self.run("merge", "--abort", cwd=wt, check=False)
                return f"Couldn't bring in new course files from main: {err}"
        return None

    def branches(self) -> list[dict]:
        out = self.run("for-each-ref", "refs/heads",
                       "--format=%(refname:short)\t%(committerdate:iso-strict)\t%(subject)")
        rows = []
        for line in out.splitlines():
            name, date, subject = (line.split("\t") + ["", ""])[:3]
            rows.append({"branch": name, "date": date, "subject": subject})
        return rows

    def student_branches(self) -> list[str]:
        return [b["branch"] for b in self.branches() if b["branch"] != "main"]

    def show(self, branch: str, path: str) -> str:
        try:
            return self.run("show", f"{branch}:{path}")
        except GitError as err:
            raise FileNotFoundError(path) from err

    def ls_tree(self, branch: str, path: str = "") -> list[tuple[str, str]]:
        """[(name, 'dir'|'file')] at a path in a branch's last commit."""
        spec = f"{branch}:{path}" if path else f"{branch}:"
        try:
            out = self.run("ls-tree", spec)
        except GitError as err:
            raise FileNotFoundError(path) from err
        rows = []
        for line in out.splitlines():
            meta, name = line.split("\t", 1)
            kind = "dir" if meta.split()[1] == "tree" else "file"
            rows.append((name, kind))
        return rows

    def ls_tree_recursive(self, branch: str) -> list[tuple[str, str]]:
        """[(path, blob sha)] of every file in a branch's last commit."""
        out = self.run("ls-tree", "-r", branch, check=False)
        rows = []
        for line in out.splitlines():
            meta, path = line.split("\t", 1)
            rows.append((path, meta.split()[2]))
        return rows

    def committed_changes(self, branch: str, prefix: str) -> list[str]:
        """Files under prefix the branch has committed since it left main."""
        out = self.run("diff", "--name-only", f"main...{branch}", "--", prefix, check=False)
        return [l for l in out.splitlines() if l.strip()]

    def last_commit_touching(self, branch: str, prefix: str) -> dict | None:
        out = self.run("log", "-1", "--format=%h\t%cd\t%s", "--date=format:%Y-%m-%d %H:%M",
                       branch, "--", prefix, check=False).strip()
        if not out:
            return None
        sha, date, subject = (out.split("\t") + ["", ""])[:3]
        return {"sha": sha, "date": date, "subject": subject}

    def worktree_differs_from_main(self, worktree: Path, prefix: str) -> bool:
        changed = subprocess.run(["git", "diff", "--quiet", "main", "--", prefix],
                                 cwd=str(worktree), capture_output=True).returncode != 0
        untracked = self.run("ls-files", "--others", "--exclude-standard", "--", prefix,
                             cwd=worktree).strip()
        return changed or bool(untracked)
