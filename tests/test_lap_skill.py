"""Tests for the LAP CLI skill (skills/lap/).

Validates:
1. Skill file structure and frontmatter
2. Agent flow: discover -> acquire -> use (mocked CLI commands)
3. All commands documented in the skill match the actual CLI
4. Reference files exist and are well-formed
5. Live E2E: search -> get -> parse and search -> skill-install (real registry)
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import yaml

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lap.core.compilers import compile as compile_spec
from lap.core.parser import parse_lap
from lap.cli.main import cmd_search, cmd_get, _format_search_results


# ── Paths ───────────────────────────────────────────────────────────

SKILL_DIR = Path(__file__).parent.parent / "lap" / "skills" / "lap"
SKILL_MD = SKILL_DIR / "SKILL.md"
REF_DIR = SKILL_DIR / "references"
AGENT_FLOW_MD = REF_DIR / "agent-flow.md"
PUBLISHER_FLOW_MD = REF_DIR / "publisher-flow.md"
COMMAND_REF_MD = REF_DIR / "command-reference.md"
PETSTORE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "examples", "verbose", "openapi", "petstore.yaml"
)

# Mock data matching test_search.py patterns
MOCK_SEARCH_RESPONSE = {
    "results": [
        {
            "name": "stripe",
            "description": "Payment processing API",
            "endpoints": 120,
            "size": 50000,
            "lean_size": 12000,
            "has_skill": True,
            "skill_size": 3000,
            "tags": ["payment", "fintech"],
            "provider": {
                "slug": "stripe",
                "display_name": "Stripe",
                "domain": "stripe.com",
            },
        },
        {
            "name": "square",
            "description": "Square payments API",
            "endpoints": 85,
            "size": 30000,
            "lean_size": 8000,
            "has_skill": True,
            "skill_size": 2500,
            "tags": ["payment"],
            "provider": {
                "slug": "square",
                "display_name": "Square",
                "domain": "squareup.com",
            },
        },
    ],
    "total": 2,
    "offset": 0,
}

MOCK_LAP_CONTENT = b"""@lap v0.3
@api Stripe Charges v1
@base https://api.stripe.com
@auth bearer
@endpoints 2
@toc charges(2)

@group charges
@endpoint POST /v1/charges
@required {amount: int, currency: str}
@returns(200) {id: str, amount: int}

