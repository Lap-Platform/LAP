"""Tests for search-related helpers and cmd_search in lap/cli/main.py."""

import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lap.cli.main import _sanitize, _validate_search_response, _format_search_results, cmd_search, cmd_get


# ── _sanitize ────────────────────────────────────────────────────────


class TestSanitize:
    def test_plain_string_unchanged(self):
        assert _sanitize("hello world") == "hello world"

    def test_strips_ansi_color_codes(self):
        assert _sanitize("\x1b[31mred\x1b[0m") == "red"

    def test_strips_ansi_cursor_move(self):
        assert _sanitize("\x1b[2Jhello") == "hello"

    def test_strips_ansi_bold(self):
        assert _sanitize("\x1b[1mbold\x1b[0m") == "bold"

    def test_strips_control_chars(self):
        assert _sanitize("\x00\x07text\x1f") == "text"

    def test_strips_null_byte(self):
        assert _sanitize("a\x00b") == "ab"

    def test_strips_bell_char(self):
        assert _sanitize("ring\x07bell") == "ringbell"

    def test_strips_delete_char(self):
        assert _sanitize("del\x7fete") == "delete"

    def test_preserves_tab(self):
        assert _sanitize("a\tb") == "a\tb"

    def test_preserves_newline(self):
        assert _sanitize("a\nb") == "a\nb"

    def test_preserves_tabs_and_newlines(self):
        assert _sanitize("a\tb\nc") == "a\tb\nc"

    def test_empty_string(self):
        assert _sanitize("") == ""

    def test_combined_ansi_and_control(self):
        assert _sanitize("\x1b[1m\x07evil\x1b[0m") == "evil"

    def test_only_ansi_sequences(self):
        assert _sanitize("\x1b[0m\x1b[32m") == ""

    def test_unicode_preserved(self):
        assert _sanitize("caf\u00e9") == "caf\u00e9"

    def test_numbers_preserved(self):
        assert _sanitize("abc123") == "abc123"

    def test_ansi_with_semicolons(self):
        # Multi-param ANSI like \x1b[0;32m
        assert _sanitize("\x1b[0;32mgreen\x1b[0m") == "green"


# ── _validate_search_response ─────────────────────────────────────────


class TestValidateSearchResponse:
    def test_valid_response(self):
        result = {"results": [{"name": "x"}], "total": 1, "offset": 0}
        _validate_search_response(result)  # should not raise

    def test_valid_empty_results(self):
        result = {"results": [], "total": 0, "offset": 0}
        _validate_search_response(result)  # should not raise

    def test_non_dict_raises(self):
        with pytest.raises(SystemExit):
            _validate_search_response("string")

    def test_integer_input_raises(self):
        with pytest.raises(SystemExit):
            _validate_search_response(42)

    def test_list_input_raises(self):
        with pytest.raises(SystemExit):
            _validate_search_response([1, 2])

    def test_none_input_raises(self):
        with pytest.raises(SystemExit):
            _validate_search_response(None)

    def test_results_not_list_raises(self):
        with pytest.raises(SystemExit):
            _validate_search_response({"results": "bad"})

    def test_results_is_dict_raises(self):
        with pytest.raises(SystemExit):
            _validate_search_response({"results": {"name": "x"}})

    def test_result_entry_not_dict_raises(self):
        with pytest.raises(SystemExit):
            _validate_search_response({"results": ["x"]})

    def test_result_entry_integer_raises(self):
        with pytest.raises(SystemExit):
            _validate_search_response({"results": [1, 2]})

    def test_fixes_non_int_total(self):
        result = {"results": [{"a": 1}], "total": "5"}
        _validate_search_response(result)
        # total is replaced with len(results) when non-int
        assert result["total"] == 1

    def test_fixes_non_int_total_none(self):
        result = {"results": [{"a": 1}, {"b": 2}], "total": None}
        _validate_search_response(result)
        assert result["total"] == 2

    def test_fixes_non_int_offset(self):
        result = {"results": [], "total": 0, "offset": "bad"}
        _validate_search_response(result)
        assert result["offset"] == 0

    def test_fixes_non_int_offset_none(self):
        result = {"results": [], "total": 0, "offset": None}
        _validate_search_response(result)
        assert result["offset"] == 0

    def test_missing_total_offset_ok(self):
        result = {"results": []}
        _validate_search_response(result)  # should not raise

    def test_valid_int_total_preserved(self):
        result = {"results": [], "total": 99, "offset": 10}
        _validate_search_response(result)
        assert result["total"] == 99
        assert result["offset"] == 10

    def test_multiple_valid_entries(self):
        result = {
            "results": [{"name": "a"}, {"name": "b"}, {"name": "c"}],
            "total": 3,
            "offset": 0,
        }
        _validate_search_response(result)  # should not raise


