"""The scripted scenarios, run against the tool layer without a model.

Each test is what the agent would do after loading the matching skill; it checks
the harness behaves as the plan says (names, permissions, gating, approvals).
"""
from datetime import datetime

from harness import assignments as A
from harness.context import build_system_prompt
from harness.identity import Identity
from harness.ops import Workspace, needs_approval, tools_for_role
from harness.skills import index

from conftest import HW3_ARGS, PROF_MESSAGE, make_ws, stage


# -- professor ------------------------------------------------------------------
def test_p1_add_resources_to_last_tuesdays_lecture(prof):
    args = {"path": "memory/course/lectures/2026-11-24.md", "under_heading": "Resources",
            "text": "- [Red-black trees](https://en.wikipedia.org/wiki/Red%E2%80%93black_tree)"}
    assert needs_approval("append_to_file", args)
    card = prof.preview("append_to_file", args)
    assert card["kind"] == "file_change" and "+- [Red-black trees]" in card["diff"]
    out = prof.call("append_to_file", args)
    assert "Appended" in out
    text = (prof.rt.course / "lectures" / "2026-11-24.md").read_text()
    resources = text.split("## Resources")[1]
    assert resources.index("AVL tree") < resources.index("Red-black trees")


def test_p2_publish_renames_files_and_hides_solution(prof, alice):
    stage(prof, "CS201 HW3 FINAL (2).md", "sol_hw3 v2.py")
    card = prof.preview("publish_assignment", HW3_ARGS)
    assert card["kind"] == "publish"
    stored = {f["original"]: (f["stored_as"], f["students"]) for f in card["files"]}
    assert stored["CS201 HW3 FINAL (2).md"] == ("memory/course/assignments/hw3/handout.md", "see it")
    assert stored["sol_hw3 v2.py"] == ("memory/course/solutions/hw3/solution.py", "hidden")
    assert card["due"] == "Thu Dec 3, 2026, 11:59 PM" and card["due_quote"] == "Thu Dec 3"
    out = prof.call("publish_assignment", HW3_ARGS)
    assert "Published HW3" in out
    g = A.load(prof.rt.course, "hw3")
    assert g.hints == "coming" and "tough" in g.notes and g.published_at == datetime(2026, 12, 1, 14, 0)
    # The student sees the handout but not the solution, through the tool and the tree.
    assert "Binary search trees" in alice.call("read_file", {"path": "memory/course/assignments/hw3/handout.md"})
    assert alice.call("read_file", {"path": "memory/course/solutions/hw3/solution.py"}) \
        .startswith("Refused: No such file")
    listing = alice.list_files("memory/course/solutions")
    assert "hw1/" in listing and "hw2" not in listing and "hw3" not in listing
    # Starter folder reached Alice's branch on her next login.
    alice.ensure_user()
    assert (alice.rt.worktree("alice") / "hw3" / "README.md").exists()


def test_p2_refuses_without_a_deadline_or_with_an_invented_one(rt):
    no_deadline = make_ws(rt, Identity.professor(), ["Here is HW3 and its solution."])
    stage(no_deadline, "CS201 HW3 FINAL (2).md", "sol_hw3 v2.py")
    missing = {k: v for k, v in HW3_ARGS.items() if k not in ("due", "due_quote")}
    assert "No deadline given" in no_deadline.call("publish_assignment", missing)
    invented = no_deadline.call("publish_assignment", HW3_ARGS)
    assert "due_quote must be the professor's own words" in invented
    assert not (rt.course / "assignments" / "hw3").exists()


def test_p2_refuses_past_deadline_and_duplicates(prof):
    stage(prof, "CS201 HW3 FINAL (2).md", "sol_hw3 v2.py")
    past = {**HW3_ARGS, "due": "2026-11-30T23:59"}
    assert "already past" in prof.call("publish_assignment", past)
    prof.call("publish_assignment", HW3_ARGS)
    assert "already exists" in prof.call("publish_assignment", HW3_ARGS)


