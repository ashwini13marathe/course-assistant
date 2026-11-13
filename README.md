# CS 201 Course Assistant

A custom agent harness for the DevFest workshop **Build Your Own Claude Code: Agent Harness Engineering from Scratch**. A professor and students share one memory tree and a git submissions repo; permissions, approvals and context are all owned by the harness, and every step is traced in Langfuse.

## Run it

### In a GitHub Codespace (no local setup)

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/ashwini13marathe/course-assistant?quickstart=1)

1. Click the badge. When asked, paste a `GOOGLE_API_KEY` (free at [aistudio.google.com/apikey](https://aistudio.google.com/apikey)) or skip and paste one in the app's sidebar later.
2. Wait for the build. The app starts by itself and opens in a new tab (or open the **Ports** panel and click port 8000).
3. To drop demo files into the chat, download them first: right-click `demo_uploads/...` in the Explorer and choose **Download**.

Stop the codespace when you're done (github.com/codespaces), since it uses your free monthly hours.

### Locally

```bash
uv sync                          # Python 3.11+
cp .env.example .env             # optional: keys here pre-fill the sidebar
uv run python server.py          # opens http://127.0.0.1:8000
```

`--port 9000` picks another port; `--no-browser` skips opening a tab.

The first run builds `runtime/` from `seed/`. Reset any time from the sidebar (**Reset demo**) or with:

```bash
uv run python scripts/reset.py                    # before_hw3: publish HW3 live
uv run python scripts/reset.py --preset after_hw3 # fallback with HW3 already published
```

### Try the UI without an API key

`tests/fake_runner.py` swaps the model for a short keyword script that still uses the real tools, files and approval cards. Useful for rehearsing the screen and for UI changes:

```bash
uv run python tests/fake_runner.py   # http://127.0.0.1:8765
```

### Tests

```bash
uv run pytest
```

## Demo files

`demo_uploads/` holds the files to drag into the chat during the demo (HW3 and HW4 with starter code and solutions, HW3 hints, Alice's buggy HW3 and her lecture notes). Its [README](demo_uploads/README.md) is the demo script: what to drop, what to type, and what should happen.

## Dates

"Now" is the real time. **Reset demo** builds the course around the day you press it: today is a lecture day, last week's lecture exists, HW2 closed a week ago, and Alice's calendar is busiest around HW3's deadline (two days out). If you reset on an earlier day, the app shows a reminder to reset again. To rehearse a fixed day, set `DEMO_NOW` in `.env` (see `.env.example`).

## How it fits together

```
server.py              Starlette app: JSON routes plus streamed replies (one JSON event per line)
web/                   the page: index.html, style.css, app.js (plain JavaScript, no build step)
webui/service.py       what the page can ask for: state, files, turns, approvals, reset
harness/
  ops.py               every tool's real behavior, permission checks, approval previews
  policy.py paths.py   can() and virtual paths: the single source of truth for access
  access.py            per-file student access (memory/course/ACCESS.yaml)
  context.py           exactly what the model sees each turn
  assignments.py       publishing, naming conventions, the deadline-quote check
  hints.py skills.py lectures.py calendar.py gitops.py memory_files.py
  lc/                  LangChain layer: tools, middleware, agent, runner, models, tracing
seed/                  the demo world (course memory, skills, Alice, calendar, repo)
tests/                 core, scenario and service tests; fake-model middleware test; fake runner
```

Middleware order: tool filter → drop old thinking → context snapshot (once per user message) → permission gate → approvals (human in the loop) → model call limit.
