"""The middleware stack, in order:

1. filter_tools_by_role  (wraps each model call)  hide tools the role can never use
2. drop_old_thinking     (wraps each model call)  send thinking from the current turn only
3. snapshot_context      (before each model call) build the context once per user message
4. course_context        (dynamic prompt)         use that snapshot as the system prompt
5. permission_gate       (wraps each tool call)   can(); deny without running the tool
6. approvals             (human in the loop)      pause gated calls for an approval card
7. call limit                                     stop loops and runaway cost

Why snapshot the context: models with extended thinking (Claude) sign each thinking
block against the exact system prompt. If the prompt changes between model calls in
one turn (the clock ticks, a tool edits course memory), the next call is rejected.
So the context is built once when a user message arrives and reused for every model
call in that turn, including after an approval card resumes the run. Thinking from
earlier turns isn't needed by the model, so it is dropped before each call.

The gate sits before approvals, so a denied call never reaches the human. It has
no side effects before calling the handler, because a paused call re-runs it on resume.
"""

import logging
import subprocess, sys

from langchain.agents.middleware import (
    AgentState,
    HumanInTheLoopMiddleware,
    before_model,
    dynamic_prompt,
    wrap_model_call,
    wrap_tool_call,
    after_agent,
)
from langchain_core.messages import ToolMessage
from typing_extensions import NotRequired

from ..context import build_system_prompt
from ..ops import ALWAYS_APPROVE, COURSE_WRITE_TOOLS, needs_approval, tools_for_role
from .context import get_context, workspace_for

log = logging.getLogger(__name__)

THINKING_TYPES = {"thinking", "redacted_thinking"}


def _tool_name(t) -> str | None:
    return getattr(t, "name", None) or (t.get("name") if isinstance(t, dict) else None)


@after_agent
def ding(state, runtime):
    """Play a sound when the agent finishes. Not in the stack: add it to build_middleware()."""
    if sys.platform == "darwin":
        subprocess.Popen(["afplay", "/System/Library/Sounds/Pop.aiff"])
    elif sys.platform == "win32":
        import winsound
        winsound.MessageBeep()
    else:
        print("\a", end="", flush=True)  # terminal bell


@wrap_model_call
def filter_tools_by_role(request, handler):
    ctx = get_context(request.runtime)
    if ctx.enforce:
        allowed = set(tools_for_role(ctx.role))
        request = request.override(tools=[t for t in request.tools if _tool_name(t) in allowed])
    return handler(request)


# -- per-turn context -----------------------------------------------------------
class TurnState(AgentState):
    turn_context: NotRequired[str]       # the system prompt for the current user message
    turn_context_key: NotRequired[str]   # which user message it was built for


def _last_human_index(messages) -> int:
    for i in range(len(messages) - 1, -1, -1):
        if getattr(messages[i], "type", "") == "human":
            return i
    return -1


def _last_human_key(messages) -> str:
    i = _last_human_index(messages)
    if i < 0:
        return "none"
    return getattr(messages[i], "id", None) or f"index-{i}"


def _fresh_prompt(runtime) -> str:
    ctx = get_context(runtime)
    ws = workspace_for(ctx)
    return build_system_prompt(ws.rt, ws.ident, ws.now(), ctx.attachments, ctx.enforce)


@before_model(state_schema=TurnState)
def snapshot_context(state, runtime):
    key = _last_human_key(state["messages"])
    if state.get("turn_context_key") == key and state.get("turn_context"):
        return None  # same user message (later step, or resumed after approval): keep it
    return {"turn_context": _fresh_prompt(runtime), "turn_context_key": key}


@dynamic_prompt
def course_context(request) -> str:
    state = request.state or {}
    snapshot = state.get("turn_context")
    if snapshot and state.get("turn_context_key") == _last_human_key(state.get("messages", [])):
        return snapshot
    return _fresh_prompt(request.runtime)  # fallback; shouldn't happen


@wrap_model_call
def drop_old_thinking(request, handler):
    """Remove thinking blocks from assistant messages before the latest user message."""
    messages = list(request.messages)
    last_human = _last_human_index(messages)
    changed = False
    for i in range(max(last_human, 0)):
        m = messages[i]
        if getattr(m, "type", "") != "ai" or not isinstance(m.content, list):
            continue
        kept = [b for b in m.content if not (isinstance(b, dict) and b.get("type") in THINKING_TYPES)]
        if len(kept) == len(m.content):
            continue
        if not kept and not getattr(m, "tool_calls", None):
            kept = [{"type": "text", "text": "(no reply text)"}]
        messages[i] = m.model_copy(update={"content": kept})
        changed = True
    return handler(request.override(messages=messages) if changed else request)


# -- tools ---------------------------------------------------------------------------
@wrap_tool_call
def permission_gate(request, handler):
    ctx = get_context(request.runtime)
    call = request.tool_call
    decision = workspace_for(ctx).check(call["name"], call.get("args") or {})
    if not decision.allowed:
        return ToolMessage(content=f"Permission denied: {decision.reason}",
                           tool_call_id=call["id"], name=call["name"], status="error")
    return handler(request)


def _when(name: str):
    def predicate(request) -> bool:
        return needs_approval(name, request.tool_call.get("args") or {})
    return predicate


def approvals() -> HumanInTheLoopMiddleware:
    decisions = ["approve", "edit", "reject"]
    interrupt_on = {name: {"allowed_decisions": decisions} for name in ALWAYS_APPROVE}
    for name in COURSE_WRITE_TOOLS | {"remember"}:
        interrupt_on[name] = {"allowed_decisions": decisions, "when": _when(name)}
    return HumanInTheLoopMiddleware(interrupt_on=interrupt_on, interrupt_mode="per_call",
                                    description_prefix="Needs your approval")


def call_limit(limit: int = 15):
    try:
        from langchain.agents.middleware import ModelCallLimitMiddleware
        return ModelCallLimitMiddleware(run_limit=limit, exit_behavior="end")
    except (ImportError, TypeError) as err:  # API drift: run without the limit rather than crash
        log.warning("Model call limit disabled: %s", err)
        return None


def build_middleware() -> list:
    stack = [filter_tools_by_role, drop_old_thinking, snapshot_context, course_context,
             permission_gate, approvals(), call_limit()]
    return [m for m in stack if m is not None]
