"""Run context: set by the app on every call, never by anything typed in chat."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..clock import Clock
from ..identity import Identity
from ..ops import Workspace
from ..runtime import RuntimePaths


@dataclass
class AppContext:
    role: str
    username: str
    runtime_root: str
    enforce: bool = True          # False = "prompt only" guardrails, for the demo beat
    attachments: list[str] = field(default_factory=list)

    @property
    def identity(self) -> Identity:
        return Identity.professor() if self.role == "professor" else Identity.student(self.username)

    @property
    def rt(self) -> RuntimePaths:
        return RuntimePaths(Path(self.runtime_root))


def get_context(runtime) -> AppContext:
    ctx = getattr(runtime, "context", None)
    if isinstance(ctx, dict):
        ctx = AppContext(**ctx)
    if not isinstance(ctx, AppContext):
        raise RuntimeError("The agent was run without an AppContext; pass context=AppContext(...).")
    return ctx


def message_text(msg) -> str:
    text = getattr(msg, "text", None)
    if callable(text):
        text = text()
    if isinstance(text, str):
        return text
    content = getattr(msg, "content", "")
    if isinstance(content, str):
        return content
    return " ".join(b.get("text", "") for b in content if isinstance(b, dict))


def human_texts(state) -> list[str]:
    msgs = (state or {}).get("messages", []) if isinstance(state, dict) else getattr(state, "messages", [])
    return [message_text(m) for m in msgs if getattr(m, "type", "") == "human"]


def workspace_for(ctx: AppContext, state=None) -> Workspace:
    rt = ctx.rt
    return Workspace(rt, ctx.identity, enforce=ctx.enforce, clock=Clock(rt.state),
                     user_texts=human_texts(state))
