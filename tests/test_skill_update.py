#!/usr/bin/env python3
"""Tests for skill update metadata helpers and check/pin/unpin commands."""

import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from lap.cli.main import (
    _compute_spec_hash,
    _is_valid_skill_name,
    _metadata_path,
    _read_metadata,
    _register_claude_hook,
    _register_cursor_hook,
    _validate_registry_url,
    _write_metadata,
    cmd_check,
    cmd_diff,
    cmd_init,
    cmd_pin,
    cmd_skill_install,
    cmd_unpin,
)


# ── _metadata_path ────────────────────────────────────────────────────


def test_metadata_path_claude():
    p = _metadata_path("claude")
    assert p == Path.home() / ".claude" / "lap-metadata.json"


def test_metadata_path_cursor():
    p = _metadata_path("cursor")
    assert p == Path.home() / ".cursor" / "lap-metadata.json"


# ── C1: _read_metadata() valid file ──────────────────────────────────


def test_read_metadata_valid(tmp_path, monkeypatch):
    data = {"skills": {"stripe": {"registryVersion": "1.2.0", "pinned": False}}}
    meta_file = tmp_path / "lap-metadata.json"
    meta_file.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr("lap.cli.main._metadata_path", lambda t: meta_file)
    result = _read_metadata("claude")
    assert result == data


# ── C2: _read_metadata() missing file ────────────────────────────────


def test_read_metadata_missing(tmp_path, monkeypatch):
    meta_file = tmp_path / "lap-metadata.json"
    monkeypatch.setattr("lap.cli.main._metadata_path", lambda t: meta_file)
    result = _read_metadata("claude")
    assert result == {"skills": {}}


# ── C3: _read_metadata() corrupt JSON ────────────────────────────────


def test_read_metadata_corrupt(tmp_path, monkeypatch, capsys):
    meta_file = tmp_path / "lap-metadata.json"
    meta_file.write_text("{this is not json{{{{", encoding="utf-8")
    monkeypatch.setattr("lap.cli.main._metadata_path", lambda t: meta_file)
    result = _read_metadata("claude")
    assert result == {"skills": {}}
    captured = capsys.readouterr()
    assert "Warning" in captured.err


# ── C4: _write_metadata() creates file ───────────────────────────────


def test_write_metadata_creates_file(tmp_path, monkeypatch):
    meta_file = tmp_path / "subdir" / "lap-metadata.json"
    monkeypatch.setattr("lap.cli.main._metadata_path", lambda t: meta_file)
    data = {"skills": {"stripe": {"registryVersion": "2.0.0"}}}
    _write_metadata("claude", data)
    assert meta_file.exists()
    written = json.loads(meta_file.read_text(encoding="utf-8"))
    assert written == data


# ── C5: _write_metadata() atomic write ───────────────────────────────


def test_write_metadata_atomic(tmp_path, monkeypatch):
    meta_file = tmp_path / "lap-metadata.json"
    monkeypatch.setattr("lap.cli.main._metadata_path", lambda t: meta_file)
    data = {"skills": {"stripe": {"registryVersion": "1.0.0"}}}
    _write_metadata("claude", data)
    # Verify the final file exists and tmp is gone
    assert meta_file.exists()
    tmp_file = meta_file.with_suffix(".tmp")
    assert not tmp_file.exists()
    written = json.loads(meta_file.read_text(encoding="utf-8"))
    assert written["skills"]["stripe"]["registryVersion"] == "1.0.0"


# ── C6: _compute_spec_hash() ─────────────────────────────────────────


def test_compute_spec_hash():
    content = "hello world"
    expected = "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest()
    assert _compute_spec_hash(content) == expected


def test_compute_spec_hash_empty():
    content = ""
    expected = "sha256:" + hashlib.sha256(b"").hexdigest()
    assert _compute_spec_hash(content) == expected


# ── C9: lap check --silent-if-clean all current (no output) ──────────