# ── _format_search_results ───────────────────────────────────────────


class TestFormatSearchResults:
    def _make_result(self, **overrides):
        base = {
            "name": "stripe",
            "description": "Payment processing",
            "endpoints": 42,
            "size": 1000,
            "lean_size": 250,
            "has_skill": True,
            "provider": {"slug": "stripe", "display_name": "Stripe", "domain": "stripe.com"},
        }
        base.update(overrides)
        return base

    def test_basic_output(self, capsys):
        results = [self._make_result()]
        _format_search_results(results, total=1, offset=0)
        out = capsys.readouterr().out
        assert "stripe" in out
        assert "stripe.com" in out
        assert "42 endpoints" in out
        assert "4.0x compressed" in out
        assert "Payment processing" in out
        assert "[skill]" in out

    def test_provider_domain_shown(self, capsys):
        results = [self._make_result(provider={"slug": "twilio", "display_name": "Twilio", "domain": "twilio.com"})]
        _format_search_results(results, total=1, offset=0)
        out = capsys.readouterr().out
        assert "twilio.com" in out

    def test_provider_fallback_to_display_name(self, capsys):
        results = [self._make_result(provider={"slug": "x", "display_name": "MyAPI", "domain": ""})]
        _format_search_results(results, total=1, offset=0)
        out = capsys.readouterr().out
        assert "MyAPI" in out

    def test_provider_missing_graceful(self, capsys):
        results = [self._make_result(provider=None)]
        _format_search_results(results, total=1, offset=0)
        out = capsys.readouterr().out
        assert "stripe" in out  # name still shows

    def test_no_skill_marker(self, capsys):
        results = [self._make_result(has_skill=False)]
        _format_search_results(results, total=1, offset=0)
        out = capsys.readouterr().out
        assert "[skill]" not in out

    def test_skill_marker_present(self, capsys):
        results = [self._make_result(has_skill=True)]
        _format_search_results(results, total=1, offset=0)
        out = capsys.readouterr().out
        assert "[skill]" in out

    def test_pagination_hint(self, capsys):
        results = [self._make_result(name=f"api{i}") for i in range(5)]
        _format_search_results(results, total=20, offset=0)
        out = capsys.readouterr().out
        assert "Showing 5/20" in out
        assert "--offset 5" in out

    def test_pagination_with_nonzero_offset(self, capsys):
        results = [self._make_result(name=f"api{i}") for i in range(5)]
        _format_search_results(results, total=20, offset=5)
        out = capsys.readouterr().out
        # shown = offset(5) + len(results)(5) = 10
        assert "Showing 10/20" in out
        assert "--offset 10" in out

    def test_no_pagination_when_all_shown(self, capsys):
        results = [self._make_result()]
        _format_search_results(results, total=1, offset=0)
        out = capsys.readouterr().out
        assert "Showing" not in out

    def test_no_pagination_when_shown_equals_total(self, capsys):
        results = [self._make_result(name=f"api{i}") for i in range(3)]
        _format_search_results(results, total=3, offset=0)
        out = capsys.readouterr().out
        assert "Showing" not in out

    def test_sanitizes_server_strings(self, capsys):
        results = [self._make_result(name="\x1b[31mevil\x1b[0m")]
        _format_search_results(results, total=1, offset=0)
        out = capsys.readouterr().out
        assert "evil" in out
        assert "\x1b" not in out

    def test_sanitizes_description(self, capsys):
        results = [self._make_result(description="\x07injected\x1b[32m")]
        _format_search_results(results, total=1, offset=0)
        out = capsys.readouterr().out
        assert "injected" in out
        assert "\x1b" not in out
        assert "\x07" not in out

    def test_missing_optional_fields(self, capsys):
        results = [{"name": "basic", "description": "Just a name"}]
        _format_search_results(results, total=1, offset=0)
        out = capsys.readouterr().out
        assert "basic" in out
        assert "Just a name" in out

    def test_no_ratio_when_lean_size_zero(self, capsys):
        results = [self._make_result(size=1000, lean_size=0)]
        _format_search_results(results, total=1, offset=0)
        out = capsys.readouterr().out
        assert "compressed" not in out

    def test_no_ratio_when_lean_size_missing(self, capsys):
        results = [{"name": "api", "description": "desc", "size": 1000}]
        _format_search_results(results, total=1, offset=0)
        out = capsys.readouterr().out
        assert "compressed" not in out

    def test_no_endpoints_when_missing(self, capsys):
        results = [{"name": "api", "description": "desc"}]
        _format_search_results(results, total=1, offset=0)
        out = capsys.readouterr().out
        assert "endpoints" not in out

    def test_multiple_results_all_shown(self, capsys):
        results = [
            self._make_result(name="stripe", endpoints=587),
            self._make_result(name="twilio", endpoints=120, has_skill=False),
        ]
        _format_search_results(results, total=2, offset=0)
        out = capsys.readouterr().out
        assert "stripe" in out
        assert "twilio" in out
        assert "587 endpoints" in out
        assert "120 endpoints" in out


