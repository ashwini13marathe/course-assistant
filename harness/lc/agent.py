"""Build the agent and run one turn of it (streaming, pausing, resuming)."""
from __future__ import annotations

from typing import Iterator

from langchain.agents import create_agent
from langchain_core.messages import AIMessageChunk
from langgraph.types import Command

from .context import AppContext
from .middleware import build_middleware
from .tools import build_tools

# Shown in the chat while a tool runs; the full detail lives in Langfuse.
TOOL_STATUS = {
    "list_files": "Looking through files",
    "read_file": "Reading a file",
    "write_file": "Writing a file",
    "append_to_file": "Updating a file",
    "save_upload": "Filing an attachment",
    "remember": "Saving to memory",
    "load_skill": "Loading a skill",
    "list_assignments": "Checking assignments",
    "publish_assignment": "Preparing the assignment",
    "update_assignment": "Preparing the change",
    "save_hints": "Preparing the hints",
    "set_student_access": "Preparing the access change",
    "get_hint": "Getting the next hint",
    "commit_changes": "Preparing the commit",
    "submission_status": "Checking submissions",
    "list_events": "Reading the calendar",
    "find_free_time": "Finding free time",
    "add_event": "Preparing the calendar event",
}


def build_agent(model, checkpointer):
    return create_agent(model=model, tools=build_tools(), middleware=build_middleware(),
                        context_schema=AppContext, checkpointer=checkpointer)


def _chunk_text(chunk) -> str:
    content = chunk.content
    if isinstance(content, str):
        return content
    out = []
    for block in content or []:
        if isinstance(block, dict) and block.get("type") == "text":
            out.append(block.get("text", ""))
    return "".join(out)


def stream_events(agent, payload, config: dict, context: AppContext) -> Iterator[dict]:
    """Yield {"type": "text", "text": ...} as the model writes and
    {"type": "status", "text": ...} when it starts a tool call.

    `payload` is the new user message ({"messages": [...]}) or a
    Command(resume=...) answering an approval card.
    """
    current, wrote = None, False
    for chunk, meta in agent.stream(payload, config=config, context=context, stream_mode="messages"):
        if meta.get("langgraph_node") != "model" or not isinstance(chunk, AIMessageChunk):
            continue
        for tc in getattr(chunk, "tool_call_chunks", None) or []:
            if tc.get("name"):
                yield {"type": "status", "text": TOOL_STATUS.get(tc["name"], f"Running {tc['name']}")}
        text = _chunk_text(chunk)
        if not text:
            continue
        if chunk.id != current:  # a new model call in the same turn: start a new paragraph
            if wrote:
                yield {"type": "text", "text": "\n\n"}
            current = chunk.id
        wrote = True
        yield {"type": "text", "text": text}


def pending_approvals(agent, config: dict) -> list[dict]:
    """Paused tool calls waiting for a decision: [{id, name, args, description}]."""
    state = agent.get_state(config)
    out = []
    for it in getattr(state, "interrupts", ()) or ():
        value = it.value if isinstance(it.value, dict) else {}
        out.append({"id": it.id, "name": value.get("name"), "args": value.get("args") or {},
                    "description": value.get("description", "")})
    return out


def resume(interrupt_id: str, decision: dict) -> Command:
    return Command(resume={interrupt_id: decision})
