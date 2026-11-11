import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from harness.clock import DEMO_START, Clock  # noqa: E402
from harness.identity import Identity  # noqa: E402
from harness.ops import Workspace  # noqa: E402
from harness.seed import reset  # noqa: E402

DEMO_UPLOADS = ROOT / "demo_uploads"
PROF_MESSAGE = ("This is HW3 and its solution. Deadline is Thu Dec 3. Tell students it's a pretty "
                "tough one so keep time for it. Will upload the hints later tonight.")


# Tests pin the demo day to Tue Dec 1, 2026, 2:00 PM so every date is predictable.
@pytest.fixture
def rt(tmp_path):
    return reset(tmp_path / "runtime", "before_hw3", pinned=DEMO_START)


@pytest.fixture
def rt_hw3(tmp_path):
    return reset(tmp_path / "runtime", "after_hw3", pinned=DEMO_START)


def make_ws(rt, ident, texts=None, enforce=True, now=DEMO_START):
    ws = Workspace(rt, ident, enforce=enforce, clock=Clock(rt.state, frozen=now), user_texts=texts or [])
    ws.ensure_user()
    return ws


@pytest.fixture
def prof(rt):
    return make_ws(rt, Identity.professor(), [PROF_MESSAGE])


@pytest.fixture
def alice(rt):
    return make_ws(rt, Identity.student("alice"))


def demo_file(name, who="professor"):
    return next((DEMO_UPLOADS / who).rglob(name))


def stage(ws, *names, who="professor"):
    for name in names:
        ws.stage_upload(name, demo_file(name, who).read_bytes())


HW3_ARGS = {
    "assignment_id": "hw3",
    "title": "Binary search trees",
    "due": "2026-12-03T23:59",
    "due_quote": "Thu Dec 3",
    "overview": "Implement a BST.",
    "professor_notes": "This is a pretty tough one, so keep time to work on it.",
    "hints_status": "coming",
    "review_checklist": "- [ ] delete handles two children",
    "files": [{"upload": "CS201 HW3 FINAL (2).md", "kind": "handout"},
              {"upload": "sol_hw3 v2.py", "kind": "solution"}],
}