# ── cmd_search helpers ────────────────────────────────────────────────


def _make_args(**overrides):
    args = MagicMock()
    args.query = ["stripe"]
    args.tag = None
    args.sort = None
    args.limit = None
    args.offset = None
    args.json = False
    for k, v in overrides.items():
        setattr(args, k, v)
    return args


MOCK_RESPONSE = {
    "results": [
        {
            "name": "Stripe",
            "description": "Payment processing",
            "endpoints": 587,
            "size": 5000,
            "lean_size": 1300,
            "has_skill": True,
        }
    ],
    "total": 1,
    "offset": 0,
}


# ── cmd_search ────────────────────────────────────────────────────────


class TestCmdSearch:
    def test_basic_search(self, capsys):
        with patch("lap.cli.auth.api_request", return_value=MOCK_RESPONSE):
            cmd_search(_make_args())
        out = capsys.readouterr().out
        assert "Stripe" in out

    def test_empty_query_exits(self):
        with pytest.raises(SystemExit):
            cmd_search(_make_args(query=["  "]))

    def test_all_whitespace_query_exits(self):
        with pytest.raises(SystemExit):
            cmd_search(_make_args(query=["   ", "  "]))

    def test_json_output(self, capsys):
        with patch("lap.cli.auth.api_request", return_value=MOCK_RESPONSE):
            cmd_search(_make_args(json=True))
        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert "results" in parsed
        assert parsed["results"][0]["name"] == "Stripe"

    def test_json_output_is_valid_json(self, capsys):
        with patch("lap.cli.auth.api_request", return_value=MOCK_RESPONSE):
            cmd_search(_make_args(json=True))
        out = capsys.readouterr().out
        # Should not raise
        json.loads(out)

    def test_no_results_message(self, capsys):
        empty = {"results": [], "total": 0, "offset": 0}
        with patch("lap.cli.auth.api_request", return_value=empty):
            cmd_search(_make_args(query=["nonexistent"]))
        out = capsys.readouterr().out
        assert "No results" in out

    def test_no_results_includes_query(self, capsys):
        empty = {"results": [], "total": 0, "offset": 0}
        with patch("lap.cli.auth.api_request", return_value=empty):
            cmd_search(_make_args(query=["xyznonexistent"]))
        out = capsys.readouterr().out
        assert "xyznonexistent" in out

    def test_query_params_forwarded(self):
        empty = {"results": [], "total": 0, "offset": 0}
        with patch("lap.cli.auth.api_request", return_value=empty) as mock_req:
            cmd_search(_make_args(tag="payment", sort="popularity", limit=5, offset=10))
        call_url = mock_req.call_args[0][1]
        assert "tag=payment" in call_url
        assert "sort=popularity" in call_url
        assert "limit=5" in call_url
        assert "offset=10" in call_url

    def test_query_string_in_url(self):
        empty = {"results": [], "total": 0, "offset": 0}
        with patch("lap.cli.auth.api_request", return_value=empty) as mock_req:
            cmd_search(_make_args(query=["payment", "api"]))
        call_url = mock_req.call_args[0][1]
        assert "q=" in call_url
        assert "payment" in call_url

    def test_optional_params_omitted_when_none(self):
        empty = {"results": [], "total": 0, "offset": 0}
        with patch("lap.cli.auth.api_request", return_value=empty) as mock_req:
            cmd_search(_make_args())
        call_url = mock_req.call_args[0][1]
        assert "tag=" not in call_url
        assert "sort=" not in call_url
        assert "limit=" not in call_url
        assert "offset=" not in call_url

    def test_api_error_exits(self):
        with patch("lap.cli.auth.api_request", side_effect=Exception("Network error")):
            with pytest.raises(SystemExit):
                cmd_search(_make_args())

    def test_api_request_called_with_get(self):
        with patch("lap.cli.auth.api_request", return_value=MOCK_RESPONSE) as mock_req:
            cmd_search(_make_args())
        assert mock_req.call_args[0][0] == "GET"

    def test_api_request_url_starts_with_search(self):
        with patch("lap.cli.auth.api_request", return_value=MOCK_RESPONSE) as mock_req:
            cmd_search(_make_args())
        call_url = mock_req.call_args[0][1]
        assert call_url.startswith("/v1/search")

    def test_json_flag_skips_format(self, capsys):
        # With --json, output should be raw JSON not formatted table
        with patch("lap.cli.auth.api_request", return_value=MOCK_RESPONSE):
            cmd_search(_make_args(json=True))
        out = capsys.readouterr().out
        # Formatted output would contain "endpoints" as a table value;
        # JSON output wraps everything in the raw response
        parsed = json.loads(out)
        assert isinstance(parsed, dict)

    def test_malformed_response_exits(self):
        with patch("lap.cli.auth.api_request", return_value="not a dict"):
            with pytest.raises(SystemExit):
                cmd_search(_make_args())

    def test_results_with_skill_shown(self, capsys):
        response = {
            "results": [
                {"name": "twilio", "description": "SMS API", "has_skill": True}
            ],
            "total": 1,
            "offset": 0,
        }
        with patch("lap.cli.auth.api_request", return_value=response):
            cmd_search(_make_args(query=["twilio"]))
        out = capsys.readouterr().out
        assert "twilio" in out
        assert "[skill]" in out


