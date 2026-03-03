"""
Shared utilities for LAP — token counting, model costs, safe file reading.

Single source of truth for functions previously duplicated across
benchmark.py, benchmark_all.py, report.py, agent_test.py, demo.py, and the SDK.
"""

import warnings
from pathlib import Path
from typing import Optional

__all__ = ["count_tokens", "MODEL_COSTS", "read_file_safe", "get_tiktoken_encoding",
           "AUTH_PARAM_NAMES", "AUTH_DESC_KEYWORDS", "resolve_ref"]

# Cost per 1K input tokens (USD) — approximate as of early 2026
MODEL_COSTS = {
    "gpt-4o": 0.0025,
    "gpt-4-turbo": 0.01,
    "claude-sonnet-4": 0.003,
    "claude-opus-4": 0.015,
    "gemini-1.5-pro": 0.00125,
}

# Module-level singleton for tiktoken encoding
_ENC_CACHE = {}


def get_tiktoken_encoding(model: str = "gpt-4o"):
    """Get a cached tiktoken encoding. Returns None if tiktoken is unavailable."""
    if model in _ENC_CACHE:
        return _ENC_CACHE[model]
    try:
        import tiktoken
        try:
            enc = tiktoken.encoding_for_model(model)
        except KeyError:
            enc = tiktoken.get_encoding("cl100k_base")
        _ENC_CACHE[model] = enc
        return enc
    except ImportError:
        return None


def count_tokens(text: str, model: str = "gpt-4o") -> int:
    """Count tokens using tiktoken. Falls back to len(text)//4 if unavailable."""
    enc = get_tiktoken_encoding(model)
    if enc:
        return len(enc.encode(text, disallowed_special=()))
    # Rough fallback
    return len(text) // 4


def read_file_safe(path: str, max_size: int = 50 * 1024 * 1024) -> Optional[str]:
    """Read a file with size limit. Returns None if file doesn't exist or is too large."""
    p = Path(path)
    if not p.exists():
        return None
    if p.stat().st_size > max_size:
        warnings.warn(f"File too large ({p.stat().st_size} bytes, max {max_size}): {path}")
        return None
    return p.read_text(encoding='utf-8')


# Parameter names that strongly suggest authentication
AUTH_PARAM_NAMES = frozenset({
    "api_key", "apikey", "api-key",
    "token", "access_token", "x-api-key",
    "authorization", "auth_token", "secret",
    "api_secret", "app_key", "appkey", "client_secret",
    "subscription-key", "ocp-apim-subscription-key",
    "x-auth-token", "api_token",
})

# Description keywords that suggest an auth parameter
AUTH_DESC_KEYWORDS = ("api key", "authentication", "auth token", "access token", "your key", "your token")


def resolve_ref(spec: dict, ref: str, _visited: set = None) -> dict:
    """Resolve a $ref pointer in a spec with cycle detection."""
    if _visited is None:
        _visited = set()
    if ref in _visited:
        raise ValueError(f"Circular $ref detected: {ref}")
    _visited.add(ref)
    parts = ref.lstrip("#/").split("/")
    node = spec
    for part in parts:
        if isinstance(node, list):
            try:
                node = node[int(part)]
            except (ValueError, IndexError):
                return {}
        elif isinstance(node, dict):
            node = node.get(part, {})
        else:
            return {}
    # If the resolved node itself contains a $ref, resolve it too
    if isinstance(node, dict) and "$ref" in node:
        return resolve_ref(spec, node["$ref"], _visited)
    return node
