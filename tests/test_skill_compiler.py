"""Tests for the skill compiler (Layer 1 -- mechanical generation)."""

import os
import re
import tempfile
from pathlib import Path

import pytest

from lap.core.compilers import compile as compile_spec
from lap.core.compilers.skill import (
    SkillOptions,
    SkillOutput,
    generate_skill,
    _slugify,
    _singularize,
    _resource_from_path,
    _infer_question_mapping,
    SKILL_MD_TOKEN_BUDGET,
)
from lap.core.formats.lap import LAPSpec, Endpoint, Param, ResponseSchema, ResponseField, ErrorSchema
from lap.core.utils import count_tokens


# ── Fixtures ────────────────────────────────────────────────────────

PETSTORE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "examples", "verbose", "openapi", "petstore.yaml"
)


@pytest.fixture
def petstore_spec():
    """Compile the petstore fixture to LAPSpec."""
    return compile_spec(PETSTORE_PATH)


@pytest.fixture
def minimal_spec():
    """A minimal spec with 1 endpoint and no auth."""
    return LAPSpec(
        api_name="Minimal API",
        base_url="https://api.minimal.com",
        version="1.0.0",
        endpoints=[
            Endpoint(method="get", path="/health", summary="Health check"),
        ],
    )


@pytest.fixture
def large_spec():
    """A spec with 100+ endpoints for token budget testing."""
    endpoints = []
    for i in range(120):
        group = f"resource{i // 4}"
        endpoints.append(
            Endpoint(
                method=["get", "post", "put", "delete"][i % 4],
                path=f"/{group}/{'{id}' if i % 4 in (2, 3) else ''}".rstrip('/'),
                summary=f"Operation {i} on {group}",
                required_params=[
                    Param(name="param1", type="str", required=True),
                ] if i % 3 == 0 else [],
                optional_params=[
                    Param(name="opt1", type="int"),
                ],
            )
        )
    return LAPSpec(
        api_name="Large API",
        base_url="https://api.large.com/v1",
        version="2.0.0",
        auth_scheme="Bearer token",
        endpoints=endpoints,
    )


# ── Directory structure tests ────────────────────────────────────────

def test_skill_directory_structure(petstore_spec):
    """file_map has SKILL.md and references/api-spec.lap."""
    result = generate_skill(petstore_spec)
    assert "SKILL.md" in result.file_map
    assert "references/api-spec.lap" in result.file_map
    assert len(result.file_map) == 2


def test_skill_output_type(petstore_spec):
    """generate_skill returns a SkillOutput."""
    result = generate_skill(petstore_spec)
    assert isinstance(result, SkillOutput)
    assert isinstance(result.name, str)
    assert isinstance(result.file_map, dict)
    assert isinstance(result.token_count, int)
    assert isinstance(result.endpoint_count, int)


def test_skill_name_is_slugified(petstore_spec):
    """Skill name should be slugified version of API name."""
    result = generate_skill(petstore_spec)
    assert result.name == _slugify(petstore_spec.api_name)
    # Should be lowercase, no spaces
    assert result.name == result.name.lower()
    assert " " not in result.name


def test_endpoint_count_matches(petstore_spec):
    """endpoint_count should match spec endpoints."""
    result = generate_skill(petstore_spec)
    assert result.endpoint_count == len(petstore_spec.endpoints)


# ── Frontmatter tests ────────────────────────────────────────────────

def test_frontmatter_format(petstore_spec):
    """SKILL.md should have valid YAML frontmatter with name and description."""
    result = generate_skill(petstore_spec)
    skill_md = result.file_map["SKILL.md"]

    # Should start with ---
    assert skill_md.startswith("---\n")

    # Extract frontmatter
    parts = skill_md.split("---", 2)
    assert len(parts) >= 3, "Frontmatter should be delimited by ---"
    frontmatter = parts[1].strip()

    # Should have name and description
    assert "name:" in frontmatter
    assert "description:" in frontmatter

    # Name should match slug
    name_match = re.search(r'name:\s*(.+)', frontmatter)
    assert name_match
    assert name_match.group(1).strip() == _slugify(petstore_spec.api_name)


