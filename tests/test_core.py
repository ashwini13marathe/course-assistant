from datetime import datetime, timedelta

import pytest

from harness.access import AccessManifest
from harness.assignments import clean_name, quote_found
from harness.calendar import Calendar
from harness.clock import fmt_dt, parse_dt
from harness.identity import Identity, username_error
from harness.mdutil import append_under_heading, section, split_frontmatter
from harness.paths import PathError, normalize, resolve
from harness.policy import LIST, READ, WRITE, can

P = Identity.professor()
A = Identity.student("alice")
B = Identity.student("bob")


# -- identity & paths -------------------------------------------------------
@pytest.mark.parametrize("name,ok", [("alice", True), ("bob-2", True), ("a", False), ("Alice", False),
                                     ("professor", False), ("main", False), ("../x", False), ("-bob", False)])
def test_usernames(name, ok):
    assert (username_error(name) is None) == ok


@pytest.mark.parametrize("bad", ["/etc/passwd", "memory/course/../../x", "..", "memory/me/../../users/bob"])
def test_paths_reject_traversal(rt, bad):
    with pytest.raises(PathError):
        resolve(rt, A, bad)


def test_normalize():
    assert normalize("./memory//course/./x.md/") == "memory/course/x.md"


def test_roots_by_role(rt):
    assert resolve(rt, A, "memory/me/MEMORY.md").real == rt.user_dir("alice") / "MEMORY.md"
    assert resolve(rt, B, "memory/me/MEMORY.md").real == rt.user_dir("bob") / "MEMORY.md"
    assert resolve(rt, A, "submission/hw1").real == rt.worktree("alice") / "hw1"
    assert resolve(rt, P, "submission/hw1").real == rt.repo / "hw1"
    with pytest.raises(PathError):
        resolve(rt, P, "memory/me/x")
    with pytest.raises(PathError):
        resolve(rt, A, "submissions/bob/hw1")
    vp = resolve(rt, P, "submissions/alice/hw1/linked_list.py")
    assert (vp.branch, vp.rel, vp.real) == ("alice", "hw1/linked_list.py", None)


def test_symlink_escape_blocked(rt):
    link = rt.user_dir("alice") / "notes" / "sneaky"
    link.symlink_to(rt.course / "solutions")
    with pytest.raises(PathError):
        resolve(rt, A, "memory/me/notes/sneaky/hw2/solution.py")


# -- access manifest -----------------------------------------------------------
def test_access_rules(rt):
    m = AccessManifest(rt.course)
    assert m.is_hidden("solutions/hw2/solution.py")
    assert not m.is_hidden("solutions/hw1/solution.py")          # HW1 released in seed
    assert m.is_hidden("skills/hints/hw1/SKILL.md")
    assert not m.is_hidden("skills/hints/SKILL.md")
    assert m.is_hidden("ACCESS.yaml")
    assert not m.is_hidden("COURSE.md")
    assert m.is_hidden("solutions/hw2", is_dir=True)
    assert not m.is_hidden("solutions", is_dir=True)              # has a readable child
    assert not m.is_hidden("skills/hints", is_dir=True)
    assert m.is_hidden("skills/publish-assignment/SKILL.md")      # professor skills
    assert m.is_hidden("skills/publish-assignment", is_dir=True)


def test_access_set_and_exact_beats_pattern(rt):
    m = AccessManifest(rt.course)
    m.set("solutions/hw2", "read", is_dir=True)
    assert not AccessManifest(rt.course).is_hidden("solutions/hw2/solution.py")
    m.set("assignments/hw2/handout.md", "hidden", is_dir=False)
    m2 = AccessManifest(rt.course)
    assert m2.is_hidden("assignments/hw2/handout.md")
    assert not m2.is_hidden("assignments/hw2/guidelines.md")


