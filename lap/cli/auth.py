"""
LAP CLI authentication -- browser-based GitHub OAuth flow.

Uses only Python stdlib (urllib, json, webbrowser) -- zero new dependencies.
Credentials stored in ~/.lap/credentials.json.
"""

import json
import os
import stat
import sys
import urllib.request
import urllib.error
import webbrowser
from pathlib import Path

from lap import __version__


# ── Config ──────────────────────────────────────────────────────────

DEFAULT_REGISTRY = "https://registry.lap.sh"
CREDENTIALS_DIR = Path.home() / ".lap"
CREDENTIALS_FILE = CREDENTIALS_DIR / "credentials.json"


def get_registry_url():
    """Get registry URL from env or default."""
    return os.environ.get("LAP_REGISTRY", DEFAULT_REGISTRY).rstrip("/")


# ── Credentials ─────────────────────────────────────────────────────

def load_credentials():
    """Load credentials from disk. Returns dict or None."""
    if not CREDENTIALS_FILE.exists():
        return None
    try:
        return json.loads(CREDENTIALS_FILE.read_text(encoding='utf-8'))
    except (json.JSONDecodeError, OSError):
        return None


def save_credentials(token, username):
    """Save credentials to ~/.lap/credentials.json with restricted perms."""
    CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)
    data = {"token": token, "username": username}
    CREDENTIALS_FILE.write_text(json.dumps(data, indent=2))
    # Restrict file permissions (owner read/write only) -- skip on Windows
    if sys.platform != "win32":
        os.chmod(CREDENTIALS_FILE, stat.S_IRUSR | stat.S_IWUSR)


def clear_credentials():
    """Remove credentials file."""
    if CREDENTIALS_FILE.exists():
        CREDENTIALS_FILE.unlink()


def get_token():
    """Shortcut: load credentials and return token, or None."""
    creds = load_credentials()
    return creds["token"] if creds else None


# ── HTTP helpers ────────────────────────────────────────────────────

def api_request(method, path, body=None, token=None):
    """Make an HTTP request to the registry. Returns parsed JSON or raises."""
    url = f"{get_registry_url()}{path}"
    headers = {"Accept": "application/json", "User-Agent": f"lapsh/{__version__}"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body_text = e.read().decode() if e.fp else ""
        try:
            err = json.loads(body_text)
        except (json.JSONDecodeError, ValueError):
            err = {"error": body_text or f"HTTP {e.code}"}
        raise SystemExit(f"Error: {err.get('error', err.get('message', body_text))}")


# ── SSE stream ──────────────────────────────────────────────────────

def poll_sse_stream(session_id):
    """Connect to SSE stream, wait for auth completion. Returns (token, username)."""
    url = f"{get_registry_url()}/auth/cli/stream/{session_id}"
    req = urllib.request.Request(url, headers={"Accept": "text/event-stream"})

    try:
        resp = urllib.request.urlopen(req, timeout=130)
    except (urllib.error.URLError, OSError) as e:
        raise SystemExit(f"Error connecting to registry: {e}")

    for raw_line in resp:
        line = raw_line.decode("utf-8", errors="replace").strip()
        if not line.startswith("data: "):
            continue
        payload = line[6:]
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            continue

        if "token" in data and "username" in data:
            return data["token"], data["username"]
        if "error" in data:
            raise SystemExit(f"Authentication failed: {data['error']}")

    raise SystemExit("Authentication timed out. Please try again.")