# ── Endpoint catalog completeness ────────────────────────────────────

def test_endpoint_catalog_completeness(petstore_spec):
    """All spec endpoints should appear in the catalog."""
    result = generate_skill(petstore_spec)
    skill_md = result.file_map["SKILL.md"]

    for ep in petstore_spec.endpoints:
        assert f"| {ep.method.upper()} |" in skill_md, f"Method {ep.method.upper()} missing from SKILL.md"
        assert ep.path in skill_md, f"Endpoint {ep.method} {ep.path} missing from SKILL.md"


# ── Question inference ────────────────────────────────────────────────

def test_question_inference(petstore_spec):
    """Mechanical question mapping should infer correct patterns."""
    questions = _infer_question_mapping(petstore_spec)
    assert len(questions) > 0

    # Should have auth question since petstore has auth
    auth_questions = [q for q in questions if "authenticate" in q.lower()]
    assert len(auth_questions) > 0


def test_question_inference_patterns():
    """Test specific question patterns for CRUD endpoints."""
    spec = LAPSpec(
        api_name="Test API",
        base_url="https://api.test.com",
        auth_scheme="Bearer token",
        endpoints=[
            Endpoint(method="get", path="/pets", summary="List all pets"),
            Endpoint(method="get", path="/pets/{petId}", summary="Get a pet"),
            Endpoint(method="post", path="/pets", summary="Create a pet"),
            Endpoint(method="put", path="/pets/{petId}", summary="Update a pet"),
            Endpoint(method="delete", path="/pets/{petId}", summary="Delete a pet"),
            Endpoint(
                method="get", path="/pets/search",
                summary="Search pets",
                optional_params=[Param(name="q", type="str")],
            ),
        ],
    )
    questions = _infer_question_mapping(spec)
    q_text = "\n".join(questions)

    assert '"List all pets?"' in q_text
    assert '"Get pet details?"' in q_text
    assert '"Create a pet?"' in q_text
    assert '"Update a pet?"' in q_text
    assert '"Delete a pet?"' in q_text
    assert '"How to authenticate?"' in q_text


# ── Auth extraction ──────────────────────────────────────────────────

def test_auth_extraction(petstore_spec):
    """Auth section should match spec.auth_scheme."""
    result = generate_skill(petstore_spec)
    skill_md = result.file_map["SKILL.md"]

    # Find Auth section
    auth_match = re.search(r'## Auth\n(.+?)(?:\n##|\Z)', skill_md, re.DOTALL)
    assert auth_match, "Auth section not found in SKILL.md"

    if petstore_spec.auth_scheme:
        assert petstore_spec.auth_scheme in auth_match.group(1)


def test_no_auth_spec():
    """Spec without auth should say 'No authentication required'."""
    spec = LAPSpec(
        api_name="Public API",
        base_url="https://api.public.com",
        endpoints=[Endpoint(method="get", path="/status")],
    )
    result = generate_skill(spec)
    skill_md = result.file_map["SKILL.md"]
    assert "No authentication required" in skill_md


# ── Lean spec reference ──────────────────────────────────────────────

def test_lean_spec_included(petstore_spec):
    """references/api-spec.lap should be a valid lean LAP spec."""
    result = generate_skill(petstore_spec)
    lap_text = result.file_map["references/api-spec.lap"]

    # Should have LAP markers
    assert "@lap" in lap_text
    assert "@api" in lap_text
    assert "@endpoint" in lap_text

    # Should be lean (no @desc lines)
    lines = lap_text.split("\n")
    desc_lines = [l for l in lines if l.strip().startswith("@desc")]
    assert len(desc_lines) == 0, "Lean spec should not have @desc lines"


# ── Minimal spec ─────────────────────────────────────────────────────

