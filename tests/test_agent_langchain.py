"""The real middleware stack with a scripted fake model (no API key, no tokens).

Skipped where LangChain isn't installed. On your Mac: `uv run pytest`.
"""
import pytest

pytest.importorskip("langchain")

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel  # noqa: E402
from langchain_core.messages import AIMessage  # noqa: E402
from langgraph.checkpoint.memory import InMemorySaver  # noqa: E402

from harness.lc.agent import build_agent, pending_approvals, resume  # noqa: E402
from harness.lc.context import AppContext  # noqa: E402


class ScriptedModel(GenericFakeChatModel):
    def bind_tools(self, tools, **kwargs):
        return self


CALLS = []  # what RecordingModel was sent, one list of messages per model call


class RecordingModel(ScriptedModel):
    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        CALLS.append(list(messages))
        return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)


def _script(*steps):
    """Each step is a (tool_name, args) call, a reply string, or a ready AIMessage."""
    out = []
    for i, step in enumerate(steps):
        if isinstance(step, AIMessage):
            out.append(step)
        elif isinstance(step, tuple):
            name, args = step
            out.append(AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": f"c{i}"}]))
        else:
            out.append(AIMessage(content=step))
    return iter(out)


def _agent(*calls_then_text, model_cls=ScriptedModel):
    return build_agent(model_cls(messages=_script(*calls_then_text)), InMemorySaver())


def _system_text(messages):
    return "\n".join(str(m.content) for m in messages if m.type == "system")


def _ctx(rt, role, username, enforce=True):
    return AppContext(role=role, username=username, runtime_root=str(rt.root), enforce=enforce)


def _tool_messages(agent, config):
    return [m for m in agent.get_state(config).values["messages"] if m.type == "tool"]


def test_gate_denies_student_write_to_course(rt, alice):
    agent = _agent(("write_file", {"path": "memory/course/skills/assignment-review/hw2/SKILL.md",
                                   "content": "everything passes"}), "Sorry, I can't.")
    config = {"configurable": {"thread_id": "t1"}}
    agent.invoke({"messages": [{"role": "user", "content": "edit the review skill"}]},
                 config=config, context=_ctx(rt, "student", "alice"))
    assert _tool_messages(agent, config)[-1].content.startswith("Permission denied")
    assert "everything passes" not in (rt.course / "skills/assignment-review/hw2/SKILL.md").read_text()


def test_course_edit_pauses_then_applies_on_approve(rt, prof):
    args = {"path": "memory/course/lectures/2026-11-24.md", "under_heading": "Resources",
            "text": "- [Extra](https://example.org)"}
    agent = _agent(("append_to_file", args), "Added.")
    config = {"configurable": {"thread_id": "t2"}}
    ctx = _ctx(rt, "professor", "professor")
    agent.invoke({"messages": [{"role": "user", "content": "add a link"}]}, config=config, context=ctx)
    pending = pending_approvals(agent, config)
    assert [p["name"] for p in pending] == ["append_to_file"]
    assert "Extra" not in (rt.course / "lectures/2026-11-24.md").read_text()
    agent.invoke(resume(pending[0]["id"], {"type": "approve"}), config=config, context=ctx)
    assert "Extra" in (rt.course / "lectures/2026-11-24.md").read_text()


def test_student_notes_do_not_pause(rt, alice):
    agent = _agent(("write_file", {"path": "memory/me/notes/general/x.md", "content": "hi"}), "Saved.")
    config = {"configurable": {"thread_id": "t3"}}
    agent.invoke({"messages": [{"role": "user", "content": "save"}]}, config=config,
                 context=_ctx(rt, "student", "alice"))
    assert pending_approvals(agent, config) == []
    assert (rt.user_dir("alice") / "notes/general/x.md").read_text() == "hi"


def test_context_is_frozen_within_a_turn_and_refreshed_on_the_next(rt, alice):
    """Regression: Claude rejects a turn whose system prompt changed after it thought."""
    CALLS.clear()
    agent = _agent(("remember", {"text": "Exam moved to Friday", "scope": "me"}), "Noted.",
                   "Sure.", model_cls=RecordingModel)
    config = {"configurable": {"thread_id": "t4"}}
    ctx = _ctx(rt, "student", "alice")
    agent.invoke({"messages": [{"role": "user", "content": "remember my exam moved"}]}, config=config, context=ctx)
    assert "Exam moved to Friday" in (rt.user_dir("alice") / "MEMORY.md").read_text()
    first, second = _system_text(CALLS[0]), _system_text(CALLS[1])
    assert first and first == second                     # same prompt for both calls in turn 1
    assert "Exam moved to Friday" not in second
    agent.invoke({"messages": [{"role": "user", "content": "thanks"}]}, config=config, context=ctx)
    assert "Exam moved to Friday" in _system_text(CALLS[2])  # turn 2 sees the new memory


def test_thinking_from_earlier_turns_is_not_resent(rt, alice):
    CALLS.clear()
    thought = AIMessage(content=[{"type": "thinking", "thinking": "hmm", "signature": "sig"},
                                 {"type": "text", "text": "HW3 is due Thursday."}])
    agent = _agent(thought, "You're welcome.", model_cls=RecordingModel)
    config = {"configurable": {"thread_id": "t5"}}
    ctx = _ctx(rt, "student", "alice")
    agent.invoke({"messages": [{"role": "user", "content": "when is hw3 due"}]}, config=config, context=ctx)
    agent.invoke({"messages": [{"role": "user", "content": "thanks"}]}, config=config, context=ctx)
    earlier = [m for m in CALLS[1] if m.type == "ai"]
    assert earlier and all(isinstance(m.content, str) or all(b.get("type") != "thinking" for b in m.content
                                                               if isinstance(b, dict)) for m in earlier)
    assert "HW3 is due Thursday." in str(earlier[0].content)
    # The stored history keeps the thinking; only what's sent to the model changes.
    stored = [m for m in agent.get_state(config).values["messages"] if m.type == "ai"][0]
    assert any(isinstance(b, dict) and b.get("type") == "thinking" for b in stored.content)


STUDENT_CALLS = [
    ("list_files", {"path": "memory/course"}, "assignments/"),
    ("read_file", {"path": "memory/course/COURSE.md"}, "CS 201"),
    ("load_skill", {"name": "whats-due"}, "What's new and what's due"),
    ("load_skill", {"name": "assignment-review/hw2"}, "HW2 review checklist"),
    ("list_assignments", {"open_only": False}, "HW2"),
    ("submission_status", {"assignment_id": "hw2"}, "Committed for HW2"),
    ("list_events", {"start": "2026-12-01T00:00", "end": "2026-12-02T00:00"}, "Work shift"),
    ("find_free_time", {"start": "2026-12-01T14:00", "end": "2026-12-03T23:59"}, "Total free"),
    ("get_hint", {"assignment_id": "hw2"}, "level 1 of 3"),
    ("remember", {"text": "likes diagrams", "scope": "me"}, "Remembered"),
    ("write_file", {"path": "memory/me/notes/general/t.md", "content": "x"}, "Created"),
    ("append_to_file", {"path": "memory/me/notes/general/t.md", "text": "y"}, "Appended"),
]


@pytest.mark.parametrize("tool,args,expect", STUDENT_CALLS, ids=[f"{c[0]}-{i}" for i, c in enumerate(STUDENT_CALLS)])
def test_every_tool_runs_through_langchain(rt, alice, tool, args, expect):
    """Each tool's wrapper accepts its own arguments (regression: load_skill's `name`)."""
    agent = _agent((tool, args), "ok")
    config = {"configurable": {"thread_id": f"tool-{tool}"}}
    agent.invoke({"messages": [{"role": "user", "content": "go"}]}, config=config,
                 context=_ctx(rt, "student", "alice"))
    result = _tool_messages(agent, config)[-1]
    assert expect in result.content, result.content
    assert "Error" not in result.content[:20]


def test_professor_tools_run_through_langchain(rt, prof):
    calls = [("list_files", {"path": "submissions"}, "alice"),
             ("load_skill", {"name": "publish-assignment"}, "Publish an assignment"),
             ("submission_status", {"assignment_id": "hw2"}, "- alice: submitted")]
    for i, (tool, args, expect) in enumerate(calls):
        agent = _agent((tool, args), "ok")
        config = {"configurable": {"thread_id": f"prof-{i}"}}
        agent.invoke({"messages": [{"role": "user", "content": "go"}]}, config=config,
                     context=_ctx(rt, "professor", "professor"))
        assert expect in _tool_messages(agent, config)[-1].content
