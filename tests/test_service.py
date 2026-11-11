"""The web service with the scripted fake agent: turns, approvals, retry, and
what each role may see through the file viewer."""
import pytest

from conftest import demo_file
from fake_runner import FakeRunner
from webui.service import RequestError, Service, Settings


def settings(role="student", username="alice", **kw):
    return Settings.parse({"role": role, "username": username, "provider": "Claude", "model": "m",
                           "api_key": "k", **kw})


@pytest.fixture
def svc(rt):
    return Service(rt.root, runner_factory=FakeRunner(rt.root, delay=0), needs_key=False)


def run(gen):
    return list(gen)


def test_settings_validation():
    with pytest.raises(RequestError):
        Settings.parse({"role": "student", "username": "Bad Name"})
    with pytest.raises(RequestError):
        Settings.parse({"role": "admin"})
    assert Settings.parse({"role": "professor", "username": "x"}).username == "professor"


def test_chat_streams_text_and_records_transcript(svc):
    s = settings()
    events = run(svc.chat(s, "how does my week look", []))
    kinds = [e["type"] for e in events]
    assert kinds[0] == "status" and "text" in kinds and kinds[-1] == "done"
    st = svc.state(s)
    assert [e["role"] for e in st["transcript"]] == ["user", "assistant"]
    assert "HW3 due 11:59 PM" in st["transcript"][1]["text"]


def test_approval_flow_marks_the_changed_file(svc, rt):
    p = settings("professor", "professor")
    run(svc.chat(p, "add these resources to last tuesday's lecture: https://example.org/rb", []))
    st = svc.state(p)
    assert len(st["pending"]) == 1
    card = st["pending"][0]
    assert card["title"] == "Add to course file" and "+- [Further reading](https://example.org/rb)" in card["preview"]["diff"]
    assert "example.org/rb" not in (rt.course / "lectures/2026-11-24.md").read_text()
    run(svc.decide(p, card["id"], {"type": "approve"}))
    st = svc.state(p)
    assert st["pending"] == []
    assert "example.org/rb" in (rt.course / "lectures/2026-11-24.md").read_text()
    assert st["changed"] == ["memory/course/lectures/2026-11-24.md"]
    assert [e["role"] for e in st["transcript"]] == ["user", "assistant", "card", "assistant"]
    assert st["transcript"][2]["text"].startswith("Approved: add to course file memory/course/lectures/")


def test_reject_and_edit(svc, rt):
    p = settings("professor", "professor")
    run(svc.chat(p, "add resources: https://example.org/a", []))
    item = svc.state(p)["pending"][0]
    run(svc.decide(p, item["id"], {"type": "reject", "message": ""}))
    assert "example.org/a" not in (rt.course / "lectures/2026-11-24.md").read_text()
    run(svc.chat(p, "add resources: https://example.org/b", []))
    item = svc.state(p)["pending"][0]
    edited = {**item["args"], "text": "- [Edited](https://example.org/edited)"}
    run(svc.decide(p, item["id"], {"type": "edit", "edited_action": {"name": item["name"], "args": edited}}))
    text = (rt.course / "lectures/2026-11-24.md").read_text()
    assert "example.org/edited" in text and "example.org/b" not in text
    bad = run(svc.decide(p, "nope", {"type": "approve"}))
    assert bad[0]["type"] == "error"


def test_publish_with_attachments_shows_names_and_deadline(svc):
    p = settings("professor", "professor")
    files = [(n, demo_file(n).read_bytes()) for n in ("CS201 HW3 FINAL (2).md", "bst (1).py", "sol_hw3 v2.py")]
    msg = "This is HW3 with its starter code and solution. Deadline is Thursday. Tough one."
    run(svc.chat(p, msg, files))
    preview = svc.state(p)["pending"][0]["preview"]
    assert preview["kind"] == "publish"
    assert {f["stored_as"] for f in preview["files"]} == {"memory/course/assignments/hw3/handout.md",
                                                          "submission/hw3/bst.py",
                                                          "memory/course/solutions/hw3/solution.py"}
    assert preview["due"] == "Thu Dec 3, 2026, 11:59 PM" and preview["due_quote"] == "Thursday"


def test_error_then_retry(svc):
    s = settings()
    events = run(svc.chat(s, "please fail", []))
    assert events[-1]["type"] == "error" and "529" in events[-1]["message"]
    st = svc.state(s)
    assert st["can_retry"] and st["transcript"][-1]["role"] == "error"
    events = run(svc.retry_last(s))
    assert events[-1]["type"] == "error"  # the script fails again, but the retry ran
    assert [e["role"] for e in svc.state(s)["transcript"]] == ["user", "error"]


def test_file_viewer_respects_access(svc):
    s, p = settings(), settings("professor", "professor")
    with pytest.raises(RequestError):
        svc.file(s, "memory/course/solutions/hw2/solution.py")
    with pytest.raises(RequestError):
        svc.file(s, "submissions/alice/hw1/linked_list.py")
    f = svc.file(p, "memory/course/solutions/hw2/solution.py")
    assert f["hidden"] and f["can_toggle"]
    assert svc.file(s, "memory/course/COURSE.md")["readonly"]
    assert "class SinglyLinkedList" in svc.file(p, "submissions/alice/hw1/linked_list.py")["text"]
    with pytest.raises(RequestError):
        svc.set_access(s, "memory/course/solutions/hw2", "read")
    svc.set_access(p, "memory/course/solutions/hw2/solution.py", "read")
    assert "ArrayStack" in svc.file(s, "memory/course/solutions/hw2/solution.py")["text"]


def test_tree_hides_from_students_and_locks_for_professor(svc):
    def find(nodes, vpath):
        for n in nodes:
            if n["vpath"] == vpath:
                return n
            got = find(n["children"], vpath)
            if got:
                return got
    s_tree = svc.state(settings())["tree"]
    p_tree = svc.state(settings("professor", "professor"))["tree"]
    assert find(s_tree, "memory/course/solutions/hw2") is None
    assert find(s_tree, "memory/course/solutions/hw1")["locked"] is False
    assert find(p_tree, "memory/course/solutions/hw2")["locked"] is True
    assert find(p_tree, "submissions/alice/hw2/stack_queue.py") is not None


def test_new_conversation_and_reset(svc, rt):
    s = settings()
    run(svc.chat(s, "hello", []))
    tid = svc.state(s)["thread_id"]
    svc.new_conversation(s)
    st = svc.state(s)
    assert st["thread_id"] != tid and st["transcript"] == []
    (rt.course / "COURSE.md").write_text("changed")
    svc.reset("before_hw3")
    assert "CS 201" in (rt.course / "COURSE.md").read_text()


def test_suggestions_use_real_weekdays(svc):
    prof = svc.state(settings("professor", "professor"))
    assert any("last Tuesday's lecture" in t for t in prof["suggestions"])
    assert any("Deadline is Thursday" in t for t in prof["suggestions"])
    assert prof["clock_mode"] == "pinned" and prof["warning"] is None


def test_stale_demo_data_warning(tmp_path):
    from datetime import datetime
    from harness.clock import Clock
    from harness.seed import reset
    rt = reset(tmp_path / "rt", "before_hw3", pinned=datetime(2026, 12, 1, 14, 0))
    Clock(rt.state).start(None, seed_day=datetime(2026, 1, 5).date())   # real clock, old data
    svc = Service(rt.root, runner_factory=FakeRunner(rt.root, delay=0), needs_key=False)
    assert "Reset demo" in svc.state(settings())["warning"]