def test_minimal_spec(minimal_spec):
    """Minimal spec (1 endpoint, no auth) should produce valid skill."""
    result = generate_skill(minimal_spec)
    assert "SKILL.md" in result.file_map
    assert result.endpoint_count == 1
    assert result.token_count > 0

    skill_md = result.file_map["SKILL.md"]
    assert "Minimal API" in skill_md
    assert "/health" in skill_md
    assert "No authentication required" in skill_md


# ── Large spec token budget ──────────────────────────────────────────

def test_large_spec(large_spec):
    """Large spec (100+ endpoints) should stay reasonable on tokens."""
    result = generate_skill(large_spec)
    assert result.endpoint_count == 120

    # SKILL.md body should stay within token budget (with headroom)
    skill_tokens = count_tokens(result.file_map["SKILL.md"])
    budget = SKILL_MD_TOKEN_BUDGET * 2  # generous headroom for large specs
    assert skill_tokens < budget, f"SKILL.md is {skill_tokens} tokens, expected < {budget}"


# ── Group names ──────────────────────────────────────────────────────

def test_group_names(petstore_spec):
    """Groups in skill should match @toc groups from the spec."""
    result = generate_skill(petstore_spec)
    skill_md = result.file_map["SKILL.md"]

    # Extract ### headings under ## Endpoints
    section_match = re.search(r'## Endpoints\n(.+?)(?:\n## |\Z)', skill_md, re.DOTALL)
    assert section_match, "Endpoints section not found"

    headings = re.findall(r'### (\w+)', section_match.group(1))
    assert len(headings) > 0, "No group headings found"

    # All endpoint paths should be covered by some group
    from lap.core.formats.lap import _group_name
    expected_groups = set(_group_name(ep.path) for ep in petstore_spec.endpoints)
    actual_groups = set(headings)
    assert expected_groups == actual_groups


# ── Install path ─────────────────────────────────────────────────────

def test_install_path(petstore_spec):
    """Skill output name should produce a valid install path."""
    result = generate_skill(petstore_spec)
    # Name should be safe for filesystem
    assert re.match(r'^[a-z0-9-]+$', result.name), f"Invalid name: {result.name}"
    # Should not contain path traversal
    assert ".." not in result.name
    # Simulated install path
    install_path = Path.home() / ".claude" / "skills" / result.name
    assert str(install_path)  # Just check it's constructable


# ── Slugify tests ────────────────────────────────────────────────────

def test_slugify_basic():
    assert _slugify("Swagger Petstore") == "swagger-petstore"


def test_slugify_special_chars():
    assert _slugify("My API (v2.0)") == "my-api-v2-0"


def test_slugify_underscores():
    assert _slugify("my_cool_api") == "my-cool-api"


def test_slugify_empty():
    assert _slugify("") == "api"


def test_slugify_dashes():
    assert _slugify("already-slugified") == "already-slugified"


# ── Singularize tests ────────────────────────────────────────────────

def test_singularize_basic():
    assert _singularize("pets") == "pet"
    assert _singularize("users") == "user"
    assert _singularize("categories") == "category"
    assert _singularize("addresses") == "address"


def test_singularize_already_singular():
    assert _singularize("pet") == "pet"
    assert _singularize("status") == "status"


# ── Resource from path ───────────────────────────────────────────────

def test_resource_from_path():
    assert _resource_from_path("/pets") == "pets"
    assert _resource_from_path("/pets/{petId}") == "pets"
    assert _resource_from_path("/v1/users/{userId}") == "users"
    assert _resource_from_path("/api/v2/orders") == "orders"


# ── Options ──────────────────────────────────────────────────────────

def test_default_options(petstore_spec):
    """Default options should work."""
    result = generate_skill(petstore_spec)
    assert result is not None


def test_non_lean_option(petstore_spec):
    """Non-lean option should include descriptions in the LAP spec."""
    options = SkillOptions(lean=False)
    result = generate_skill(petstore_spec, options)
    lap_text = result.file_map["references/api-spec.lap"]

    # Non-lean should have @desc lines
    lines = lap_text.split("\n")
    desc_lines = [l for l in lines if l.strip().startswith("@desc")]
    assert len(desc_lines) > 0, "Non-lean spec should have @desc lines"


