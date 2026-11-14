"""Everything the web UI can ask for, independent of the web framework.

server.py turns these methods into HTTP routes. Streaming methods yield events
(dicts) that the browser receives as one JSON object per line:

    {"type": "status", "text": "Loading a skill"}     a tool started
    {"type": "text", "text": "..."}                   reply text, as it streams
    {"type": "error", "message": "..."}               the run failed (Retry offered)
    {"type": "done", ...}                             finished; the UI reloads its state
"""
from __future__ import annotations

import hashlib
import os
import threading
from dataclasses import dataclass
from typing import Callable, Iterator

from datetime import date, timedelta

from harness.clock import WEEKDAY_NAMES, Clock, fmt_date
from harness.identity import Identity, username_error
from harness.lc.models import PROVIDERS, default_key, default_model
from harness.lc.tracing import HOSTS
from harness.ops import Workspace
from harness.paths import PathError, resolve
from harness.runtime import RuntimePaths, default_runtime_root
from harness.seed import PRESETS, reset

TITLES = {
    "publish_assignment": "Publish assignment",
    "update_assignment": "Change assignment",
    "save_hints": "Save hints",
    "set_student_access": "Change what students can see",
    "commit_changes": "Commit (submit)",
    "add_event": "Add calendar event",
    "write_file": "Write course file",
    "append_to_file": "Add to course file",
    "save_upload": "Save attachment into course files",
    "remember": "Add to course memory",
}
REJECT_DEFAULTS = {
    "commit_changes": "The user did not approve this commit. Don't retry; ask what to change.",
    "publish_assignment": "The professor rejected this draft. Ask what to change before trying again.",
}
REJECT_DEFAULT = "The user rejected this action. Don't retry it; ask what they want instead."
PRESET_LABELS = {"before_hw3": "Before HW3 (publish it live)", "after_hw3": "After HW3 (fallback)"}


def suggestions(role: str, seed_day: date) -> list[str]:
    """Example prompts for the welcome screen, worded for the day the demo data was built."""
    day = lambda n: WEEKDAY_NAMES[(seed_day + timedelta(days=n)).weekday()]
    if role == "professor":
        return [
            f"Add these resources to last {day(0)}'s lecture: https://en.wikipedia.org/wiki/Red%E2%80%93black_tree "
            "and https://visualgo.net/en/avl",
            f"This is HW3 with its starter code and solution. Deadline is {day(2)}. Tell students it's a pretty "
            "tough one so keep time for it. Will upload the hints later tonight.",
            "Here are the HW3 hints",
            "Here is HW4",
            "Who hasn't submitted HW2?",
            "Release the HW2 solution",
        ]
    return [
        "Any new assignment since yesterday?",
        "How does my week look?",
        "Here are my notes from today's lecture, add them to my course notes",
        "Can you check my HW3?",
        "I'm stuck on deleting a node with two children in HW3",
        "Submit my HW3",
    ]


class RequestError(ValueError):
    """A bad request from the browser; shown to the user as is."""


@dataclass(frozen=True)
class Settings:
    role: str
    username: str
    provider: str
    model: str
    api_key: str
    lf_public: str
    lf_secret: str
    lf_host: str
    enforce: bool

    @classmethod
    def parse(cls, d: dict | None) -> "Settings":
        d = d or {}
        role = d.get("role", "student")
        if role not in ("student", "professor"):
            raise RequestError("Role must be student or professor.")
        username = "professor" if role == "professor" else str(d.get("username") or "").strip()
        if role == "student":
            err = username_error(username)
            if err:
                raise RequestError(f"Username: {err}")
        provider = d.get("provider") or "Claude"
        if provider not in PROVIDERS:
            raise RequestError(f"Unknown provider {provider}.")
        return cls(
            role=role, username=username, provider=provider,
            model=str(d.get("model") or "").strip() or default_model(provider),
            api_key=str(d.get("api_key") or "").strip() or default_key(provider),
            lf_public=str(d.get("lf_public") or "").strip() or os.environ.get("LANGFUSE_PUBLIC_KEY", ""),
            lf_secret=str(d.get("lf_secret") or "").strip() or os.environ.get("LANGFUSE_SECRET_KEY", ""),
            lf_host=str(d.get("lf_host") or "").strip() or os.environ.get("LANGFUSE_HOST", HOSTS["US cloud"]),
            enforce=bool(d.get("enforce", True)),
        )

    @property
    def identity(self) -> Identity:
        return Identity.professor() if self.role == "professor" else Identity.student(self.username)

    @property
    def conversation_key(self) -> str:
        return f"{self.role}:{self.username}:{self.provider}:{'mw' if self.enforce else 'prompt'}"

    @property
    def ready(self) -> bool:
        return bool(self.model and self.api_key)