def test_check_silent_if_clean_no_updates(tmp_path, monkeypatch, capsys):
    meta_file = tmp_path / "lap-metadata.json"
    data = {"skills": {"stripe": {"registryVersion": "1.0.0", "pinned": False}}}
    meta_file.write_text(json.dumps(data), encoding="utf-8")

    def fake_metadata_path(t):
        if t == "claude":
            return meta_file
        return tmp_path / "no-exist.json"

    monkeypatch.setattr("lap.cli.main._metadata_path", fake_metadata_path)
    monkeypatch.setattr("lap.cli.auth.get_registry_url", lambda: "https://registry.lap.sh")

    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps({"results": [
        {"name": "stripe", "has_update": False, "installed_version": "1.0.0", "latest_version": "1.0.0"}
    ]}).encode("utf-8")
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = lambda s, *a: None

    with patch("urllib.request.urlopen", return_value=mock_resp):
        args = SimpleNamespace(silent_if_clean=True, json=False, target="auto")
        cmd_check(args)

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


# ── C10: lap check with updates prints notification ───────────────────


def test_check_with_updates_prints(tmp_path, monkeypatch, capsys):
    meta_file = tmp_path / "lap-metadata.json"
    data = {"skills": {"stripe": {"registryVersion": "1.0.0", "pinned": False}}}
    meta_file.write_text(json.dumps(data), encoding="utf-8")

    def fake_metadata_path(t):
        if t == "claude":
            return meta_file
        return tmp_path / "no-exist.json"

    monkeypatch.setattr("lap.cli.main._metadata_path", fake_metadata_path)
    monkeypatch.setattr("lap.cli.auth.get_registry_url", lambda: "https://registry.lap.sh")

    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps({"results": [
        {"name": "stripe", "has_update": True, "installed_version": "1.0.0", "latest_version": "2.0.0"}
    ]}).encode("utf-8")
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = lambda s, *a: None

    with patch("urllib.request.urlopen", return_value=mock_resp):
        args = SimpleNamespace(silent_if_clean=False, json=False, target="auto")
        cmd_check(args)

    captured = capsys.readouterr()
    assert "stripe" in captured.out
    assert "1.0.0" in captured.out
    assert "2.0.0" in captured.out
    assert "lapsh skill-install stripe" in captured.out


# ── C11: lap check --json valid JSON output ───────────────────────────


def test_check_json_output(tmp_path, monkeypatch, capsys):
    meta_file = tmp_path / "lap-metadata.json"
    data = {"skills": {"stripe": {"registryVersion": "1.0.0", "pinned": False}}}
    meta_file.write_text(json.dumps(data), encoding="utf-8")

    def fake_metadata_path(t):
        if t == "claude":
            return meta_file
        return tmp_path / "no-exist.json"

    monkeypatch.setattr("lap.cli.main._metadata_path", fake_metadata_path)
    monkeypatch.setattr("lap.cli.auth.get_registry_url", lambda: "https://registry.lap.sh")

    update_result = {"results": [
        {"name": "stripe", "has_update": True, "installed_version": "1.0.0", "latest_version": "2.0.0"}
    ]}
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(update_result).encode("utf-8")
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = lambda s, *a: None

    with patch("urllib.request.urlopen", return_value=mock_resp):
        args = SimpleNamespace(silent_if_clean=False, json=True, target="auto")
        cmd_check(args)

    captured = capsys.readouterr()
    parsed = json.loads(captured.out)
    assert "updates" in parsed
    assert parsed["updates"][0]["name"] == "stripe"


# ── C12: lap check network failure silent skip ────────────────────────


def test_check_network_failure_silent(tmp_path, monkeypatch, capsys):
    meta_file = tmp_path / "lap-metadata.json"
    data = {"skills": {"stripe": {"registryVersion": "1.0.0", "pinned": False}}}
    meta_file.write_text(json.dumps(data), encoding="utf-8")

    def fake_metadata_path(t):
        if t == "claude":
            return meta_file
        return tmp_path / "no-exist.json"

    monkeypatch.setattr("lap.cli.main._metadata_path", fake_metadata_path)
    monkeypatch.setattr("lap.cli.auth.get_registry_url", lambda: "https://registry.lap.sh")

    with patch("urllib.request.urlopen", side_effect=OSError("network error")):
        args = SimpleNamespace(silent_if_clean=True, json=False, target="auto")
        cmd_check(args)

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_check_network_failure_warns(tmp_path, monkeypatch, capsys):
    meta_file = tmp_path / "lap-metadata.json"
    data = {"skills": {"stripe": {"registryVersion": "1.0.0", "pinned": False}}}
    meta_file.write_text(json.dumps(data), encoding="utf-8")

    def fake_metadata_path(t):
        if t == "claude":
            return meta_file
        return tmp_path / "no-exist.json"

    monkeypatch.setattr("lap.cli.main._metadata_path", fake_metadata_path)
    monkeypatch.setattr("lap.cli.auth.get_registry_url", lambda: "https://registry.lap.sh")

    with patch("urllib.request.urlopen", side_effect=OSError("network error")):
        args = SimpleNamespace(silent_if_clean=False, json=False, target="auto")
        cmd_check(args)

    captured = capsys.readouterr()
    assert "Warning" in captured.err