# ── cmd_get ──────────────────────────────────────────────────────────


def _make_get_args(**overrides):
    args = MagicMock()
    args.name = "stripe"
    args.output = None
    args.lean = False
    for k, v in overrides.items():
        setattr(args, k, v)
    return args


class TestCmdGet:
    def test_get_prints_to_stdout(self, capsys):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"@api Stripe\n@base https://api.stripe.com"
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        with patch("lap.cli.main.urlopen", return_value=mock_resp):
            cmd_get(_make_get_args())
        out = capsys.readouterr().out
        assert "@api Stripe" in out

    def test_get_writes_to_file(self, tmp_path):
        out_file = str(tmp_path / "stripe.lap")
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"@api Stripe"
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        with patch("lap.cli.main.urlopen", return_value=mock_resp):
            cmd_get(_make_get_args(output=out_file))
        assert Path(out_file).read_text(encoding="utf-8") == "@api Stripe"

    def test_get_lean_flag_adds_query_param(self):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"@api Stripe"
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        with patch("lap.cli.main.urlopen", return_value=mock_resp) as mock_open:
            cmd_get(_make_get_args(lean=True))
        call_arg = mock_open.call_args[0][0]
        assert "format=lean" in call_arg.full_url

    def test_get_network_error_exits(self):
        with patch("lap.cli.main.urlopen", side_effect=Exception("Connection refused")):
            with pytest.raises(SystemExit):
                cmd_get(_make_get_args())
