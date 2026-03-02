"""Tests for cli/auth.py -- credential management and SSE parsing."""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lap.cli import auth


# ── Credential management ────────────────────────────────────────────


class TestCredentials:
    """Test save/load/clear/get_token for ~/.lap/credentials.json."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.creds_dir = Path(self.tmpdir) / ".lap"
        self.creds_file = self.creds_dir / "credentials.json"
        # Patch module-level paths
        self._dir_patch = patch.object(auth, "CREDENTIALS_DIR", self.creds_dir)
        self._file_patch = patch.object(auth, "CREDENTIALS_FILE", self.creds_file)
        self._dir_patch.start()
        self._file_patch.start()

    def teardown_method(self):
        self._dir_patch.stop()
        self._file_patch.stop()
        # Clean up
        if self.creds_file.exists():
            self.creds_file.unlink()
        if self.creds_dir.exists():
            self.creds_dir.rmdir()
        os.rmdir(self.tmpdir)

    def test_load_no_file(self):
        assert auth.load_credentials() is None

    def test_save_and_load(self):
        auth.save_credentials("lap_abc123", "testuser")
        creds = auth.load_credentials()
        assert creds is not None
        assert creds["token"] == "lap_abc123"
        assert creds["username"] == "testuser"

    def test_save_creates_directory(self):
        assert not self.creds_dir.exists()
        auth.save_credentials("tok", "usr")
        assert self.creds_dir.exists()
        assert self.creds_file.exists()

    def test_clear_removes_file(self):
        auth.save_credentials("tok", "usr")
        assert self.creds_file.exists()
        auth.clear_credentials()
        assert not self.creds_file.exists()

    def test_clear_no_file_no_error(self):
        auth.clear_credentials()  # Should not raise

    def test_get_token_with_creds(self):
        auth.save_credentials("lap_mytoken", "user1")
        assert auth.get_token() == "lap_mytoken"

    def test_get_token_without_creds(self):
        assert auth.get_token() is None

    def test_load_corrupt_json(self):
        self.creds_dir.mkdir(parents=True, exist_ok=True)
        self.creds_file.write_text("not valid json{{{")
        assert auth.load_credentials() is None

    def test_save_overwrites(self):
        auth.save_credentials("tok1", "usr1")
        auth.save_credentials("tok2", "usr2")
        creds = auth.load_credentials()
        assert creds["token"] == "tok2"
        assert creds["username"] == "usr2"

    @pytest.mark.skipif(sys.platform == "win32", reason="chmod not enforced on Windows")
    def test_file_permissions(self):
        auth.save_credentials("tok", "usr")
        mode = oct(os.stat(self.creds_file).st_mode & 0o777)
        assert mode == "0o600"


# ── Registry URL ─────────────────────────────────────────────────────


class TestRegistryUrl:
    def test_default(self):
        with patch.dict(os.environ, {}, clear=True):
            # Remove LAP_REGISTRY if set
            os.environ.pop("LAP_REGISTRY", None)
            url = auth.get_registry_url()
            assert url == "https://registry.lap.sh"

    def test_env_override(self):
        with patch.dict(os.environ, {"LAP_REGISTRY": "http://localhost:8787/"}):
            url = auth.get_registry_url()
            assert url == "http://localhost:8787"
            assert not url.endswith("/")  # Trailing slash stripped


# ── SSE parsing ──────────────────────────────────────────────────────


class TestSseParsing:
    """Test SSE stream parsing logic (mocked HTTP)."""

    def _make_stream(self, lines):
        """Create a mock HTTP response that yields lines."""
        mock_resp = MagicMock()
        mock_resp.__iter__ = lambda self: iter(lines)
        mock_resp.__enter__ = lambda self: self
        mock_resp.__exit__ = lambda self, *a: None
        return mock_resp

    def test_success(self):
        lines = [
            b'data: {"status":"waiting"}\n',
            b'\n',
            b'data: {"token":"lap_abc","username":"octocat"}\n',
            b'\n',
        ]
        mock_resp = self._make_stream(lines)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            token, username = auth.poll_sse_stream("test-session")
            assert token == "lap_abc"
            assert username == "octocat"

    def test_error_response(self):
        lines = [
            b'data: {"status":"waiting"}\n',
            b'data: {"error":"Session expired or not found"}\n',
        ]
        mock_resp = self._make_stream(lines)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            with pytest.raises(SystemExit, match="Session expired"):
                auth.poll_sse_stream("bad-session")

    def test_timeout(self):
        lines = [
            b'data: {"status":"waiting"}\n',
            b'data: {"status":"waiting"}\n',
            # Stream ends without token
        ]
        mock_resp = self._make_stream(lines)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            with pytest.raises(SystemExit, match="timed out"):
                auth.poll_sse_stream("timeout-session")

    def test_ignores_non_data_lines(self):
        lines = [
            b': keepalive\n',
            b'event: message\n',
            b'data: {"token":"lap_xyz","username":"user1"}\n',
        ]
        mock_resp = self._make_stream(lines)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            token, username = auth.poll_sse_stream("s1")
            assert token == "lap_xyz"

    def test_ignores_invalid_json(self):
        lines = [
            b'data: not-json\n',
            b'data: {"token":"lap_ok","username":"u"}\n',
        ]
        mock_resp = self._make_stream(lines)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            token, _ = auth.poll_sse_stream("s2")
            assert token == "lap_ok"


# ── api_request ──────────────────────────────────────────────────────


class TestApiRequest:
    def test_get_success(self):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"user":{"username":"me"}}'
        mock_resp.__enter__ = lambda self: self
        mock_resp.__exit__ = lambda self, *a: None

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = auth.api_request("GET", "/auth/me", token="lap_tok")
            assert result["user"]["username"] == "me"

    def test_http_error(self):
        import urllib.error
        err = urllib.error.HTTPError(
            "http://x", 401, "Unauthorized", {},
            MagicMock(read=lambda: b'{"error":"Invalid token"}')
        )
        err.fp = True
        with patch("urllib.request.urlopen", side_effect=err):
            with pytest.raises(SystemExit, match="Invalid token"):
                auth.api_request("GET", "/auth/me", token="bad")