# ── C14: lap check scans both platforms ──────────────────────────────


def test_check_scans_both_platforms(tmp_path, monkeypatch):
    claude_file = tmp_path / "claude-meta.json"
    cursor_file = tmp_path / "cursor-meta.json"
    claude_data = {"skills": {"stripe": {"registryVersion": "1.0.0", "pinned": False}}}
    cursor_data = {"skills": {"github": {"registryVersion": "2.0.0", "pinned": False}}}
    claude_file.write_text(json.dumps(claude_data), encoding="utf-8")
    cursor_file.write_text(json.dumps(cursor_data), encoding="utf-8")

    def fake_metadata_path(t):
        if t == "claude":
            return claude_file
        return cursor_file

    monkeypatch.setattr("lap.cli.main._metadata_path", fake_metadata_path)
    monkeypatch.setattr("lap.cli.auth.get_registry_url", lambda: "https://registry.lap.sh")

    captured_payload = {}

    def fake_urlopen(req, timeout=None):
        import urllib.request
        body = json.loads(req.data.decode("utf-8"))
        captured_payload["skills"] = body["skills"]
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"results": []}).encode("utf-8")
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = lambda s, *a: None
        return mock_resp

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        args = SimpleNamespace(silent_if_clean=True, json=False, target="auto")
        cmd_check(args)

    names_checked = {s["name"] for s in captured_payload.get("skills", [])}
    assert "stripe" in names_checked
    assert "github" in names_checked


# ── C15: lap pin sets pinned: true ───────────────────────────────────


def test_pin_sets_pinned_true(tmp_path, monkeypatch):
    meta_file = tmp_path / "lap-metadata.json"
    data = {"skills": {"stripe": {"registryVersion": "1.0.0", "pinned": False}}}
    meta_file.write_text(json.dumps(data), encoding="utf-8")

    monkeypatch.setattr("lap.cli.main._metadata_path", lambda t: meta_file)
    monkeypatch.setattr("lap.cli.main._write_metadata", lambda t, d: meta_file.write_text(json.dumps(d, indent=2), encoding="utf-8"))

    args = SimpleNamespace(name="stripe", target="claude")
    cmd_pin(args)

    written = json.loads(meta_file.read_text(encoding="utf-8"))
    assert written["skills"]["stripe"]["pinned"] is True


# ── C16: lap unpin sets pinned: false ────────────────────────────────


def test_unpin_sets_pinned_false(tmp_path, monkeypatch):
    meta_file = tmp_path / "lap-metadata.json"
    data = {"skills": {"stripe": {"registryVersion": "1.0.0", "pinned": True}}}
    meta_file.write_text(json.dumps(data), encoding="utf-8")

    monkeypatch.setattr("lap.cli.main._metadata_path", lambda t: meta_file)
    monkeypatch.setattr("lap.cli.main._write_metadata", lambda t, d: meta_file.write_text(json.dumps(d, indent=2), encoding="utf-8"))

    args = SimpleNamespace(name="stripe", target="claude")
    cmd_unpin(args)

    written = json.loads(meta_file.read_text(encoding="utf-8"))
    assert written["skills"]["stripe"]["pinned"] is False


# ── C17: lap pin unknown raises error ────────────────────────────────


