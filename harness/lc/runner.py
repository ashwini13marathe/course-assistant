"""The real agent behind the web UI: LangChain + Langfuse.

The web service talks to any object with this shape (see webui/service.py), so
the UI can also be driven by a scripted stand-in in tests.
"""
from __future__ import annotations

from .agent import pending_approvals, resume, stream_events
from .context import AppContext, human_texts


class LangChainRunner:
    def __init__(self, settings, runtime_root: str, agent, tracer):
        self.s = settings
        self.runtime_root = runtime_root
        self.agent = agent
        self.tracer = tracer

    def _config(self, tid: str, traced: bool = True) -> dict:
        config = {"configurable": {"thread_id": tid}}
        if traced:
            tags = [self.s.role, self.s.provider, "middleware" if self.s.enforce else "prompt-only"]
            config.update(self.tracer.run_config(self.s.username, tid, tags))
        return config

    def user_payload(self, content: str):
        return {"messages": [{"role": "user", "content": content}]}

    def resume_payload(self, interrupt_id: str, decision: dict):
        return resume(interrupt_id, decision)

    def stream(self, payload, tid: str, attachments: list[str]):
        ctx = AppContext(role=self.s.role, username=self.s.username, runtime_root=self.runtime_root,
                         enforce=self.s.enforce, attachments=attachments)
        yield from stream_events(self.agent, payload, self._config(tid), ctx)

    def pending(self, tid: str) -> list[dict]:
        return pending_approvals(self.agent, self._config(tid, traced=False))

    def human_texts(self, tid: str) -> list[str]:
        try:
            values = self.agent.get_state(self._config(tid, traced=False)).values
        except Exception:
            return []
        return human_texts(values)

    def finish(self) -> str | None:
        self.tracer.flush()
        return self.tracer.last_trace_url()