# ── Response tips ────────────────────────────────────────────────────

def test_response_tips_present(petstore_spec):
    """SKILL.md should have a Response Tips section."""
    result = generate_skill(petstore_spec)
    skill_md = result.file_map["SKILL.md"]
    assert "## Response Tips" in skill_md


# ── Token counting ───────────────────────────────────────────────────

def test_token_count_positive(petstore_spec):
    """Token count should be positive and sum of all files."""
    result = generate_skill(petstore_spec)
    assert result.token_count > 0

    expected = sum(count_tokens(c) for c in result.file_map.values())
    assert result.token_count == expected


# -- New tests ---------------------------------------------------------------

def test_empty_spec_raises():
    """Spec with no endpoints should raise ValueError."""
    spec = LAPSpec(
        api_name="Empty API",
        base_url="https://api.empty.com",
        endpoints=[],
    )
    with pytest.raises(ValueError, match="no endpoints"):
        generate_skill(spec)


def test_patch_question():
    """PATCH endpoint should generate partial update question."""
    spec = LAPSpec(
        api_name="Patch API",
        base_url="https://api.patch.com",
        endpoints=[
            Endpoint(method="patch", path="/items/{id}", summary="Partially update item"),
        ],
    )
    questions = _infer_question_mapping(spec)
    q_text = "\n".join(questions)
    assert "Partially update" in q_text


def test_multi_auth():
    """Spec with multiple auth references should include auth question."""
    spec = LAPSpec(
        api_name="Multi Auth API",
        base_url="https://api.multi.com",
        auth_scheme="Bearer token or API key",
        endpoints=[
            Endpoint(method="get", path="/public", summary="Public endpoint"),
            Endpoint(method="get", path="/private", summary="Private endpoint", auth="Bearer token"),
        ],
    )
    result = generate_skill(spec)
    skill_md = result.file_map["SKILL.md"]
    assert "Bearer token or API key" in skill_md
    questions = _infer_question_mapping(spec)
    assert any("authenticate" in q.lower() for q in questions)


def test_singularize_vowel_ses():
    """Singularize should handle vowel+ses correctly."""
    assert _singularize("responses") == "response"
    assert _singularize("databases") == "database"
    assert _singularize("purchases") == "purchase"
    assert _singularize("resources") == "resource"
    assert _singularize("cases") == "case"
    assert _singularize("bases") == "base"
    # Standard plurals should still work
    assert _singularize("pets") == "pet"
    assert _singularize("users") == "user"
    assert _singularize("categories") == "category"


# -- Distribution frontmatter tests -----------------------------------------

def test_frontmatter_has_version(minimal_spec):
    """Generated frontmatter includes version: 1.0.0"""
    result = generate_skill(minimal_spec)
    skill_md = result.file_map["SKILL.md"]
    assert "version: 1.0.0" in skill_md


def test_frontmatter_has_generator(minimal_spec):
    """Generated frontmatter includes generator: lapsh"""
    result = generate_skill(minimal_spec)
    skill_md = result.file_map["SKILL.md"]
    assert "generator: lapsh" in skill_md


def test_frontmatter_version_and_generator_in_frontmatter(minimal_spec):
    """version and generator should be inside frontmatter delimiters."""
    result = generate_skill(minimal_spec)
    skill_md = result.file_map["SKILL.md"]
    parts = skill_md.split("---", 2)
    frontmatter = parts[1]
    assert "version: 1.0.0" in frontmatter
    assert "generator: lapsh" in frontmatter


def test_clawhub_metadata_with_auth():
    """With clawhub=True and auth, includes metadata.openclaw.requires.env."""
    spec = LAPSpec(
        api_name="Stripe",
        base_url="https://api.stripe.com",
        auth_scheme="Bearer token",
        endpoints=[Endpoint(method="get", path="/charges", summary="List charges")],
    )
    result = generate_skill(spec, SkillOptions(clawhub=True))
    md = result.file_map["SKILL.md"]
    assert "metadata:" in md
    assert "openclaw:" in md
    assert "requires:" in md
    assert "env:" in md
    assert "STRIPE_API_KEY" in md


