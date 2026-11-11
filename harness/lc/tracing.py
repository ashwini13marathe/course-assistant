"""Langfuse tracing that can never break the app.

No keys, wrong keys, a network error or an SDK change all end the same way:
tracing is off for the session and the chat works as before.
"""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)

HOSTS = {
    "EU cloud": "https://cloud.langfuse.com",
    "US cloud": "https://us.cloud.langfuse.com",
}


class Tracer:
    def __init__(self, public_key: str, secret_key: str, host: str):
        self.ok = False
        self.error: str | None = None
        self.client = None
        self.handler = None
        if not (public_key and secret_key):
            self.error = "No Langfuse keys"
            return
        try:
            from langfuse import Langfuse
            from langfuse.langchain import CallbackHandler

            try:
                self.client = Langfuse(public_key=public_key, secret_key=secret_key, host=host)
            except TypeError:
                self.client = Langfuse(public_key=public_key, secret_key=secret_key, base_url=host)
            check = getattr(self.client, "auth_check", None)
            if check is not None and not check():
                raise RuntimeError("Langfuse rejected these keys")
            self.handler = CallbackHandler(public_key=public_key)
            self.ok = True
        except Exception as err:
            self.error = str(err) or err.__class__.__name__
            log.warning("Tracing off: %s", self.error)

    def run_config(self, user_id: str, session_id: str, tags: list[str]) -> dict:
        if not self.ok:
            return {}
        return {
            "callbacks": [self.handler],
            "metadata": {"langfuse_user_id": user_id, "langfuse_session_id": session_id,
                         "langfuse_tags": tags},
        }

    def flush(self) -> None:
        if not self.ok:
            return
        try:
            self.client.flush()
        except Exception as err:
            self.ok, self.error = False, f"flush failed: {err}"

    def last_trace_url(self) -> str | None:
        if not self.ok:
            return None
        try:
            trace_id = getattr(self.handler, "last_trace_id", None)
            return self.client.get_trace_url(trace_id=trace_id) if trace_id else None
        except Exception:
            return None