@endpoint GET /v1/charges
@returns(200) {data: [map]}
"""


def _make_search_args(**overrides):
    args = MagicMock()
    args.query = ["payment"]
    args.tag = None
    args.sort = None
    args.limit = None
    args.offset = None
    args.json = False
    for k, v in overrides.items():
        setattr(args, k, v)
    return args


def _make_get_args(**overrides):
    args = MagicMock()
    args.name = "stripe"
    args.output = None
    args.lean = False
    for k, v in overrides.items():
        setattr(args, k, v)
    return args


# ── Skill Structure Tests ──────────────────────────────────────────


class TestSkillStructure:
    """Verify skill files exist and have correct structure."""

    def test_skill_md_exists(self):
        assert SKILL_MD.is_file(), f"SKILL.md not found at {SKILL_MD}"

    def test_references_dir_exists(self):
        assert REF_DIR.is_dir(), f"references/ dir not found at {REF_DIR}"

    def test_agent_flow_exists(self):
        assert AGENT_FLOW_MD.is_file(), f"agent-flow.md not found"

    def test_publisher_flow_exists(self):
        assert PUBLISHER_FLOW_MD.is_file(), f"publisher-flow.md not found"

    def test_command_reference_exists(self):
        assert COMMAND_REF_MD.is_file(), f"command-reference.md not found"


class TestSkillFrontmatter:
    """Verify SKILL.md has valid YAML frontmatter."""

    @pytest.fixture
    def frontmatter(self):
        text = SKILL_MD.read_text(encoding="utf-8")
        match = re.match(r"^---\n(.+?)\n---", text, re.DOTALL)
        assert match, "SKILL.md must start with --- YAML frontmatter ---"
        return yaml.safe_load(match.group(1))

    def test_has_name(self, frontmatter):
        assert frontmatter["name"] == "lap"

    def test_has_description(self, frontmatter):
        assert "description" in frontmatter
        assert len(frontmatter["description"]) > 20

    def test_user_invocable(self, frontmatter):
        assert frontmatter.get("user-invocable") is True

    def test_has_version(self, frontmatter):
        assert re.match(r"\d+\.\d+\.\d+", frontmatter["version"])

    def test_openclaw_metadata(self, frontmatter):
        meta = frontmatter.get("metadata", {}).get("openclaw", {})
        assert "requires" in meta
        assert "anyBins" in meta["requires"]
        assert "lapsh" in meta["requires"]["anyBins"]

    def test_openclaw_install(self, frontmatter):
        meta = frontmatter.get("metadata", {}).get("openclaw", {})
        install = meta.get("install", [])
        assert len(install) >= 1
        assert install[0]["package"] == "@lap-platform/lapsh"

    def test_description_mentions_key_commands(self, frontmatter):
        desc = frontmatter["description"]
        for cmd in ["compile", "search", "get", "skill", "publish"]:
            assert cmd in desc, f"Description should mention '{cmd}'"


class TestSkillContent:
    """Verify SKILL.md body has required sections."""

    @pytest.fixture
    def content(self):
        return SKILL_MD.read_text(encoding="utf-8")

    def test_has_command_resolution(self, content):
        assert "Command Resolution" in content

    def test_has_agent_flow(self, content):
        assert "Agent Flow" in content

    def test_has_publisher_flow(self, content):
        assert "Publisher Flow" in content

    def test_has_quick_reference(self, content):
        assert "Quick Reference" in content

    def test_has_error_recovery(self, content):
        assert "Error Recovery" in content

    def test_has_references_section(self, content):
        assert "references/agent-flow.md" in content
        assert "references/publisher-flow.md" in content
        assert "references/command-reference.md" in content

    def test_line_count_under_budget(self, content):
        lines = content.count("\n")
        assert lines <= 500, f"SKILL.md is {lines} lines, budget is 500"

    def test_npx_command_present(self, content):
        assert "npx @lap-platform/lapsh" in content

    def test_lean_flag_documented(self, content):
        assert "--lean" in content


class TestCommandReference:
    """Verify command-reference.md covers all CLI commands."""

    @pytest.fixture
    def content(self):
        return COMMAND_REF_MD.read_text(encoding="utf-8")

    def test_all_ts_commands_documented(self, content):
        ts_commands = [
            "compile", "search", "get", "publish",
            "login", "logout", "whoami",
            "skill", "skill-batch", "skill-install",
        ]
        for cmd in ts_commands:
            assert f"### {cmd}" in content or f"### {cmd} " in content, \
                f"TS command '{cmd}' not documented"

    def test_total_command_count(self, content):
        # 10 TS commands (### headings)
        headings = re.findall(r"^### \w", content, re.MULTILINE)
        assert len(headings) >= 10, f"Expected 10 commands, found {len(headings)}"

    def test_environment_variables(self, content):
        assert "LAP_REGISTRY" in content

    def test_flags_documented(self, content):
        # Key flags that must appear
        for flag in ["--lean", "--json", "--tag", "--sort", "--provider",
                      "--ai", "--no-ai", "--install", "--full-spec"]:
            assert flag in content, f"Flag '{flag}' not documented"


class TestReferenceFiles:
    """Verify reference files are well-formed and within budget."""

    def test_agent_flow_line_count(self):
        lines = AGENT_FLOW_MD.read_text(encoding="utf-8").count("\n")
        assert lines <= 300, f"agent-flow.md is {lines} lines, budget is 300"

    def test_publisher_flow_line_count(self):
        lines = PUBLISHER_FLOW_MD.read_text(encoding="utf-8").count("\n")
        assert lines <= 350, f"publisher-flow.md is {lines} lines, budget is 350"

    def test_command_ref_line_count(self):
        lines = COMMAND_REF_MD.read_text(encoding="utf-8").count("\n")
        assert lines <= 400, f"command-reference.md is {lines} lines, budget is 400"

    def test_agent_flow_has_search_examples(self):
        content = AGENT_FLOW_MD.read_text(encoding="utf-8")
        assert "lapsh search" in content

    def test_agent_flow_has_get_examples(self):
        content = AGENT_FLOW_MD.read_text(encoding="utf-8")
        assert "lapsh get" in content

    def test_agent_flow_has_compile_examples(self):
        content = AGENT_FLOW_MD.read_text(encoding="utf-8")
        assert "lapsh compile" in content

    def test_agent_flow_has_lap_markers(self):
        content = AGENT_FLOW_MD.read_text(encoding="utf-8")
        for marker in ["@api", "@endpoint", "@required", "@response"]:
            assert marker in content, f"Agent flow should document '{marker}' marker"

    def test_publisher_flow_has_auth(self):
        content = PUBLISHER_FLOW_MD.read_text(encoding="utf-8")
        assert "lapsh login" in content
        assert "lapsh whoami" in content

    def test_publisher_flow_has_publish(self):
        content = PUBLISHER_FLOW_MD.read_text(encoding="utf-8")
        assert "lapsh publish" in content
        assert "--provider" in content

    def test_publisher_flow_has_skill_generation(self):
        content = PUBLISHER_FLOW_MD.read_text(encoding="utf-8")
        assert "lapsh skill" in content
        assert "--ai" in content


# ── Agent Flow: Discover ───────────────────────────────────────────


class TestAgentFlowDiscover:
    """Test the discover step: search the registry."""

    def test_search_returns_results(self, capsys):
        with patch("lap.cli.auth.api_request", return_value=MOCK_SEARCH_RESPONSE):
            cmd_search(_make_search_args())
        out = capsys.readouterr().out
        assert "stripe" in out.lower()

    def test_search_shows_skill_marker(self, capsys):
        with patch("lap.cli.auth.api_request", return_value=MOCK_SEARCH_RESPONSE):
            cmd_search(_make_search_args())
        out = capsys.readouterr().out
        assert "[skill]" in out

    def test_search_json_output(self, capsys):
        with patch("lap.cli.auth.api_request", return_value=MOCK_SEARCH_RESPONSE):
            cmd_search(_make_search_args(json=True))
        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert len(parsed["results"]) == 2
        assert parsed["results"][0]["has_skill"] is True

    def test_search_with_tag_filter(self):
        empty = {"results": [], "total": 0, "offset": 0}
        with patch("lap.cli.auth.api_request", return_value=empty) as mock_req:
            cmd_search(_make_search_args(tag="payment"))
        call_url = mock_req.call_args[0][1]
        assert "tag=payment" in call_url

    def test_search_with_sort(self):
        empty = {"results": [], "total": 0, "offset": 0}
        with patch("lap.cli.auth.api_request", return_value=empty) as mock_req:
            cmd_search(_make_search_args(sort="popularity"))
        call_url = mock_req.call_args[0][1]
        assert "sort=popularity" in call_url

    def test_search_with_limit(self):
        empty = {"results": [], "total": 0, "offset": 0}
        with patch("lap.cli.auth.api_request", return_value=empty) as mock_req:
            cmd_search(_make_search_args(limit=3))
        call_url = mock_req.call_args[0][1]
        assert "limit=3" in call_url

    def test_search_no_results_message(self, capsys):
        empty = {"results": [], "total": 0, "offset": 0}
        with patch("lap.cli.auth.api_request", return_value=empty):
            cmd_search(_make_search_args(query=["xyznonexistent"]))
        out = capsys.readouterr().out
        assert "No results" in out


# ── Agent Flow: Acquire ────────────────────────────────────────────


class TestAgentFlowAcquireGet:
    """Test the acquire step: download specs from registry."""

    def _mock_response(self, content=MOCK_LAP_CONTENT):
        mock_resp = MagicMock()
        mock_resp.read.return_value = content
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        return mock_resp

    def test_get_prints_lap_to_stdout(self, capsys):
        with patch("lap.cli.main.urlopen", return_value=self._mock_response()):
            cmd_get(_make_get_args())
        out = capsys.readouterr().out
        assert "@api Stripe Charges" in out

    def test_get_writes_to_file(self, tmp_path):
        out_file = str(tmp_path / "stripe.lap")
        with patch("lap.cli.main.urlopen", return_value=self._mock_response()):
            cmd_get(_make_get_args(output=out_file))
        content = Path(out_file).read_text(encoding="utf-8")
        assert "@api Stripe Charges" in content

    def test_get_lean_flag(self):
        with patch("lap.cli.main.urlopen", return_value=self._mock_response()) as mock_open:
            cmd_get(_make_get_args(lean=True))
        call_url = mock_open.call_args[0][0]
        assert "format=lean" in call_url.full_url

    def test_get_network_error(self):
        with patch("lap.cli.main.urlopen", side_effect=Exception("Connection refused")):
            with pytest.raises(SystemExit):
                cmd_get(_make_get_args())

    def test_downloaded_lap_is_parseable(self, capsys):
        with patch("lap.cli.main.urlopen", return_value=self._mock_response()):
            cmd_get(_make_get_args())
        out = capsys.readouterr().out
        spec = parse_lap(out)
        assert "Stripe Charges" in spec.api_name
        assert len(spec.endpoints) == 2


class TestAgentFlowAcquireCompile:
    """Test the acquire step: compile a local spec."""

    def test_compile_petstore(self):
        spec = compile_spec(PETSTORE_PATH)
        assert spec.api_name is not None
        assert len(spec.endpoints) > 0

    def test_compile_to_lap_text(self):
        spec = compile_spec(PETSTORE_PATH)
        text = spec.to_lap(lean=False)
        assert text.startswith("@lap")
        assert "@api" in text
        assert "@endpoint" in text

    def test_compile_lean(self):
        spec = compile_spec(PETSTORE_PATH)
        standard = spec.to_lap(lean=False)
        lean = spec.to_lap(lean=True)
        # Lean should be shorter
        assert len(lean) < len(standard)

    def test_compile_to_file(self, tmp_path):
        spec = compile_spec(PETSTORE_PATH)
        out_file = tmp_path / "petstore.lap"
        out_file.write_text(spec.to_lap(lean=False), encoding="utf-8")
        assert out_file.exists()
        content = out_file.read_text(encoding="utf-8")
        assert "@api" in content

    def test_compiled_lap_roundtrips(self):
        spec = compile_spec(PETSTORE_PATH)
        text = spec.to_lap(lean=True)
        parsed = parse_lap(text)
        assert parsed.api_name == spec.api_name
        assert len(parsed.endpoints) == len(spec.endpoints)


# ── Agent Flow: Use ────────────────────────────────────────────────


class TestAgentFlowUse:
    """Test the use step: parse and work with LAP specs."""

    @pytest.fixture
    def petstore_lap(self):
        spec = compile_spec(PETSTORE_PATH)
        return spec.to_lap(lean=False)

    def test_parse_has_api_name(self, petstore_lap):
        spec = parse_lap(petstore_lap)
        assert spec.api_name is not None
        assert len(spec.api_name) > 0

    def test_parse_has_endpoints(self, petstore_lap):
        spec = parse_lap(petstore_lap)
        assert len(spec.endpoints) > 0

    def test_parse_endpoints_have_method(self, petstore_lap):
        spec = parse_lap(petstore_lap)
        for ep in spec.endpoints:
            assert ep.method.upper() in {"GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"}

    def test_parse_endpoints_have_path(self, petstore_lap):
        spec = parse_lap(petstore_lap)
        for ep in spec.endpoints:
            assert ep.path.startswith("/")

    def test_lap_markers_present(self, petstore_lap):
        """Verify the markers documented in the skill are present."""
        assert "@api" in petstore_lap
        assert "@endpoint" in petstore_lap
        assert "@toc" in petstore_lap

    def test_lean_is_smaller_than_standard(self):
        spec = compile_spec(PETSTORE_PATH)
        standard = spec.to_lap(lean=False)
        lean = spec.to_lap(lean=True)
        assert len(lean) < len(standard), "Lean should compress more than standard"


# ── End-to-End Agent Flow ──────────────────────────────────────────


class TestAgentFlowEndToEnd:
    """Simulate the full agent flow: discover -> acquire -> use."""

    def test_search_then_get_then_parse(self, capsys):
        """Simulate: search for payment -> get stripe -> parse the result."""
        # Step 1: Discover
        with patch("lap.cli.auth.api_request", return_value=MOCK_SEARCH_RESPONSE):
            cmd_search(_make_search_args(query=["payment"]))
        search_out = capsys.readouterr().out
        assert "stripe" in search_out.lower()

        # Step 2: Acquire (get from registry)
        mock_resp = MagicMock()
        mock_resp.read.return_value = MOCK_LAP_CONTENT
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        with patch("lap.cli.main.urlopen", return_value=mock_resp):
            cmd_get(_make_get_args(name="stripe"))
        get_out = capsys.readouterr().out
        assert "@api" in get_out

        # Step 3: Use (parse the downloaded spec)
        spec = parse_lap(get_out)
        assert "Stripe Charges" in spec.api_name
        assert len(spec.endpoints) == 2
        methods = {ep.method.upper() for ep in spec.endpoints}
        assert "POST" in methods
        assert "GET" in methods

    def test_compile_local_then_parse(self, tmp_path):
        """Simulate: compile a local spec -> write to file -> parse it back."""
        # Step 1: Compile
        spec = compile_spec(PETSTORE_PATH)
        lap_text = spec.to_lap(lean=True)
        out_file = tmp_path / "petstore.lean.lap"
        out_file.write_text(lap_text, encoding="utf-8")

        # Step 2: Read back and parse
        content = out_file.read_text(encoding="utf-8")
        parsed = parse_lap(content)

        # Step 3: Verify usable
        assert parsed.api_name is not None
        assert len(parsed.endpoints) == len(spec.endpoints)
        assert all(ep.path.startswith("/") for ep in parsed.endpoints)

    def test_search_json_filter_then_get(self, capsys):
        """Simulate: search with JSON -> filter has_skill -> get."""
        # Step 1: Search JSON
        with patch("lap.cli.auth.api_request", return_value=MOCK_SEARCH_RESPONSE):
            cmd_search(_make_search_args(json=True))
        json_out = capsys.readouterr().out
        results = json.loads(json_out)

        # Step 2: Filter for APIs with skills
        with_skills = [r for r in results["results"] if r["has_skill"]]
        assert len(with_skills) >= 1
        api_name = with_skills[0]["name"]

        # Step 3: Get that API
        mock_resp = MagicMock()
        mock_resp.read.return_value = MOCK_LAP_CONTENT
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        with patch("lap.cli.main.urlopen", return_value=mock_resp):
            cmd_get(_make_get_args(name=api_name))
        out = capsys.readouterr().out
        assert "@api" in out


# ── Live E2E Tests (hit real registry) ─────────────────────────────

def _resolve_lap_cmd():
    """Resolve the lapsh CLI command, preferring global install over npx.

    On Windows, subprocess needs shell=True for .CMD wrappers (npx.CMD),
    so we return (cmd_list, shell_flag).
    """
    if shutil.which("lapsh"):
        return ["lapsh"], False
    npx = shutil.which("npx")
    if npx:
        # Windows: npx.CMD needs shell=True for subprocess
        needs_shell = sys.platform == "win32"
        return ["npx", "@lap-platform/lapsh"], needs_shell
    return None, False


def _can_reach_registry():
    """Quick check: can we reach the registry?"""
    cmd, shell = _resolve_lap_cmd()
    if not cmd:
        return False
    try:
        result = subprocess.run(
            cmd + ["search", "test", "--limit", "1", "--json"],
            capture_output=True, text=True, timeout=20, shell=shell,
        )
        return result.returncode == 0 and '"results"' in result.stdout
    except (subprocess.TimeoutExpired, OSError):
        return False


# Cache the check so it only runs once per session
_REGISTRY_OK = None

def registry_available():
    global _REGISTRY_OK
    if _REGISTRY_OK is None:
        _REGISTRY_OK = _can_reach_registry()
    return _REGISTRY_OK


skip_no_registry = pytest.mark.skipif(
    "os.environ.get('CI') == 'true' or not registry_available()",
    reason="LAP registry live tests skipped in CI or registry unreachable",
)

PROJECT_DIR = Path(__file__).parent.parent


@skip_no_registry
class TestLiveDiscover:
    """E2E: search the real LAP registry."""

    def _run(self, *args, **kwargs):
        cmd, shell = _resolve_lap_cmd()
        return subprocess.run(
            cmd + list(args),
            capture_output=True, text=True, timeout=30,
            shell=shell, cwd=str(PROJECT_DIR), **kwargs,
        )

    def test_search_returns_results(self):
        r = self._run("search", "payment", "--limit", "3")
        assert r.returncode == 0
        assert "endpoints" in r.stdout
        assert "compressed" in r.stdout

    def test_search_json_parseable(self):
        r = self._run("search", "payment", "--limit", "3", "--json")
        assert r.returncode == 0
        data = json.loads(r.stdout)
        assert "results" in data
        assert len(data["results"]) > 0

    def test_search_json_has_expected_fields(self):
        r = self._run("search", "stripe", "--limit", "1", "--json")
        assert r.returncode == 0
        data = json.loads(r.stdout)
        result = data["results"][0]
        for field in ["name", "endpoints", "size", "has_skill"]:
            assert field in result, f"Missing field '{field}' in search result"

    def test_search_with_tag(self):
        r = self._run("search", "api", "--tag", "payment", "--limit", "3")
        assert r.returncode == 0

    def test_search_with_sort(self):
        r = self._run("search", "api", "--sort", "popularity", "--limit", "3")
        assert r.returncode == 0

    def test_search_no_results(self):
        r = self._run("search", "xyznonexistent999")
        assert r.returncode == 0
        assert "No results" in r.stdout or "0" in r.stdout


@skip_no_registry
class TestLiveAcquireGet:
    """E2E: download real specs from the registry."""

    def _run(self, *args, **kwargs):
        cmd, shell = _resolve_lap_cmd()
        return subprocess.run(
            cmd + list(args),
            capture_output=True, text=True, timeout=30,
            shell=shell, cwd=str(PROJECT_DIR), **kwargs,
        )

    def _find_api_name(self):
        """Find a real API name from the registry."""
        r = self._run("search", "api", "--limit", "1", "--json")
        data = json.loads(r.stdout)
        return data["results"][0]["name"]

    def test_get_to_stdout(self):
        name = self._find_api_name()
        r = self._run("get", name)
        assert r.returncode == 0
        assert "@api" in r.stdout
        assert "@endpoint" in r.stdout

    def test_get_to_file(self, tmp_path):
        name = self._find_api_name()
        out = str(tmp_path / "spec.lap")
        r = self._run("get", name, "-o", out)
        assert r.returncode == 0
        content = Path(out).read_text(encoding="utf-8")
        assert "@api" in content
        assert "@endpoint" in content

    def test_get_lean(self, tmp_path):
        name = self._find_api_name()
        out = str(tmp_path / "spec.lean.lap")
        r = self._run("get", name, "--lean", "-o", out)
        assert r.returncode == 0
        content = Path(out).read_text(encoding="utf-8")
        assert "@api" in content

    def test_get_output_is_parseable(self):
        """Downloaded LAP can be parsed back into a LAPSpec."""
        name = self._find_api_name()
        r = self._run("get", name)
        assert r.returncode == 0
        spec = parse_lap(r.stdout)
        assert spec.api_name is not None
        assert len(spec.endpoints) > 0


@skip_no_registry
class TestLiveAcquireSkillInstall:
    """E2E: install a real skill from the registry."""

    def _run(self, *args, **kwargs):
        cmd, shell = _resolve_lap_cmd()
        return subprocess.run(
            cmd + list(args),
            capture_output=True, text=True, timeout=30,
            shell=shell, cwd=str(PROJECT_DIR), **kwargs,
        )

    def _find_api_with_skill(self):
        """Find an API that has a skill available."""
        r = self._run("search", "api", "--limit", "20", "--json")
        data = json.loads(r.stdout)
        for result in data["results"]:
            if result.get("has_skill"):
                return result["name"]
        pytest.skip("No API with skill found in first 20 results")

    def test_skill_install_creates_files(self, tmp_path):
        name = self._find_api_with_skill()
        install_dir = str(tmp_path / name)
        r = self._run("skill-install", name, "--dir", install_dir)
        assert r.returncode == 0

        install_path = Path(install_dir)
        skill_md = install_path / "SKILL.md"
        assert skill_md.exists(), f"SKILL.md not created at {skill_md}"

    def test_installed_skill_has_valid_frontmatter(self, tmp_path):
        name = self._find_api_with_skill()
        install_dir = str(tmp_path / name)
        self._run("skill-install", name, "--dir", install_dir)

        skill_md = Path(install_dir) / "SKILL.md"
        text = skill_md.read_text(encoding="utf-8")
        match = re.match(r"^---\n(.+?)\n---", text, re.DOTALL)
        assert match, "Installed SKILL.md should have YAML frontmatter"
        fm = yaml.safe_load(match.group(1))
        assert "name" in fm
        assert "description" in fm

    def test_installed_skill_has_lap_spec(self, tmp_path):
        name = self._find_api_with_skill()
        install_dir = str(tmp_path / name)
        self._run("skill-install", name, "--dir", install_dir)

        refs_dir = Path(install_dir) / "references"
        assert refs_dir.exists(), "references/ dir should exist"
        lap_files = list(refs_dir.glob("*.lap"))
        assert len(lap_files) >= 1, "Should have at least one .lap file"

        # Verify the LAP file is parseable
        lap_content = lap_files[0].read_text(encoding="utf-8")
        spec = parse_lap(lap_content)
        assert spec.api_name is not None
        assert len(spec.endpoints) > 0


@skip_no_registry
class TestLiveCompile:
    """E2E: compile a local spec via the real CLI."""

    def _run(self, *args, **kwargs):
        cmd, shell = _resolve_lap_cmd()
        return subprocess.run(
            cmd + list(args),
            capture_output=True, text=True, timeout=30,
            shell=shell, cwd=str(PROJECT_DIR), **kwargs,
        )

    def test_compile_petstore_to_stdout(self):
        r = self._run("compile", PETSTORE_PATH)
        assert r.returncode == 0
        assert "@api" in r.stdout
        assert "@endpoint" in r.stdout
        assert "@toc" in r.stdout

    def test_compile_petstore_lean(self, tmp_path):
        out = str(tmp_path / "petstore.lean.lap")
        r = self._run("compile", PETSTORE_PATH, "--lean", "-o", out)
        assert r.returncode == 0
        content = Path(out).read_text(encoding="utf-8")
        assert "@api" in content
        # Lean should not have @desc
        assert "@desc" not in content

    def test_compile_output_is_parseable(self):
        r = self._run("compile", PETSTORE_PATH)
        assert r.returncode == 0
        spec = parse_lap(r.stdout)
        assert spec.api_name is not None
        assert len(spec.endpoints) == 19  # petstore has 19 endpoints


@skip_no_registry
class TestLiveAgentFlowEndToEnd:
    """E2E: the full agent discover -> acquire -> use flow against the real registry."""

    def _run(self, *args, **kwargs):
        cmd, shell = _resolve_lap_cmd()
        return subprocess.run(
            cmd + list(args),
            capture_output=True, text=True, timeout=30,
            shell=shell, cwd=str(PROJECT_DIR), **kwargs,
        )

    def test_search_then_get_then_parse(self):
        """Full flow: search -> pick first result -> get -> parse."""
        # Step 1: Discover
        r = self._run("search", "payment", "--limit", "3", "--json")
        assert r.returncode == 0
        data = json.loads(r.stdout)
        assert len(data["results"]) > 0
        name = data["results"][0]["name"]

        # Step 2: Acquire
        r = self._run("get", name)
        assert r.returncode == 0
        assert "@api" in r.stdout

        # Step 3: Use
        spec = parse_lap(r.stdout)
        assert spec.api_name is not None
        assert len(spec.endpoints) > 0
        # Verify endpoints are well-formed
        for ep in spec.endpoints:
            assert ep.method.upper() in {"GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"}
            assert ep.path.startswith("/")

    def test_search_then_skill_install_then_verify(self, tmp_path):
        """Full flow: search for skill -> install -> verify files -> parse LAP."""
        # Step 1: Discover APIs with skills
        r = self._run("search", "api", "--limit", "20", "--json")
        assert r.returncode == 0
        data = json.loads(r.stdout)
        with_skills = [x for x in data["results"] if x.get("has_skill")]
        if not with_skills:
            pytest.skip("No APIs with skills found")
        name = with_skills[0]["name"]

        # Step 2: Install skill
        install_dir = str(tmp_path / name)
        r = self._run("skill-install", name, "--dir", install_dir)
        assert r.returncode == 0

        # Step 3: Verify skill structure
        install_path = Path(install_dir)
        assert (install_path / "SKILL.md").exists()
        assert (install_path / "references").is_dir()

        # Step 4: Parse the installed LAP spec
        lap_files = list((install_path / "references").glob("*.lap"))
        assert len(lap_files) >= 1
        spec = parse_lap(lap_files[0].read_text(encoding="utf-8"))
        assert spec.api_name is not None
        assert len(spec.endpoints) > 0

    def test_compile_local_then_parse_roundtrip(self, tmp_path):
        """Full flow: compile local spec -> write -> read back -> parse -> verify."""
        # Step 1: Compile
        out = str(tmp_path / "petstore.lap")
        r = self._run("compile", PETSTORE_PATH, "-o", out)
        assert r.returncode == 0

        # Step 2: Read and parse
        content = Path(out).read_text(encoding="utf-8")
        spec = parse_lap(content)

        # Step 3: Verify
        assert spec.api_name is not None
        assert len(spec.endpoints) == 19
        methods = {ep.method.upper() for ep in spec.endpoints}
        assert "GET" in methods
        assert "POST" in methods
        assert "PUT" in methods
        assert "DELETE" in methods
