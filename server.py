"""CS 201 course assistant: web server.

    uv run python server.py              # opens http://127.0.0.1:8000
    uv run python server.py --port 9000 --no-browser
"""
from __future__ import annotations

import argparse
import json
import logging
import threading
import webbrowser
from pathlib import Path

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, StreamingResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from webui.service import RequestError, Service, Settings  # noqa: E402

WEB = Path(__file__).resolve().parent / "web"
MAX_UPLOAD = 20 * 1024 * 1024
log = logging.getLogger("course-assistant")


def create_app(service: Service | None = None) -> Starlette:
    svc = service or Service()

    def guarded(handler):
        async def endpoint(request: Request):
            try:
                return await handler(request)
            except RequestError as err:
                return JSONResponse({"error": str(err)}, status_code=400)
            except Exception as err:  # keep the page alive; details go to the terminal
                log.exception("Request failed")
                return JSONResponse({"error": f"{type(err).__name__}: {err}"}, status_code=500)
        return endpoint

    def stream(events) -> StreamingResponse:
        def lines():
            try:
                for ev in events:
                    yield json.dumps(ev) + "\n"
            except RequestError as err:
                yield json.dumps({"type": "error", "message": str(err)}) + "\n"
            except Exception as err:
                log.exception("Stream failed")
                yield json.dumps({"type": "error", "message": f"{type(err).__name__}: {err}"}) + "\n"
        return StreamingResponse(lines(), media_type="application/x-ndjson",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    async def body(request: Request) -> dict:
        try:
            data = await request.json()
        except ValueError as err:
            raise RequestError("Expected a JSON body.") from err
        if not isinstance(data, dict):
            raise RequestError("Expected a JSON object.")
        return data

    async def index(request):
        return FileResponse(WEB / "index.html", headers={"Cache-Control": "no-cache"})

    async def config(request):
        return JSONResponse(svc.config())

    async def state(request):
        data = await body(request)
        return JSONResponse(svc.state(Settings.parse(data.get("settings"))))

    async def file(request):
        data = await body(request)
        return JSONResponse(svc.file(Settings.parse(data.get("settings")), str(data.get("path", ""))))

    async def access(request):
        data = await body(request)
        svc.set_access(Settings.parse(data.get("settings")), str(data.get("path", "")), str(data.get("access", "")))
        return JSONResponse({"ok": True})

    async def preview(request):
        data = await body(request)
        s = Settings.parse(data.get("settings"))
        return JSONResponse(svc.preview(s, str(data.get("name", "")), dict(data.get("args") or {})))

    async def new(request):
        data = await body(request)
        svc.new_conversation(Settings.parse(data.get("settings")))
        return JSONResponse({"ok": True})

    async def reset(request):
        data = await body(request)
        svc.reset(str(data.get("preset", "before_hw3")))
        return JSONResponse({"ok": True})

    async def chat(request):
        form = await request.form(max_part_size=MAX_UPLOAD)
        try:
            s = Settings.parse(json.loads(form.get("settings") or "{}"))
        except ValueError as err:
            raise RequestError(str(err)) from err
        files = []
        for f in form.getlist("files"):
            if hasattr(f, "read"):
                files.append((f.filename or "upload", await f.read()))
        return stream(svc.chat(s, str(form.get("text") or ""), files))

    async def decide(request):
        data = await body(request)
        s = Settings.parse(data.get("settings"))
        return stream(svc.decide(s, str(data.get("interrupt_id", "")), dict(data.get("decision") or {})))

    async def retry(request):
        data = await body(request)
        return stream(svc.retry_last(Settings.parse(data.get("settings"))))

    routes = [
        Route("/", index),
        Route("/api/config", guarded(config)),
        Route("/api/state", guarded(state), methods=["POST"]),
        Route("/api/file", guarded(file), methods=["POST"]),
        Route("/api/access", guarded(access), methods=["POST"]),
        Route("/api/preview", guarded(preview), methods=["POST"]),
        Route("/api/new", guarded(new), methods=["POST"]),
        Route("/api/reset", guarded(reset), methods=["POST"]),
        Route("/api/chat", guarded(chat), methods=["POST"]),
        Route("/api/decide", guarded(decide), methods=["POST"]),
        Route("/api/retry", guarded(retry), methods=["POST"]),
        Mount("/static", StaticFiles(directory=WEB), name="static"),
    ]
    return Starlette(routes=routes)


def main() -> None:
    import uvicorn

    parser = argparse.ArgumentParser(description="CS 201 course assistant")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    url = f"http://{args.host}:{args.port}"
    if not args.no_browser:
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    print(f"Course assistant running at {url}")
    uvicorn.run(create_app(), host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