def test_clawhub_metadata_without_auth():
    """With clawhub=True but no auth, omits metadata.openclaw block."""
    spec = LAPSpec(
        api_name="Public API",
        base_url="https://api.public.com",
        endpoints=[Endpoint(method="get", path="/status")],
    )
    result = generate_skill(spec, SkillOptions(clawhub=True))
    md = result.file_map["SKILL.md"]
    # metadata block should not appear in frontmatter
    parts = md.split("---", 2)
    frontmatter = parts[1]
    assert "metadata:" not in frontmatter


def test_default_no_clawhub_metadata():
    """Default generation (clawhub=False) omits metadata.openclaw even with auth."""
    spec = LAPSpec(
        api_name="Stripe",
        base_url="https://api.stripe.com",
        auth_scheme="Bearer token",
        endpoints=[Endpoint(method="get", path="/charges", summary="List charges")],
    )
    result = generate_skill(spec)  # clawhub defaults to False
    md = result.file_map["SKILL.md"]
    parts = md.split("---", 2)
    frontmatter = parts[1]
    assert "metadata:" not in frontmatter


def test_attribution_line(minimal_spec):
    """SKILL.md body contains LAP attribution line."""
    result = generate_skill(minimal_spec)
    md = result.file_map["SKILL.md"]
    assert "Generated from the official API spec by" in md
    assert "lap.sh" in md


def test_attribution_after_references(minimal_spec):
    """Attribution line should appear after References section."""
    result = generate_skill(minimal_spec)
    md = result.file_map["SKILL.md"]
    ref_idx = md.index("## References")
    attr_idx = md.index("Generated from the official API spec by")
    assert attr_idx > ref_idx


# -- Skill version override tests -------------------------------------------

def test_custom_skill_version():
    """SkillOptions(version='2.1.0') puts version: 2.1.0 in frontmatter."""
    spec = LAPSpec(
        api_name="Version Test API",
        base_url="https://api.test.com",
        endpoints=[Endpoint(method="get", path="/ping", summary="Ping")],
    )
    result = generate_skill(spec, SkillOptions(version="2.1.0"))
    md = result.file_map["SKILL.md"]
    parts = md.split("---", 2)
    frontmatter = parts[1]
    assert "version: 2.1.0" in frontmatter
    assert "version: 1.0.0" not in frontmatter


def test_api_version_in_body():
    """spec.version appears in SKILL.md body after the title."""
    spec = LAPSpec(
        api_name="Versioned API",
        base_url="https://api.test.com",
        version="1.0.27",
        endpoints=[Endpoint(method="get", path="/items", summary="List items")],
    )
    result = generate_skill(spec)
    md = result.file_map["SKILL.md"]
    assert "API version: 1.0.27" in md
    # Should appear right after the title
    title_idx = md.index("# Versioned API")
    version_idx = md.index("API version: 1.0.27")
    assert version_idx > title_idx


def test_api_version_omitted_when_empty():
    """No 'API version:' line when spec.version is empty."""
    spec = LAPSpec(
        api_name="No Version API",
        base_url="https://api.test.com",
        version="",
        endpoints=[Endpoint(method="get", path="/status", summary="Status")],
    )
    result = generate_skill(spec)
    md = result.file_map["SKILL.md"]
    assert "API version:" not in md


# -- Target: Cursor -----------------------------------------------------------