class Service:
    def __init__(self, root=None, runner_factory: Callable | None = None, needs_key: bool = True):
        self.rt = RuntimePaths(root or default_runtime_root())
        if not self.rt.exists():
            reset(self.rt.root, "before_hw3")
        self.custom_runner = runner_factory
        self.needs_key = needs_key
        self.lock = threading.RLock()
        self._clear()

    def _clear(self) -> None:
        self.threads: dict[str, int] = {}
        self.transcripts: dict[str, list[dict]] = {}
        self.changed: dict[str, set[str]] = {}
        self.retry: dict[str, tuple] = {}
        self.busy: set[str] = set()
        self._agents: dict = {}
        self._tracers: dict = {}
        self._checkpointer = None

    # ------------------------------------------------------------------ plumbing
    def workspace(self, s: Settings, user_texts: list[str] | None = None) -> Workspace:
        return Workspace(self.rt, s.identity, enforce=s.enforce, clock=Clock(self.rt.state),
                         user_texts=user_texts)

    def thread_id(self, s: Settings) -> str:
        with self.lock:
            n = self.threads.setdefault(s.conversation_key, 1)
        return f"{s.conversation_key}:{n}"

    def ready(self, s: Settings) -> bool:
        return s.ready or not self.needs_key

    def tracer(self, s: Settings):
        from harness.lc.tracing import Tracer

        key = (s.lf_public, s.lf_secret, s.lf_host)
        with self.lock:
            if key not in self._tracers:
                self._tracers[key] = Tracer(*key)
            return self._tracers[key]

    def tracing_status(self, s: Settings) -> dict:
        if not (s.lf_public and s.lf_secret):
            return {"on": False, "message": "Tracing off (no keys)"}
        t = self.tracer(s)
        return {"on": t.ok, "message": "Tracing on" if t.ok else f"Tracing off: {t.error}"}

    def runner(self, s: Settings):
        if self.custom_runner:
            return self.custom_runner(s)
        from harness.lc.agent import build_agent
        from harness.lc.models import make_model
        from harness.lc.runner import LangChainRunner
        from langgraph.checkpoint.memory import InMemorySaver

        with self.lock:
            if self._checkpointer is None:
                self._checkpointer = InMemorySaver()
            key = (s.provider, s.model, hashlib.sha256(s.api_key.encode()).hexdigest()[:12])
            if key not in self._agents:
                self._agents[key] = build_agent(make_model(s.provider, s.model, s.api_key), self._checkpointer)
            agent = self._agents[key]
        return LangChainRunner(s, str(self.rt.root), agent, self.tracer(s))

    # ------------------------------------------------------------------ reads
    def config(self) -> dict:
        return {
            "providers": [{"label": p.label, "default_model": default_model(p.label),
                           "env_key_name": p.env_key, "env_key_set": bool(default_key(p.label))}
                          for p in PROVIDERS.values()],
            "langfuse": {"env_set": bool(os.environ.get("LANGFUSE_PUBLIC_KEY") and
                                         os.environ.get("LANGFUSE_SECRET_KEY")),
                         "env_host": os.environ.get("LANGFUSE_HOST", ""),
                         "hosts": [{"label": k, "url": v} for k, v in HOSTS.items()]},
            "presets": [{"id": p, "label": PRESET_LABELS[p]} for p in PRESETS],
            "needs_key": self.needs_key,
        }

    def state(self, s: Settings) -> dict:
        ws = self.workspace(s)
        warning = ws.ensure_user()
        tid = self.thread_id(s)
        pending = []
        if self.ready(s):
            try:
                pending = self._pending_items(s, tid, self.runner(s))
            except Exception as err:  # a bad key or model shouldn't break the page
                warning = f"Couldn't load the model: {err}"
        clock = Clock(self.rt.state)
        seed_day = clock.seed_day() or ws.now().date()
        if not warning and clock.mode == "real" and seed_day != ws.now().date():
            warning = (f"The demo data was set up for {fmt_date(seed_day)}. "
                       "Reset demo to line it up with today.")
        return {
            "thread_id": tid,
            "clock_mode": clock.mode,
            "suggestions": suggestions(s.role, seed_day),
            "identity": s.identity.display,
            "transcript": self.transcripts.get(tid, []),
            "pending": pending,
            "tree": ws.tree(),
            "changed": sorted(self.changed.get(tid, set())),
            "demo_now": ws.now().isoformat(),
            "warning": warning,
            "tracing": self.tracing_status(s),
            "ready": self.ready(s),
            "busy": tid in self.busy,
            "can_retry": tid in self.retry,
        }

    def file(self, s: Settings, vpath: str) -> dict:
        ws = self.workspace(s)
        text = ws.read_for_ui(vpath)
        if text is None:
            raise RequestError("That file isn't available.")
        out = {"path": vpath, "text": text, "hidden": False, "can_toggle": False,
               "readonly": True, "changed": vpath in self.changed.get(self.thread_id(s), set())}
        try:
            vp = resolve(self.rt, s.identity, vpath)
        except PathError as err:
            raise RequestError(str(err)) from err
        if vp.root == "course":
            out["hidden"] = ws.manifest.is_hidden(vp.rel)
            out["can_toggle"] = s.role == "professor" and vp.rel != "ACCESS.yaml"
            out["readonly"] = s.role == "student"
        elif vp.root in ("me", "submission"):
            out["readonly"] = False
        return out

    def preview(self, s: Settings, name: str, args: dict) -> dict:
        tid = self.thread_id(s)
        texts = self.runner(s).human_texts(tid) if self.ready(s) else []
        return self.workspace(s, texts).preview(name, args)

    def _pending_items(self, s: Settings, tid: str, runner) -> list[dict]:
        items = runner.pending(tid)
        if not items:
            return []
        ws = self.workspace(s, runner.human_texts(tid))
        return [{**it, "title": TITLES.get(it["name"], it["name"]), "preview": ws.preview(it["name"], it["args"])}
                for it in items]

    # ------------------------------------------------------------------ writes
    def set_access(self, s: Settings, vpath: str, access: str) -> None:
        """The professor's switch in the file viewer (a direct human action)."""
        if s.role != "professor":
            raise RequestError("Only the professor can change what students see.")
        if access not in ("read", "hidden"):
            raise RequestError("access must be read or hidden")
        try:
            vp = resolve(self.rt, s.identity, vpath)
        except PathError as err:
            raise RequestError(str(err)) from err
        if vp.root != "course" or not vp.rel or vp.rel == "ACCESS.yaml" or not vp.real.exists():
            raise RequestError("Only files in course memory have student access settings.")
        self.workspace(s).manifest.set(vp.rel, access, is_dir=vp.real.is_dir())

    def new_conversation(self, s: Settings) -> None:
        with self.lock:
            self.threads[s.conversation_key] = self.threads.get(s.conversation_key, 1) + 1

    def reset(self, preset: str) -> None:
        if preset not in PRESETS:
            raise RequestError(f"Unknown preset {preset}.")
        with self.lock:
            if self.busy:
                raise RequestError("Wait for the current reply to finish.")
            reset(self.rt.root, preset)
            tracers = self._tracers
            self._clear()
            self._tracers = tracers  # keep verified Langfuse clients
            if hasattr(self.custom_runner, "reset"):
                self.custom_runner.reset()

    # ------------------------------------------------------------------ turns
    def chat(self, s: Settings, text: str, files: list[tuple[str, bytes]]) -> Iterator[dict]:
        tid = self.thread_id(s)
        text = (text or "").strip()
        ws = self.workspace(s)
        names = [ws.stage_upload(name, data) for name, data in files]
        if not text and not names:
            yield {"type": "error", "message": "Type a message or attach a file."}
            return
        content = text or "(see attached files)"
        if names:
            content += "\n\n[Attached: " + ", ".join(names) + "]"
        with self.lock:
            self.transcripts.setdefault(tid, []).append({"role": "user", "text": text, "files": names})
            self.changed[tid] = set()
        runner = self.runner(s)
        yield from self._run(s, tid, runner, runner.user_payload(content), names)

    def decide(self, s: Settings, interrupt_id: str, decision: dict) -> Iterator[dict]:
        tid = self.thread_id(s)
        runner = self.runner(s)
        item = next((p for p in runner.pending(tid) if p["id"] == interrupt_id), None)
        if item is None:
            yield {"type": "error", "message": "That approval is no longer waiting. Reload the page."}
            return
        kind = (decision or {}).get("type")
        if kind == "approve":
            decision = {"type": "approve"}
            record = f"Approved: {self._summary(item)}"
        elif kind == "edit":
            edited = decision.get("edited_action") or {}
            if edited.get("name") != item["name"] or not isinstance(edited.get("args"), dict):
                yield {"type": "error", "message": "Edited action doesn't match the paused call."}
                return
            decision = {"type": "edit", "edited_action": {"name": item["name"], "args": edited["args"]}}
            record = f"Approved with edits: {self._summary(item)}"
        elif kind == "reject":
            msg = str(decision.get("message") or "").strip() or REJECT_DEFAULTS.get(item["name"], REJECT_DEFAULT)
            decision = {"type": "reject", "message": msg}
            record = f"Rejected: {self._summary(item)}"
        else:
            yield {"type": "error", "message": "Decision must be approve, edit or reject."}
            return
        with self.lock:
            self.transcripts.setdefault(tid, []).append({"role": "card", "text": record, "ok": kind != "reject"})
        yield from self._run(s, tid, runner, runner.resume_payload(interrupt_id, decision), [])

    def retry_last(self, s: Settings) -> Iterator[dict]:
        tid = self.thread_id(s)
        with self.lock:
            saved = self.retry.get(tid)
            log = self.transcripts.get(tid, [])
            if saved and log and log[-1]["role"] == "error":
                log.pop()
        if not saved:
            yield {"type": "error", "message": "Nothing to retry."}
            return
        payload, attachments = saved
        yield from self._run(s, tid, self.runner(s), payload, attachments)

    def _run(self, s: Settings, tid: str, runner, payload, attachments: list[str]) -> Iterator[dict]:
        with self.lock:
            if tid in self.busy:
                yield {"type": "error", "message": "Still working on the previous message."}
                return
            self.busy.add(tid)
        try:
            ws = self.workspace(s)
            before = ws.snapshot()
            parts: list[str] = []
            try:
                for ev in runner.stream(payload, tid, attachments):
                    if ev.get("type") == "text":
                        parts.append(ev["text"])
                    yield ev
                trace_url = runner.finish()
            except Exception as err:
                message = f"{type(err).__name__}: {err}"
                with self.lock:
                    self.retry[tid] = (payload, attachments)
                    log = self.transcripts.setdefault(tid, [])
                    if "".join(parts).strip():
                        log.append({"role": "assistant", "text": "".join(parts)})
                    log.append({"role": "error", "text": message})
                yield {"type": "error", "message": message}
                return
            text = "".join(parts)
            with self.lock:
                self.retry.pop(tid, None)
                if text.strip():
                    self.transcripts.setdefault(tid, []).append(
                        {"role": "assistant", "text": text, "trace_url": trace_url})
                after = ws.snapshot()
                self.changed.setdefault(tid, set()).update(k for k, v in after.items() if before.get(k) != v)
            yield {"type": "done"}
        finally:
            with self.lock:
                self.busy.discard(tid)

    @staticmethod
    def _summary(item: dict) -> str:
        name, args = item["name"], item["args"]
        title = TITLES.get(name, name)
        if "path" in args:
            return f"{title.lower()} {args['path']}"
        if "assignment_id" in args:
            return f"{title.lower()} {str(args['assignment_id']).upper()}"
        if name == "commit_changes":
            return f"commit \"{args.get('message', '')}\""
        if name == "add_event":
            return f"event \"{args.get('title', '')}\""
        if name == "remember":
            return "course memory"
        return title.lower()
