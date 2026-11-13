"""Model providers: one place to switch between Claude, Gemini and OpenAI."""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Provider:
    label: str
    key: str              # init_chat_model provider id
    env_key: str          # API key environment variable
    env_model: str        # model name environment variable
    default_model: str    # "" = the user must type one


PROVIDERS = {
    "Claude": Provider("Claude", "anthropic", "ANTHROPIC_API_KEY", "CLAUDE_MODEL", "claude-opus-5-5"),
    "Gemini": Provider("Gemini", "google_genai", "GOOGLE_API_KEY", "GEMINI_MODEL", "gemini-3.5-flash-lite"),
    "OpenAI": Provider("OpenAI", "openai", "OPENAI_API_KEY", "OPENAI_MODEL", ""),
}


def default_model(label: str) -> str:
    p = PROVIDERS[label]
    return os.environ.get(p.env_model, "").strip() or p.default_model


def default_key(label: str) -> str:
    return os.environ.get(PROVIDERS[label].env_key, "")


def make_model(label: str, model: str, api_key: str):
    from langchain.chat_models import init_chat_model

    p = PROVIDERS[label]
    kwargs = {}
    if p.key == "google_genai":
        kwargs["google_api_key"] = api_key
    else:
        kwargs["api_key"] = api_key
    if p.key == "anthropic":
        kwargs["max_tokens"] = 8192
    return init_chat_model(model, model_provider=p.key, **kwargs)