class TestCursorTarget:
    """Tests for --target cursor output."""

    def test_cursor_file_extension(self, minimal_spec):
        """Cursor target produces .mdc file instead of SKILL.md."""
        result = generate_skill(minimal_spec, SkillOptions(target="cursor"))
        mdc_files = [k for k in result.file_map if k.endswith(".mdc")]
        assert len(mdc_files) == 1
        assert "SKILL.md" not in result.file_map

    def test_cursor_filename_matches_slug(self, minimal_spec):
        """Cursor .mdc filename matches slugified API name."""
        result = generate_skill(minimal_spec, SkillOptions(target="cursor"))
        expected = f"{_slugify(minimal_spec.api_name)}.mdc"
        assert expected in result.file_map

    def test_cursor_frontmatter_has_description(self, minimal_spec):
        """Cursor frontmatter has description field."""
        result = generate_skill(minimal_spec, SkillOptions(target="cursor"))
        md = result.file_map[result.main_file]
        parts = md.split("---", 2)
        frontmatter = parts[1]
        assert "description:" in frontmatter

    def test_cursor_frontmatter_has_always_apply(self, minimal_spec):
        """Cursor frontmatter has alwaysApply: false."""
        result = generate_skill(minimal_spec, SkillOptions(target="cursor"))
        md = result.file_map[result.main_file]
        parts = md.split("---", 2)
        frontmatter = parts[1]
        assert "alwaysApply: false" in frontmatter

    def test_cursor_frontmatter_no_generator(self, minimal_spec):
        """Cursor frontmatter should NOT have generator or version fields."""
        result = generate_skill(minimal_spec, SkillOptions(target="cursor"))
        md = result.file_map[result.main_file]
        parts = md.split("---", 2)
        frontmatter = parts[1]
        assert "generator:" not in frontmatter
        assert "version:" not in frontmatter

    def test_cursor_reference_file_present(self, minimal_spec):
        """Cursor target still includes references/api-spec.lap."""
        result = generate_skill(minimal_spec, SkillOptions(target="cursor"))
        assert "references/api-spec.lap" in result.file_map

    def test_cursor_body_matches_claude(self, minimal_spec):
        """Cursor body content (after frontmatter) matches Claude body."""
        claude = generate_skill(minimal_spec, SkillOptions(target="claude"))
        cursor = generate_skill(minimal_spec, SkillOptions(target="cursor"))
        claude_body = claude.file_map[claude.main_file].split("---", 2)[2]
        cursor_body = cursor.file_map[cursor.main_file].split("---", 2)[2]
        assert claude_body == cursor_body


# -- Default target ------------------------------------------------------------

class TestDefaultTarget:
    """Verify default target is Claude for backward compat."""

    def test_default_is_claude(self, minimal_spec):
        """Default SkillOptions produces Claude output."""
        result = generate_skill(minimal_spec)
        assert "SKILL.md" in result.file_map
        md = result.file_map["SKILL.md"]
        parts = md.split("---", 2)
        frontmatter = parts[1]
        assert "generator: lapsh" in frontmatter
        assert "version:" in frontmatter


# -- CLI section ---------------------------------------------------------------

class TestCliSection:
    """Verify CLI section appears in generated skills."""

    def test_cli_section_present(self, minimal_spec):
        """Generated body includes ## CLI section."""
        result = generate_skill(minimal_spec)
        md = result.file_map["SKILL.md"]
        assert "## CLI" in md

    def test_cli_section_has_npx(self, minimal_spec):
        """CLI section contains npx @lap-platform/lapsh commands."""
        result = generate_skill(minimal_spec)
        md = result.file_map["SKILL.md"]
        assert "npx @lap-platform/lapsh" in md

    def test_cli_section_has_slug(self, minimal_spec):
        """CLI section uses slugified API name."""
        result = generate_skill(minimal_spec)
        md = result.file_map["SKILL.md"]
        slug = _slugify(minimal_spec.api_name)
        assert f"lapsh get {slug}" in md
        assert f"lapsh search {slug}" in md

    def test_cli_section_in_all_targets(self, minimal_spec):
        """CLI section appears in Claude, Cursor, and Codex outputs."""
        for target in ("claude", "cursor", "codex"):
            result = generate_skill(minimal_spec, SkillOptions(target=target))
            assert "## CLI" in result.file_map[result.main_file], f"CLI section missing for {target}"

    def test_cli_section_before_references(self, minimal_spec):
        """CLI section appears before References section."""
        result = generate_skill(minimal_spec)
        md = result.file_map["SKILL.md"]
        cli_idx = md.index("## CLI")
        ref_idx = md.index("## References")
        assert cli_idx < ref_idx