def test_pin_unknown_skill_errors(tmp_path, monkeypatch):
    meta_file = tmp_path / "lap-metadata.json"
    data = {"skills": {}}
    meta_file.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr("lap.cli.main._metadata_path", lambda t: meta_file)

    args = SimpleNamespace(name="nonexistent", target="claude")
    with pytest.raises(SystemExit):
        cmd_pin(args)


def test_unpin_unknown_skill_errors(tmp_path, monkeypatch):
    meta_file = tmp_path / "lap-metadata.json"
    data = {"skills": {}}
    meta_file.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr("lap.cli.main._metadata_path", lambda t: meta_file)

    args = SimpleNamespace(name="nonexistent", target="claude")
    with pytest.raises(SystemExit):
        cmd_unpin(args)


# ── C18: lap check skips pinned ──────────────────────────────────────


def test_check_skips_pinned(tmp_path, monkeypatch):
    meta_file = tmp_path / "lap-metadata.json"
    data = {"skills": {"stripe": {"registryVersion": "1.0.0", "pinned": True}}}
    meta_file.write_text(json.dumps(data), encoding="utf-8")

    def fake_metadata_path(t):
        if t == "claude":
            return meta_file
        return tmp_path / "no-exist.json"

    monkeypatch.setattr("lap.cli.main._metadata_path", fake_metadata_path)
    monkeypatch.setattr("lap.cli.auth.get_registry_url", lambda: "https://registry.lap.sh")

    urlopen_called = []

    def fake_urlopen(req, timeout=None):
        urlopen_called.append(True)
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"results": []}).encode("utf-8")
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = lambda s, *a: None
        return mock_resp

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        args = SimpleNamespace(silent_if_clean=True, json=False, target="auto")
        cmd_check(args)

    # No network call should be made since the only skill is pinned
    assert not urlopen_called


# ── C24: Path traversal name rejected ────────────────────────────────


def test_is_valid_skill_name_safe():
    assert _is_valid_skill_name("stripe") is True
    assert _is_valid_skill_name("my-api.v2") is True
    assert _is_valid_skill_name("MY_API_123") is True


def test_is_valid_skill_name_rejects_traversal():
    assert _is_valid_skill_name("../../etc/passwd") is False
    assert _is_valid_skill_name("../secret") is False
    assert _is_valid_skill_name("bad/name") is False
    assert _is_valid_skill_name("name with spaces") is False
    assert _is_valid_skill_name("name!@#") is False
    assert _is_valid_skill_name(".hidden") is False
    assert _is_valid_skill_name("..") is False
    assert _is_valid_skill_name("") is False
    assert _is_valid_skill_name("-dash-start") is False
    assert _is_valid_skill_name("_under_start") is False


# ── C25: HTTPS-only registry URL ─────────────────────────────────────


def test_validate_registry_url_https_allowed():
    url = _validate_registry_url("https://registry.lap.sh")
    assert url == "https://registry.lap.sh"


def test_validate_registry_url_localhost_allowed():
    url = _validate_registry_url("http://localhost:8787")
    assert url == "http://localhost:8787"


def test_validate_registry_url_127_allowed():
    url = _validate_registry_url("http://127.0.0.1:8080")
    assert url == "http://127.0.0.1:8080"


def test_validate_registry_url_http_rejected():
    with pytest.raises(ValueError, match="HTTPS"):
        _validate_registry_url("http://evil.com")


def test_validate_registry_url_rejects_localhost_prefix_confusion():
    """http://localhost.evil.com must NOT be treated as localhost."""
    with pytest.raises(ValueError, match="HTTPS"):
        _validate_registry_url("http://localhost.evil.com")
    with pytest.raises(ValueError, match="HTTPS"):
        _validate_registry_url("http://localhost-attacker.com")


# ── C7: skill-install writes metadata ────────────────────────────────


