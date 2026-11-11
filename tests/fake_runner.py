"""A scripted stand-in for the LangChain agent, for UI and service tests.

It uses the real Workspace tools, so files, permissions and approval previews are
real; only the "model" is a keyword script. Run the UI with it:

    python tests/fake_runner.py      # http://127.0.0.1:8765, no API key needed
"""
from __future__ import annotations

import re
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from harness.clock import Clock  # noqa: E402
from harness.ops import Workspace, needs_approval  # noqa: E402

HW3 = {
    "assignment_id": "hw3", "title": "Binary search trees", "overview": "Implement a binary search tree with insert, contains, delete, inorder and height.",
    "professor_notes": "This is a pretty tough one, so keep time to work on it. Hints will be uploaded tonight.",
    "hints_status": "coming",
    "review_checklist": "- [ ] `delete` handles a leaf, one child and two children\n- [ ] `height` is -1 for an empty tree",
}
LONG = """Here's your week at a glance.

## Today
- Work shift 3:00 to 7:00 PM
- Robotics club 7:30 to 9:00 PM

## Tomorrow
- MATH 240 review 9:00 AM to 12:00 PM
- Library job 12:30 to 4:00 PM
- **MATH 240 midterm** 6:00 to 8:00 PM

## The day after
- CS 201 lecture 10:00 to 11:15 AM
- Work 12:00 to 5:00 PM
- **HW3 due 11:59 PM**, during the hackathon kickoff (6:00 to 11:00 PM)

| Day | Free time | Longest block |
| --- | --- | --- |
| Today | 2 h | 1 h |
| Tomorrow | 4 h 45 min | 2 h |
| Day after | 3 h | 1 h |

HW3 is estimated at about 6 hours and the professor says it's a tough one. You have about 9¾ free hours before it's due, none longer than 2 hours, so I'd start today.

Want me to add study blocks for Wednesday 4:00 to 6:00 PM and Thursday 5:00 to 6:00 PM?"""


class FakeRunner:
    def __init__(self, runtime_root: Path, delay: float = 0.004):
        self.rt_root = Path(runtime_root)
        self.delay = delay
        self.threads: dict[str, dict] = {}
        self.s = None

    # factory interface: Service calls runner_factory(settings)
    def __call__(self, settings):
        self.s = settings
        return self

    def reset(self):
        self.threads.clear()

    def _t(self, tid):
        return self.threads.setdefault(tid, {"human": [], "pending": []})

    def _day(self, offset: int):
        from datetime import timedelta
        from harness.clock import WEEKDAY_NAMES
        seed = Clock(self.rt_root / "state").seed_day()
        d = seed + timedelta(days=offset)
        return d, WEEKDAY_NAMES[d.weekday()]

    def _ws(self, tid):
        from harness.runtime import RuntimePaths
        rt = RuntimePaths(self.rt_root)
        return Workspace(rt, self.s.identity, enforce=self.s.enforce, clock=Clock(rt.state),
                         user_texts=self.human_texts(tid))

    def user_payload(self, content):
        return {"kind": "user", "content": content}

    def resume_payload(self, iid, decision):
        return {"kind": "resume", "id": iid, "decision": decision}

    def human_texts(self, tid):
        return list(self._t(tid)["human"])

    def pending(self, tid):
        return [dict(p) for p in self._t(tid)["pending"]]

    def finish(self):
        return None

    def _say(self, text):
        for piece in re.split(r"(\s+)", text):
            if piece:
                time.sleep(self.delay)
                yield {"type": "text", "text": piece}

    def _ask(self, tid, name, args):
        self._t(tid)["pending"].append({"id": uuid.uuid4().hex, "name": name, "args": args, "description": ""})

    def _tool(self, tid, name, args):
        yield {"type": "status", "text": f"Running {name}"}
        if needs_approval(name, args):
            self._ask(tid, name, args)
            return None
        return self._ws(tid).call(name, args)

    def stream(self, payload, tid, attachments):
        t = self._t(tid)
        if payload["kind"] == "resume":
            item = next(p for p in t["pending"] if p["id"] == payload["id"])
            t["pending"].remove(item)
            d = payload["decision"]
            if d["type"] == "reject":
                yield from self._say("Okay, I left it as it was. What would you like to change?")
                return
            args = d.get("edited_action", {}).get("args") or item["args"]
            yield {"type": "status", "text": f"Running {item['name']}"}
            out = self._ws(tid).call(item["name"], args)
            yield from self._say(f"Done. {out}")
            return

        text = payload["content"]
        t["human"].append(text)
        low = text.lower()
        yield {"type": "status", "text": "Loading a skill"}
        time.sleep(0.15)
        if "fail" in low:
            raise RuntimeError("The model provider returned 529 Overloaded")
        if "resource" in low:
            url = re.search(r"https?://\S+", text)
            link = f"- [Further reading]({url.group(0) if url else 'https://example.org'})"
            d, wd = self._day(-7)
            yield from self._say(f"Last {wd} was **{d:%a %b} {d.day}**, Lecture 18 (Balanced trees and AVL intuition). "
                                 "I'll add the link under Resources.")
            yield from self._tool(tid, "append_to_file", {"path": f"memory/course/lectures/{d.isoformat()}.md",
                                                          "under_heading": "Resources", "text": link})
        elif "hw3" in low and attachments:
            kinds = [{"upload": a, "kind": "solution" if "sol" in a.lower() else
                      "starter" if a.endswith(".py") else "handout"} for a in attachments]
            d, wd = self._day(2)
            yield from self._say("I read the files: the handout, the starter code and a complete solution. Here's the draft.")
            yield from self._tool(tid, "publish_assignment", {**HW3, "due": f"{d.isoformat()}T23:59",
                                                              "due_quote": wd, "files": kinds})
        elif "notes" in low:
            out = yield from self._tool(tid, "write_file", {
                "path": f"memory/me/notes/lectures/{self._day(0)[0].isoformat()}.md",
                "content": "# Lecture 20: AVL rotations\n\n## Notes\n\n- right rotation fixes left-left\n"})
            yield from self._say(f"Saved. {out}")
        elif "submit" in low:
            yield from self._say("Your HW3 folder has changes. Here's the commit for your approval.")
            yield from self._tool(tid, "commit_changes", {"message": "Submit HW3"})
        elif "edit the review skill" in low:
            ws = self._ws(tid)
            check = ws.check("write_file", {"path": "memory/course/skills/assignment-review/hw2/SKILL.md"})
            yield from self._say(f"I can't do that. {check.reason or 'Allowed.'}")
        else:
            yield from self._say(LONG)


if __name__ == "__main__":
    import uvicorn

    from harness.seed import reset
    from server import create_app
    from webui.service import Service

    runtime = ROOT / "runtime-fake"
    reset(runtime, "before_hw3")  # real clock, or DEMO_NOW if set
    fake = FakeRunner(runtime, delay=0.01)
    print("Fake-agent UI at http://127.0.0.1:8765")
    uvicorn.run(create_app(Service(runtime, runner_factory=fake, needs_key=False)), host="127.0.0.1", port=8765,
                log_level="warning")