# -- policy ------------------------------------------------------------------------
POLICY_TABLE = [
    (P, WRITE, "memory/course/lectures/2026-11-24.md", True),
    (P, WRITE, "memory/course/ACCESS.yaml", False),
    (P, READ, "memory/course/solutions/hw2/solution.py", True),
    (A, READ, "memory/course/COURSE.md", True),
    (A, WRITE, "memory/course/COURSE.md", False),
    (A, WRITE, "memory/course/skills/assignment-review/hw2/SKILL.md", False),
    (A, READ, "memory/course/solutions/hw2/solution.py", False),
    (A, READ, "memory/course/solutions/hw1/solution.py", True),
    (A, READ, "memory/course/skills/hints/hw1/SKILL.md", False),
    (A, LIST, "memory/course/solutions/hw2", False),
    (A, READ, "memory/course/ACCESS.yaml", False),
    (A, WRITE, "memory/me/notes/general/x.md", True),
    (A, WRITE, "submission/hw3/bst.py", True),
    (A, WRITE, "uploads/x.txt", False),
    (P, READ, "submissions/alice/hw1/linked_list.py", True),
    (P, WRITE, "submissions/alice/hw1/linked_list.py", False),
]


@pytest.mark.parametrize("ident,action,path,allowed", POLICY_TABLE)
def test_policy_table(rt, ident, action, path, allowed):
    vp = resolve(rt, ident, path)
    assert bool(can(ident, action, vp, AccessManifest(rt.course))) == allowed


# -- markdown -------------------------------------------------------------------------
def test_append_under_heading_existing_section():
    text = "# T\n\n## Summary\n\nS.\n\n## Resources\n\n- [A](a)\n\n## After\n\nX\n"
    out = append_under_heading(text, "Resources", "- [B](b)")
    assert section(out, "Resources") == "- [A](a)\n- [B](b)"
    assert section(out, "After") == "X"


def test_append_under_heading_last_and_missing():
    text = "# T\n\n## Resources\n\n_None yet._\n"
    out = append_under_heading(text, "Resources", "- [B](b)")
    assert out.endswith("_None yet._\n- [B](b)\n")
    out2 = append_under_heading("# T\n", "Updates", "- x")
    assert section(out2, "Updates") == "- x"
    out3 = append_under_heading("# T\n\n## Updates\n", "Updates", "- y")
    assert section(out3, "Updates") == "- y"


def test_frontmatter_roundtrip():
    meta, body = split_frontmatter("---\na: 1\n---\n# B\n")
    assert meta == {"a": 1} and body == "# B\n"


# -- clock & calendar -----------------------------------------------------------------------
def test_dates():
    assert fmt_dt(datetime(2026, 12, 1, 14, 7)) == "Tue Dec 1, 2026, 2:07 PM"
    assert parse_dt("2026-12-03") == datetime(2026, 12, 3, 23, 59)


def test_free_time_matches_the_demo_clash(rt):
    cal = Calendar(rt, "alice")
    blocks = cal.free_time(datetime(2026, 12, 1, 14), datetime(2026, 12, 3, 23, 59), "09:00", "22:00")
    total = sum((e - s for s, e in blocks), timedelta())
    longest = max(e - s for s, e in blocks)
    assert total == timedelta(hours=9, minutes=45)
    assert longest == timedelta(hours=2)


def test_add_event_is_per_student(rt):
    Calendar(rt, "alice").add_event("Study HW3", datetime(2026, 12, 2, 16), datetime(2026, 12, 2, 18))
    span = (datetime(2026, 12, 2), datetime(2026, 12, 3))
    assert any(e.added for e in Calendar(rt, "alice").list_events(*span))
    assert not any(e.added for e in Calendar(rt, "bob").list_events(*span))


# -- naming --------------------------------------------------------------------------------------
@pytest.mark.parametrize("orig,clean", [
    ("CS201 HW3 FINAL (2).PDF", "cs201-hw3.pdf"),
    ("sol_hw3 v2.py", "sol_hw3.py"),
    ("My BST copy.py", "my_bst.py"),
    ("2nd try.py", "f_2nd_try.py"),
    ("notes.final.md", "notes.md"),
])
def test_clean_name(orig, clean):
    assert clean_name(orig) == clean


def test_quote_found():
    msgs = ["Deadline is Thu Dec 3. Tell students it's tough."]
    assert quote_found("Thu Dec 3", msgs)
    assert quote_found("thu  dec 3.", msgs)
    assert not quote_found("Fri Dec 4", msgs)
    assert not quote_found("3", msgs)