# -- Invalid target ---------------------------------------------------------------

def test_invalid_target_raises(minimal_spec):
    """Unknown target raises ValueError."""
    with pytest.raises(ValueError, match="Unknown target"):
        generate_skill(minimal_spec, SkillOptions(target="vscode"))


# -- Init command (built-in skill install) -------------------------------------

class TestInit:
    """Tests for _install_builtin_skill and _get_skills_dir (used by lapsh init)."""

    def test_skills_dir_found(self):
        """_get_skills_dir returns a valid directory."""
        from lap.cli.main import _get_skills_dir
        skills_dir = _get_skills_dir()
        assert skills_dir is not None
        assert skills_dir.is_dir()

    def test_builtin_install_cursor(self, tmp_path):
        """Installing 'lap' for cursor creates .mdc file with references."""
        from lap.cli.main import _install_builtin_skill
        dest = tmp_path / "cursor-out"
        _install_builtin_skill("lap", "cursor", str(dest))
        assert (dest / "lap.mdc").exists()
        assert (dest / "references" / "agent-flow.md").exists()
        assert (dest / "references" / "command-reference.md").exists()
        assert (dest / "references" / "publisher-flow.md").exists()

    def test_builtin_install_claude(self, tmp_path):
        """Installing 'lap' for claude creates SKILL.md with references."""
        from lap.cli.main import _install_builtin_skill
        dest = tmp_path / "claude-out"
        _install_builtin_skill("lap", "claude", str(dest))
        assert (dest / "SKILL.md").exists()
        assert (dest / "references" / "agent-flow.md").exists()

    def test_builtin_cursor_no_claude_paths(self, tmp_path):
        """Cursor skill file should not contain ~/.claude/ paths."""
        from lap.cli.main import _install_builtin_skill
        dest = tmp_path / "check"
        _install_builtin_skill("lap", "cursor", str(dest))
        content = (dest / "lap.mdc").read_text(encoding="utf-8")
        assert "~/.claude/skills/" not in content

    def test_builtin_install_codex(self, tmp_path):
        """Installing 'lap' for codex creates SKILL.md with references (same as claude)."""
        from lap.cli.main import _install_builtin_skill
        dest = tmp_path / "codex-out"
        _install_builtin_skill("lap", "codex", str(dest))
        assert (dest / "SKILL.md").exists()
        assert (dest / "references" / "agent-flow.md").exists()
        assert (dest / "references" / "command-reference.md").exists()
        assert (dest / "references" / "publisher-flow.md").exists()

    def test_builtin_codex_no_claude_paths(self, tmp_path):
        """Codex skill file should not contain ~/.claude/ paths."""
        from lap.cli.main import _install_builtin_skill
        dest = tmp_path / "check"
        _install_builtin_skill("lap", "codex", str(dest))
        content = (dest / "SKILL.md").read_text(encoding="utf-8")
        assert "~/.claude/skills/" not in content

    def test_builtin_file_count(self, tmp_path):
        """Each target installs exactly 4 files (main + 3 references)."""
        from lap.cli.main import _install_builtin_skill
        for target in ("claude", "cursor", "codex"):
            dest = tmp_path / target
            _install_builtin_skill("lap", target, str(dest))
            files = list(dest.rglob("*"))
            file_count = sum(1 for f in files if f.is_file())
            assert file_count == 4, f"{target} should have 4 files, got {file_count}"


# -- Target: Codex ---------------------------------------------------------------