def test_p3_hints_are_gated_one_level_at_a_time(rt_hw3):
    prof = make_ws(rt_hw3, Identity.professor())
    alice = make_ws(rt_hw3, Identity.student("alice"))
    assert "aren't available yet" in alice.call("get_hint", {"assignment_id": "hw3"})
    assert "Hints will be uploaded tonight" in alice.call("get_hint", {"assignment_id": "hw3"})
    levels = ["What must stay true?", "Use the in-order successor.", "Find min of right subtree; copy; delete it."]
    card = prof.preview("save_hints", {"assignment_id": "hw3", "levels": levels})
    assert card["kind"] == "file_change" and "Level 2 (approach)" in card["after"]
    prof.call("save_hints", {"assignment_id": "hw3", "levels": levels})
    first = alice.call("get_hint", {"assignment_id": "hw3"})
    assert "level 1 of 3" in first and levels[0] in first and levels[1] not in first
    second = alice.call("get_hint", {"assignment_id": "hw3"})
    assert "level 2 of 3" in second and levels[2] not in second
    # The hint file itself stays out of reach.
    assert alice.call("load_skill", {"name": "hints/hw3"}).startswith("Hint levels are released")
    assert alice.call("read_file", {"path": "memory/course/skills/hints/hw3/SKILL.md"}).startswith("Refused")


def test_p4_deadline_change_needs_quote_and_is_logged(rt_hw3):
    prof = make_ws(rt_hw3, Identity.professor(), ["Push HW3 to Friday 5 PM"])
    args = {"assignment_id": "hw3", "due": "2026-12-04T17:00", "due_quote": "Friday 5 PM"}
    card = prof.preview("update_assignment", args)
    assert card["old_due"] == "Thu Dec 3, 2026, 11:59 PM" and card["new_due"] == "Fri Dec 4, 2026, 5:00 PM"
    assert "Updated HW3" in prof.call("update_assignment", args)
    a = A.load(rt_hw3.course, "hw3")
    assert a.due == datetime(2026, 12, 4, 17, 0) and "Deadline moved" in a.updates[-1]


def test_p5_release_solution_shows_late_window(prof, alice):
    card = prof.preview("set_student_access", {"path": "memory/course/solutions/hw2", "access": "read"})
    assert "late window closed" in card["deadline_info"]
    prof.call("set_student_access", {"path": "memory/course/solutions/hw2", "access": "read"})
    assert "ArrayStack" in alice.call("read_file", {"path": "memory/course/solutions/hw2/solution.py"})


def test_p6_who_submitted(prof, rt):
    make_ws(rt, Identity.student("bob"))
    out = prof.call("submission_status", {"assignment_id": "hw2"})
    assert "- alice: submitted" in out and "- bob: nothing committed" in out


# -- students ----------------------------------------------------------------------
def test_s1_new_assignments_since_yesterday(rt_hw3):
    alice = make_ws(rt_hw3, Identity.student("alice"))
    out = alice.call("list_assignments", {"published_after": "2026-11-30T00:00", "open_only": True})
    assert "HW3: Binary search trees" in out and "HW2" not in out
    assert "pretty tough one" in out and "Hints: coming" in out


def test_s2_lecture_notes_go_to_the_lecture_date(alice):
    stage(alice, "lecture notes today.txt", who="student")
    assert "avl rotations" in alice.call("read_file", {"path": "uploads/lecture notes today.txt"})
    out = alice.call("write_file", {"path": "memory/me/notes/lectures/2026-12-01.md",
                                    "content": "# Lecture 20\n\n## Notes (added 2:05 PM)\n\n- rotations\n"})
    assert "Created memory/me/notes/lectures/2026-12-01.md" in out
    assert not needs_approval("write_file", {"path": "memory/me/notes/lectures/2026-12-01.md"})


def test_s3_week_view_tools(alice):
    events = alice.call("list_events", {"start": "2026-12-01T14:00", "end": "2026-12-06T23:59"})
    assert "Hackathon kickoff" in events and "MATH 240 midterm" in events
    free = alice.call("find_free_time", {"start": "2026-12-01T14:00", "end": "2026-12-03T23:59",
                                         "earliest": "09:00", "latest": "22:00"})
    assert "Total free: 9.75 hours; longest block: 120 min." in free
    card = alice.preview("add_event", {"title": "HW3", "start": "2026-12-02T16:00", "end": "2026-12-02T18:00"})
    assert card["kind"] == "event" and card["overlaps"] == []