def test_skill_install_writes_metadata(tmp_path, monkeypatch):
    """After install, metadata entry is created for the skill."""
    meta_file = tmp_path / "lap-metadata.json"
    monkeypatch.setattr("lap.cli.main._metadata_path", lambda t: meta_file)
    monkeypatch.setattr("lap.cli.auth.get_registry_url", lambda: "https://registry.lap.sh")

    # Mock LAP spec fetch (text/lap)
    spec_text = "API: stripe\nVersion: 2.0.0\nBase: https://api.stripe.com\n"

    # Mock the skill generation and file writing
    fake_skill = MagicMock()
    fake_skill.file_map = {"SKILL.md": "# stripe skill"}
    fake_skill.name = "stripe"
    fake_skill.token_count = 500

    # Two urlopen calls: first for the spec (text/lap), second for JSON version
    lap_resp = MagicMock()
    lap_resp.read.return_value = spec_text.encode("utf-8")
    lap_resp.__enter__ = lambda s: s
    lap_resp.__exit__ = lambda s, *a: None

    json_resp = MagicMock()
    json_resp.read.return_value = json.dumps({"version": "2.0.0"}).encode("utf-8")
    json_resp.__enter__ = lambda s: s
    json_resp.__exit__ = lambda s, *a: None

    call_count = [0]

    def fake_urlopen(req, timeout=None):
        call_count[0] += 1
        if call_count[0] == 1:
            return lap_resp
        return json_resp

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        with patch("lap.core.parser.parse_lap", return_value=MagicMock()):
            with patch("lap.core.compilers.skill.generate_skill", return_value=fake_skill):
                with patch("lap.core.compilers.skill.detect_target", return_value="claude"):
                    args = SimpleNamespace(name="stripe", target="claude", dir=str(tmp_path / "install"))
                    cmd_skill_install(args)

    assert meta_file.exists()
    meta = json.loads(meta_file.read_text(encoding="utf-8"))
    assert "stripe" in meta["skills"]
    entry = meta["skills"]["stripe"]
    assert entry["registryVersion"] == "2.0.0"
    assert entry["pinned"] is False
    assert "specHash" in entry
    assert "installedAt" in entry


# ── C8: skill-install updates existing entry ─────────────────────────


def test_skill_install_updates_existing_entry(tmp_path, monkeypatch):
    """Reinstalling overwrites the metadata entry without duplication."""
    meta_file = tmp_path / "lap-metadata.json"
    existing = {"skills": {"stripe": {"registryVersion": "1.0.0", "pinned": True}}}
    meta_file.write_text(json.dumps(existing), encoding="utf-8")

    monkeypatch.setattr("lap.cli.main._metadata_path", lambda t: meta_file)
    monkeypatch.setattr("lap.cli.auth.get_registry_url", lambda: "https://registry.lap.sh")

    spec_text = "API: stripe\nVersion: 3.0.0\nBase: https://api.stripe.com\n"

    fake_skill = MagicMock()
    fake_skill.file_map = {"SKILL.md": "# stripe skill"}
    fake_skill.name = "stripe"
    fake_skill.token_count = 500

    lap_resp = MagicMock()
    lap_resp.read.return_value = spec_text.encode("utf-8")
    lap_resp.__enter__ = lambda s: s
    lap_resp.__exit__ = lambda s, *a: None

    json_resp = MagicMock()
    json_resp.read.return_value = json.dumps({"version": "3.0.0"}).encode("utf-8")
    json_resp.__enter__ = lambda s: s
    json_resp.__exit__ = lambda s, *a: None

    call_count = [0]

    def fake_urlopen(req, timeout=None):
        call_count[0] += 1
        if call_count[0] == 1:
            return lap_resp
        return json_resp

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        with patch("lap.core.parser.parse_lap", return_value=MagicMock()):
            with patch("lap.core.compilers.skill.generate_skill", return_value=fake_skill):
                with patch("lap.core.compilers.skill.detect_target", return_value="claude"):
                    args = SimpleNamespace(name="stripe", target="claude", dir=str(tmp_path / "install"))
                    cmd_skill_install(args)

    meta = json.loads(meta_file.read_text(encoding="utf-8"))
    # Only one entry for stripe
    assert list(meta["skills"].keys()) == ["stripe"]
    # Version updated, pinned reset to False
    assert meta["skills"]["stripe"]["registryVersion"] == "3.0.0"
    assert meta["skills"]["stripe"]["pinned"] is False


# ── C19: `lap diff stripe` single arg detection ───────────────────────


