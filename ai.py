#!/usr/bin/env python3
"""Resource Shrimp — AI assistant: model router + text extraction.

Routes chat requests across free LLM providers and lets users bring their
own key. Local Ollama needs no key; Groq/OpenRouter use env keys or a
per-request key supplied by the user.

Text extraction turns a downloaded resource (PDF, subtitles, plain text)
into the context the model reasons over.
"""

import json
import mimetypes
import os
import re
import secrets
from urllib.request import Request, urlopen

# ── Providers ───────────────────────────────────────────────────────
# Cloud providers speak the OpenAI chat-completions dialect; Ollama has
# its own /api/chat shape. key_env=None means no key required (local).
PROVIDERS = {
    "openai": {
        "base": "https://api.openai.com/v1",
        "key_env": "OPENAI_API_KEY",
        "default_model": "gpt-4o-mini",
        "type": "openai",
    },
    "anthropic": {
        "base": "https://api.anthropic.com",
        "key_env": "ANTHROPIC_API_KEY",
        "default_model": "claude-3-5-haiku-latest",
        "type": "anthropic",
    },
    "groq": {
        "base": "https://api.groq.com/openai/v1",
        "key_env": "GROQ_API_KEY",
        "default_model": "llama-3.3-70b-versatile",
        "type": "openai",
    },
    "openrouter": {
        "base": "https://openrouter.ai/api/v1",
        "key_env": "OPENROUTER_API_KEY",
        "default_model": "meta-llama/llama-3.3-70b-instruct:free",
        "type": "openai",
    },
    "ollama": {
        "base": os.environ.get("OLLAMA_BASE", "http://localhost:11434"),
        "key_env": None,
        "default_model": None,   # resolved from the local server
        "type": "ollama",
    },
    "custom": {                  # user-supplied OpenAI-compatible endpoint
        "base": "",
        "key_env": None,
        "default_model": None,
        "type": "openai",
    },
}
# Preference order when the caller doesn't name a provider
PREFERENCE = ["groq", "openrouter", "openai", "anthropic", "ollama"]

MAX_CONTEXT_CHARS = 48000


def _env_key(provider):
    cfg = PROVIDERS.get(provider) or {}
    return os.environ.get(cfg["key_env"], "") if cfg.get("key_env") else ""


def _ollama_models():
    try:
        with urlopen(PROVIDERS["ollama"]["base"] + "/api/tags", timeout=3) as r:
            data = json.loads(r.read())
        return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []


def available():
    """List of providers usable right now, each with a default model."""
    out = []
    for name in PREFERENCE:
        if name == "ollama":
            models = _ollama_models()
            if models:
                out.append({"provider": "ollama", "model": models[0], "byok": False})
        elif _env_key(name):
            out.append({"provider": name, "model": PROVIDERS[name]["default_model"],
                        "byok": False})
    return out


def _post(url, payload, headers, timeout=120):
    body = json.dumps(payload).encode()
    h = {"Content-Type": "application/json"}
    h.update(headers or {})
    req = Request(url, data=body, headers=h)
    with urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _split_system(messages):
    """Anthropic wants the system prompt separate from the message list."""
    system_parts, conv = [], []
    for m in messages:
        if m.get("role") == "system":
            system_parts.append(m.get("content", ""))
        else:
            conv.append({"role": m["role"], "content": m["content"]})
    return "\n\n".join(p for p in system_parts if p), conv


def chat(messages, provider=None, key=None, model=None, base_url=None):
    """Send messages to a provider. Returns {answer, provider, model}.

    Resolution: explicit provider (with optional user key/base_url) wins;
    otherwise pick the first available provider in preference order.
    """
    if not provider:
        avail = available()
        if avail:
            provider = avail[0]["provider"]
            model = model or avail[0]["model"]
        else:
            raise RuntimeError("No AI provider available. Add an API key or run Ollama.")

    cfg = PROVIDERS.get(provider)
    if not cfg:
        raise RuntimeError(f"Unknown provider: {provider}")

    ptype = cfg["type"]
    base = (base_url or cfg["base"]).rstrip("/")
    if not model:
        model = cfg["default_model"] or (_ollama_models() or [None])[0]
    if not model:
        raise RuntimeError(f"No model set for provider {provider}")

    if ptype == "openai":
        api_key = key or _env_key(provider)
        if not api_key:
            raise RuntimeError(f"{provider} requires an API key")
        if not base:
            raise RuntimeError(f"{provider} requires a base URL")
        resp = _post(
            base + "/chat/completions",
            {"model": model, "messages": messages, "temperature": 0.2},
            {"Authorization": f"Bearer {api_key}"},
        )
        answer = resp["choices"][0]["message"]["content"]
    elif ptype == "anthropic":
        api_key = key or _env_key(provider)
        if not api_key:
            raise RuntimeError("anthropic requires an API key")
        system, conv = _split_system(messages)
        payload = {"model": model, "max_tokens": 1024, "messages": conv}
        if system:
            payload["system"] = system
        resp = _post(
            base + "/v1/messages",
            payload,
            {"x-api-key": api_key, "anthropic-version": "2023-06-01"},
        )
        answer = "".join(b.get("text", "") for b in resp.get("content", [])
                         if b.get("type") == "text")
    else:  # ollama — local models can be slow to load/infer, allow more time
        resp = _post(
            base + "/api/chat",
            {"model": model, "messages": messages, "stream": False},
            {},
            timeout=300,
        )
        answer = resp["message"]["content"]

    return {"answer": (answer or "").strip(), "provider": provider, "model": model}


# ── Text extraction ─────────────────────────────────────────────────
def _strip_subtitles(text):
    out = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.isdigit() or "-->" in s or s.upper() == "WEBVTT":
            continue
        out.append(re.sub(r"<[^>]+>", "", s))
    # de-dupe consecutive repeats common in auto-subs
    deduped = []
    for s in out:
        if not deduped or deduped[-1] != s:
            deduped.append(s)
    return "\n".join(deduped)


def extract_text(filepath, mime=None, max_chars=MAX_CONTEXT_CHARS):
    """Best-effort plain text from a resource file, or None if unsupported."""
    if not filepath or not os.path.isfile(filepath):
        return None
    low = filepath.lower()
    try:
        if low.endswith(".pdf") or (mime and "pdf" in mime):
            from pypdf import PdfReader
            reader = PdfReader(filepath)
            parts, total = [], 0
            for page in reader.pages[:80]:
                t = page.extract_text() or ""
                parts.append(t)
                total += len(t)
                if total >= max_chars:
                    break
            text = "\n".join(parts)
        elif low.endswith((".vtt", ".srt")):
            with open(filepath, "r", errors="ignore") as f:
                text = _strip_subtitles(f.read())
        elif (mime and mime.startswith("text")) or low.endswith((".txt", ".md", ".json", ".csv")):
            with open(filepath, "r", errors="ignore") as f:
                text = f.read()
        else:
            return None
    except Exception:
        return None
    text = (text or "").strip()
    return text[:max_chars] if text else None