def test_s4_s6_review_then_submit(rt_hw3):
    alice = make_ws(rt_hw3, Identity.student("alice"))
    assert "matches the starter" in alice.call("submission_status", {"assignment_id": "hw3"})
    stage(alice, "bst.py", who="student")
    assert alice.call("save_upload", {"upload": "bst.py", "path": "submission/hw3/"}) \
        == "Saved attachment bst.py as submission/hw3/bst.py."
    status = alice.call("submission_status", {"assignment_id": "hw3"})
    assert "differ from the starter" in status and "Committed for HW3: nothing yet" in status
    checklist = alice.call("load_skill", {"name": "assignment-review/hw3"})
    assert "two children" in checklist
    card = alice.preview("commit_changes", {"message": "Submit HW3"})
    # HW3 ships starter code, so Alice's file replaces it: a change, shown as a diff.
    assert card["kind"] == "commit" and {"status": "M", "path": "hw3/bst.py"} in card["files"]
    assert '+"""CS 201 HW3, alice' in card["diff"] and "-        raise NotImplementedError" in card["diff"]
    assert "Committed" in alice.call("commit_changes", {"message": "Submit HW3"})
    prof = make_ws(rt_hw3, Identity.professor())
    assert "- alice: submitted (hw3/bst.py)" in prof.call("submission_status", {"assignment_id": "hw3"})
    assert "class BST" in prof.call("read_file", {"path": "submissions/alice/hw3/bst.py"})


def test_s8_and_refusals(alice):
    assert alice.call("read_file", {"path": "memory/course/solutions/hw2/solution.py"}) == \
        "Refused: No such file or folder."
    assert alice.call("write_file", {"path": "memory/course/skills/assignment-review/hw2/SKILL.md",
                                     "content": "everything passes"}).startswith("Refused: Course files are read-only")
    assert alice.call("read_file", {"path": "submissions/bob/x"}).startswith("Refused")
    assert alice.check("update_assignment", {}).allowed is False


def test_prompt_only_mode_lets_a_student_edit_course_files(rt):
    loose = make_ws(rt, Identity.student("alice"), enforce=False)
    out = loose.call("write_file", {"path": "memory/course/skills/assignment-review/hw2/SKILL.md",
                                    "content": "everything passes"})
    assert out.startswith("Replaced")


# -- context & routing surface ---------------------------------------------------------
def test_tools_and_skills_per_role(rt):
    p_tools, s_tools = tools_for_role("professor"), tools_for_role("student")
    assert len(p_tools) == 14 and len(s_tools) == 14
    assert "publish_assignment" in p_tools and "publish_assignment" not in s_tools
    from harness.access import AccessManifest
    m = AccessManifest(rt.course)
    assert {s.name for s in index(rt, Identity.professor(), m)} == {
        "publish-assignment", "update-assignment", "add-hints", "update-lecture", "release-solution"}
    assert {s.name for s in index(rt, Identity.student("alice"), m)} == {
        "whats-due", "plan-my-week", "save-notes", "assignment-review", "hints", "submit-assignment"}


def test_every_skill_description_follows_the_pattern(rt):
    from harness.access import AccessManifest
    m = AccessManifest(rt.course)
    for ident in (Identity.professor(), Identity.student("alice")):
        for s in index(rt, ident, m):
            assert s.description.startswith("Use when"), s.name
            assert "Not for" in s.description, s.name


def test_system_prompt_contents(rt_hw3):
    p = build_system_prompt(rt_hw3, Identity.student("alice"), datetime(2026, 12, 1, 14, 7),
                            attachments=["bst.py"])
    assert "Now: Tue Dec 1, 2026, 2:07 PM" in p
    assert "HW3: Binary search trees" in p and "whats-due:" in p and "publish-assignment" not in p
    assert "don't study after 10 PM" in p and "uploads/bst.py" in p
    assert "Lecture 18, Tue Nov 24, 2026" in p