def test_diff_single_arg_calls_diff_skill(monkeypatch):
    """Single non-file argument is treated as a skill name for skill diff."""
    called_with = {}

    def fake_diff_skill(name, args):
        called_with["name"] = name

    monkeypatch.setattr("lap.cli.main._diff_skill", fake_diff_skill)

    args = SimpleNamespace(old="stripe", new=None, format="summary", version=None)
    cmd_diff(args)

    assert called_with.get("name") == "stripe"


def test_diff_single_arg_with_lap_extension_errors():
    """.lap extension in single arg triggers error (needs two files)."""
    args = SimpleNamespace(old="spec.lap", new=None, format="summary", version=None)
    with pytest.raises(SystemExit):
        cmd_diff(args)


def test_diff_single_arg_with_slash_errors():
    """Path with slash in single arg triggers error (needs two files)."""
    args = SimpleNamespace(old="some/path", new=None, format="summary", version=None)
    with pytest.raises(SystemExit):
        cmd_diff(args)


# ── C20: `lap diff old.lap new.lap` existing behavior preserved ───────


def test_diff_two_files_preserved(tmp_path):
    """Two-file diff uses existing file-based diff behavior."""
    lap_content = (
        "API: TestAPI\nVersion: 1.0\nBase: https://api.example.com\n\n"
        "GET /ping\n"
    )
    old_file = tmp_path / "old.lap"
    new_file = tmp_path / "new.lap"
    old_file.write_text(lap_content, encoding="utf-8")
    new_file.write_text(lap_content, encoding="utf-8")

    args = SimpleNamespace(
        old=str(old_file),
        new=str(new_file),
        format="summary",
        version=None,
    )
    # Should run without error and not call _diff_skill
    cmd_diff(args)


def test_diff_two_files_missing_old_errors(tmp_path):
    """Missing old file triggers error."""
    new_file = tmp_path / "new.lap"
    new_file.write_text("API: X\n", encoding="utf-8")

    args = SimpleNamespace(
        old=str(tmp_path / "missing.lap"),
        new=str(new_file),
        format="summary",
        version=None,
    )
    with pytest.raises(SystemExit):
        cmd_diff(args)


# ── C21-C23: Hook registration ──────────────────────────────────────


def _find_lap_hook(entries):
    """Helper: find the LAP hook command in new-format hook entries."""
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        for h in entry.get("hooks", []):
            if isinstance(h, dict) and "lapsh check" in h.get("command", ""):
                return h
    return None


def test_register_claude_hook(tmp_path):
    """C21: init registers SessionStart hook in .claude/settings.json."""
    config_path = tmp_path / "settings.json"
    _register_claude_hook(config_path, "npx @lap-platform/lapsh check --silent-if-clean")

    config = json.loads(config_path.read_text(encoding="utf-8"))
    assert "hooks" in config
    assert "SessionStart" in config["hooks"]
    entries = config["hooks"]["SessionStart"]
    assert len(entries) == 1
    assert entries[0]["matcher"] == ""
    hook = _find_lap_hook(entries)
    assert hook is not None, "LAP hook not found"
    assert hook["type"] == "command"
    assert "lapsh check" in hook["command"]


def test_register_claude_hook_idempotent(tmp_path):
    """C22: Running init twice does not duplicate the hook."""
    config_path = tmp_path / "settings.json"
    _register_claude_hook(config_path, "npx @lap-platform/lapsh check --silent-if-clean")
    _register_claude_hook(config_path, "npx @lap-platform/lapsh check --silent-if-clean")

    config = json.loads(config_path.read_text(encoding="utf-8"))
    entries = config["hooks"]["SessionStart"]
    assert len(entries) == 1, "Hook should not be duplicated"