class TestCodexTarget:
    """Tests for --target codex output."""

    def test_codex_file_extension(self, minimal_spec):
        """Codex target produces SKILL.md (same as Claude)."""
        result = generate_skill(minimal_spec, SkillOptions(target="codex"))
        assert "SKILL.md" in result.file_map
        assert result.main_file == "SKILL.md"

    def test_codex_frontmatter_has_name(self, minimal_spec):
        """Codex frontmatter has name field."""
        result = generate_skill(minimal_spec, SkillOptions(target="codex"))
        md = result.file_map["SKILL.md"]
        parts = md.split("---", 2)
        frontmatter = parts[1]
        assert "name:" in frontmatter

    def test_codex_frontmatter_has_generator(self, minimal_spec):
        """Codex frontmatter has generator: lapsh."""
        result = generate_skill(minimal_spec, SkillOptions(target="codex"))
        md = result.file_map["SKILL.md"]
        parts = md.split("---", 2)
        frontmatter = parts[1]
        assert "generator: lapsh" in frontmatter

    def test_codex_frontmatter_has_version(self, minimal_spec):
        """Codex frontmatter has version field."""
        result = generate_skill(minimal_spec, SkillOptions(target="codex"))
        md = result.file_map["SKILL.md"]
        parts = md.split("---", 2)
        frontmatter = parts[1]
        assert "version:" in frontmatter

    def test_codex_frontmatter_no_always_apply(self, minimal_spec):
        """Codex frontmatter should NOT have alwaysApply (unlike Cursor)."""
        result = generate_skill(minimal_spec, SkillOptions(target="codex"))
        md = result.file_map["SKILL.md"]
        parts = md.split("---", 2)
        frontmatter = parts[1]
        assert "alwaysApply" not in frontmatter

    def test_codex_reference_file_present(self, minimal_spec):
        """Codex target includes references/api-spec.lap."""
        result = generate_skill(minimal_spec, SkillOptions(target="codex"))
        assert "references/api-spec.lap" in result.file_map

    def test_codex_body_differs_only_in_cli(self, minimal_spec):
        """Codex vs Claude body identical except CLI section."""
        import re
        claude = generate_skill(minimal_spec, SkillOptions(target="claude"))
        codex = generate_skill(minimal_spec, SkillOptions(target="codex"))
        claude_body = claude.file_map[claude.main_file].split("---", 2)[2]
        codex_body = codex.file_map[codex.main_file].split("---", 2)[2]
        assert claude_body != codex_body, "Bodies should differ"
        strip_cli = lambda s: re.sub(r"## CLI\n[\s\S]*?(?=\n## |\Z)", "", s)
        assert strip_cli(claude_body) == strip_cli(codex_body), "Only CLI section should differ"

    def test_codex_cli_has_curl(self, minimal_spec):
        """Codex CLI section contains curl commands."""
        result = generate_skill(minimal_spec, SkillOptions(target="codex"))
        md = result.file_map["SKILL.md"]
        assert "curl" in md

    def test_codex_cli_has_registry_urls(self, minimal_spec):
        """Codex CLI section references registry API endpoints."""
        result = generate_skill(minimal_spec, SkillOptions(target="codex"))
        md = result.file_map["SKILL.md"]
        assert "registry.lap.sh/v1/apis/" in md
        assert "registry.lap.sh/v1/search" in md

    def test_codex_cli_has_npx_fallback(self, minimal_spec):
        """Codex CLI section includes npx as fallback."""
        result = generate_skill(minimal_spec, SkillOptions(target="codex"))
        md = result.file_map["SKILL.md"]
        assert "npx @lap-platform/lapsh" in md

    def test_claude_cli_no_curl(self, minimal_spec):
        """Claude CLI section does NOT have curl commands."""
        result = generate_skill(minimal_spec, SkillOptions(target="claude"))
        md = result.file_map["SKILL.md"]
        assert "curl" not in md

    def test_cursor_cli_no_curl(self, minimal_spec):
        """Cursor CLI section does NOT have curl commands."""
        result = generate_skill(minimal_spec, SkillOptions(target="cursor"))
        md = result.file_map[result.main_file]
        assert "curl" not in md