def test_register_claude_hook_preserves_existing(tmp_path):
    """C23: Existing hooks are not overwritten or removed."""
    config_path = tmp_path / "settings.json"
    existing = {
        "hooks": {
            "SessionStart": [
                {"matcher": "Bash", "hooks": [{"type": "command", "command": "echo hello"}]},
            ],
            "PreToolUse": [
                {"matcher": "Edit|Write", "hooks": [{"type": "command", "command": "lint-check"}]},
            ],
        },
        "customSetting": True,
    }
    config_path.write_text(json.dumps(existing), encoding="utf-8")

    _register_claude_hook(config_path, "npx @lap-platform/lapsh check --silent-if-clean")

    config = json.loads(config_path.read_text(encoding="utf-8"))
    # Original SessionStart hook preserved
    assert config["hooks"]["SessionStart"][0]["matcher"] == "Bash"
    assert config["hooks"]["SessionStart"][0]["hooks"][0]["command"] == "echo hello"
    # LAP hook appended
    assert len(config["hooks"]["SessionStart"]) == 2
    lap = _find_lap_hook(config["hooks"]["SessionStart"])
    assert lap is not None
    # Other hook arrays untouched
    assert len(config["hooks"]["PreToolUse"]) == 1
    assert config["hooks"]["PreToolUse"][0]["hooks"][0]["command"] == "lint-check"
    # Non-hook settings untouched
    assert config["customSetting"] is True


def test_register_cursor_hook(tmp_path):
    """C21 (Cursor): init registers sessionStart hook in .cursor/hooks.json."""
    config_path = tmp_path / "hooks.json"
    _register_cursor_hook(config_path, "npx @lap-platform/lapsh check --silent-if-clean --hook")

    config = json.loads(config_path.read_text(encoding="utf-8"))
    assert config["version"] == 1
    assert "hooks" in config
    assert "sessionStart" in config["hooks"]
    entries = config["hooks"]["sessionStart"]
    assert len(entries) == 1
    # Cursor uses flat format: command + type + timeout at top level
    assert entries[0]["type"] == "command"
    assert "lapsh check" in entries[0]["command"]
    assert entries[0]["timeout"] == 30


def test_register_cursor_hook_idempotent(tmp_path):
    """C22 (Cursor): Running init twice does not duplicate the hook."""
    config_path = tmp_path / "hooks.json"
    _register_cursor_hook(config_path, "npx @lap-platform/lapsh check --silent-if-clean --hook")
    _register_cursor_hook(config_path, "npx @lap-platform/lapsh check --silent-if-clean --hook")

    config = json.loads(config_path.read_text(encoding="utf-8"))
    entries = config["hooks"]["sessionStart"]
    assert len(entries) == 1, "Hook should not be duplicated"


def test_register_cursor_hook_preserves_existing(tmp_path):
    """C23 (Cursor): Existing hooks are not overwritten or removed."""
    config_path = tmp_path / "hooks.json"
    existing = {
        "version": 1,
        "hooks": {
            "sessionStart": [
                {"command": "echo cursor-hello", "type": "command", "timeout": 5},
            ],
        },
        "otherKey": 42,
    }
    config_path.write_text(json.dumps(existing), encoding="utf-8")

    _register_cursor_hook(config_path, "npx @lap-platform/lapsh check --silent-if-clean --hook")

    config = json.loads(config_path.read_text(encoding="utf-8"))
    # Original hook preserved
    assert config["hooks"]["sessionStart"][0]["command"] == "echo cursor-hello"
    # LAP hook appended
    assert len(config["hooks"]["sessionStart"]) == 2
    assert "lapsh check" in config["hooks"]["sessionStart"][1]["command"]
    # Other keys untouched
    assert config["otherKey"] == 42


def test_register_claude_hook_corrupt_config(tmp_path):
    """Hook registration handles corrupt/empty settings file gracefully."""
    config_path = tmp_path / "settings.json"
    config_path.write_text("not valid json", encoding="utf-8")

    _register_claude_hook(config_path, "npx @lap-platform/lapsh check --silent-if-clean")

    config = json.loads(config_path.read_text(encoding="utf-8"))
    assert len(config["hooks"]["SessionStart"]) == 1
    assert _find_lap_hook(config["hooks"]["SessionStart"]) is not None


def test_register_claude_hook_creates_missing_file(tmp_path):
    """Hook registration creates settings.json if it doesn't exist."""
    config_path = tmp_path / "subdir" / "settings.json"
    assert not config_path.exists()

    _register_claude_hook(config_path, "npx @lap-platform/lapsh check --silent-if-clean")

    assert config_path.exists()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    assert len(config["hooks"]["SessionStart"]) == 1
    assert _find_lap_hook(config["hooks"]["SessionStart"]) is not None


