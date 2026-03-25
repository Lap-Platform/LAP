"""
Skill compiler -- generates Claude Code skill directories from LAPSpec objects.

Layer 1 is fully mechanical (parser-based, no LLM). Layer 2 (optional) uses
LLM enhancement at publish time (see skill_llm.py).
"""

import re
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from lap.core.formats.lap import LAPSpec, Endpoint, _group_name
from lap.core.utils import count_tokens, AUTH_PARAM_NAMES


# Parameter names that strongly suggest authentication (safety net)
_AUTH_PARAM_NAMES = AUTH_PARAM_NAMES | {"key"}

SKILL_MD_TOKEN_BUDGET = 3000
VALID_TARGETS = {"claude", "cursor", "codex"}


def detect_target() -> str:
    """Auto-detect IDE target from environment.

    Detection priority:
    1. TERM_PROGRAM env var (macOS/Linux -- set by IDE terminals)
    2. IDE-specific env vars (CURSOR_TRACE_ID, CURSOR_EDITOR, etc.)
    3. PATH entries containing IDE binary paths (cross-platform)
    4. .cursor project directory (walk up to .git root)
    5. ~/.cursor/ in home directory (Cursor installed on this machine)
    6. Codex env vars (CODEX_SANDBOX, CODEX_SESSION_ID)
    7. Codex in PATH or ~/.codex/ home directory
    8. Default: 'claude'
    """
    import os
    import shutil

    # 1. TERM_PROGRAM (macOS/Linux)
    term = os.environ.get("TERM_PROGRAM", "").lower()
    if "cursor" in term:
        return "cursor"

    # 2. IDE-specific env vars
    if os.environ.get("CURSOR_TRACE_ID") or os.environ.get("CURSOR_EDITOR"):
        return "cursor"

    # 3. PATH-based detection (works on Windows where TERM_PROGRAM is unset)
    path_env = os.environ.get("PATH", "").lower()
    if "cursor" in path_env and "codebin" in path_env:
        return "cursor"

    # 4. Project directory walk
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        if (parent / ".cursor").is_dir():
            return "cursor"
        if (parent / ".git").exists():
            break

    # 5. Home directory check (Cursor config exists)
    cursor_home = Path.home() / ".cursor"
    if cursor_home.is_dir():
        return "cursor"

    # 6. Codex env vars
    if os.environ.get("CODEX_SANDBOX") or os.environ.get("CODEX_SESSION_ID"):
        return "codex"

    # 7. Codex in PATH or home directory
    if shutil.which("codex"):
        return "codex"
    codex_home = Path.home() / ".codex"
    if codex_home.is_dir():
        return "codex"

    return "claude"


@dataclass
class SkillOptions:
    layer: int = 1           # 1 = mechanical, 2 = LLM-enhanced
    lean: bool = True
    clawhub: bool = False    # include metadata.openclaw block
    version: str = "1.0.0"   # skill version in frontmatter
    target: str = "claude"   # "claude" | "cursor" | "codex"


@dataclass
class SkillOutput:
    name: str                # skill directory name (slugified api name)
    main_file: str           # key into file_map for the main skill file
    file_map: dict[str, str] # {relative_path: content_string}
    token_count: int         # total tokens across all files
    endpoint_count: int


def generate_skill(spec: LAPSpec, options: Optional[SkillOptions] = None) -> SkillOutput:
    """Generate a Claude Code skill directory from a LAPSpec.

    Returns a SkillOutput with file_map containing all files to write.
    """
    if options is None:
        options = SkillOptions()

    if options.target not in VALID_TARGETS:
        raise ValueError(f"Unknown target '{options.target}'. Valid targets: {', '.join(sorted(VALID_TARGETS))}")

    if not spec.endpoints:
        raise ValueError("Cannot generate skill from spec with no endpoints.")

    name = _slugify(spec.api_name)
    file_map = {}

    # Main skill file -- extension depends on target
    skill_md = _generate_skill_md(spec, options)
    if options.target == "cursor":
        main_file = f"{name}.mdc"
    else:
        main_file = "SKILL.md"
    file_map[main_file] = skill_md

    # references/api-spec.lap -- lean LAP spec
    lean_spec = spec.to_lap(lean=options.lean)
    file_map["references/api-spec.lap"] = lean_spec

    total_tokens = sum(count_tokens(content) for content in file_map.values())

    return SkillOutput(
        name=name,
        main_file=main_file,
        file_map=file_map,
        token_count=total_tokens,
        endpoint_count=len(spec.endpoints),
    )


def _detect_auth_param(spec: LAPSpec) -> tuple[str, str] | None:
    """Safety net: detect auth-like parameters when spec.auth_scheme is empty.

    Scans common_fields first (most likely location after deduplication),
    then endpoint params. Returns (param_name, location_hint) or None.
    """
    # Check common_fields first (auth params usually appear everywhere)
    for p in spec.common_fields:
        if p.name.lower() in _AUTH_PARAM_NAMES:
            return (p.name, "common_fields")

    # Check endpoint params
    for ep in spec.endpoints:
        for p in ep.required_params + ep.optional_params + ep.request_body:
            if p.name.lower() in _AUTH_PARAM_NAMES:
                return (p.name, "parameter")

    return None


def _slugify(name: str) -> str:
    """Convert API name to a valid skill directory name."""
    slug = name.lower().replace(" ", "-").replace("_", "-").replace("/", "-").replace(".", "-")
    slug = "".join(c for c in slug if c.isalnum() or c == "-").strip("-")
    # Collapse repeated hyphens
    slug = re.sub(r"-+", "-", slug)
    return slug or "api"


def _generate_skill_md(spec: LAPSpec, options: SkillOptions) -> str:
    """Generate the main SKILL.md file."""
    parts = []

    # Frontmatter
    parts.append(_generate_frontmatter(spec, options))
    parts.append("")

    # Body
    parts.append(_generate_skill_body(spec))

    return "\n".join(parts)


def _build_description(spec: LAPSpec) -> str:
    """Build skill description text from spec metadata. Returns escaped string safe for YAML quoting."""
    groups = _get_groups(spec)
    top_groups = list(groups.keys())[:3]
    group_text = ", ".join(top_groups) if top_groups else "API operations"
    ep_count = len(spec.endpoints)

    # Strip trailing " API" (or bare "API") to avoid "API API" doubling
    display_name = spec.api_name
    if display_name.upper().endswith(" API"):
        display_name = display_name[:-4].rstrip()
    if not display_name or display_name.upper() == "API":
        display_name = spec.api_name  # fallback: use original name as-is

    if display_name.upper() == "API":
        desc = (
            f"API skill. "
            f"Use when working with this API for {group_text}. "
            f"Covers {ep_count} endpoint{'s' if ep_count != 1 else ''}."
        )
    else:
        desc = (
            f"{display_name} API skill. "
            f"Use when working with {display_name} for {group_text}. "
            f"Covers {ep_count} endpoint{'s' if ep_count != 1 else ''}."
        )
    return desc.replace('\\', '\\\\').replace('"', '\\"')


def _generate_frontmatter(spec: LAPSpec, options: SkillOptions) -> str:
    """Dispatch to target-specific frontmatter generator."""
    if options.target == "cursor":
        return _generate_cursor_frontmatter(spec)
    return _generate_claude_frontmatter(spec, options)


def _generate_claude_frontmatter(spec: LAPSpec, options: SkillOptions) -> str:
    """Generate Claude Code YAML frontmatter with name, description, version, and generator."""
    name = _slugify(spec.api_name)
    desc_escaped = _build_description(spec)
    lines = [
        "---",
        f"name: {name}",
        f'description: "{desc_escaped}"',
        f"version: {options.version}",
        "generator: lapsh",
    ]

    if options.clawhub and spec.auth_scheme:
        env_slug = _slugify(spec.api_name).upper().replace("-", "_")
        if env_slug.endswith("_API"):
            env_slug = env_slug[:-4]
        env_var = (env_slug or "API") + "_API_KEY"
        lines.append("metadata:")
        lines.append("  openclaw:")
        lines.append("    requires:")
        lines.append("      env:")
        lines.append(f"        - {env_var}")

    lines.append("---")
    return "\n".join(lines)


def _generate_cursor_frontmatter(spec: LAPSpec) -> str:
    """Generate Cursor .mdc frontmatter (description + alwaysApply)."""
    desc_escaped = _build_description(spec)
    lines = [
        "---",
        f'description: "{desc_escaped}"',
        "alwaysApply: false",
        "---",
    ]
    return "\n".join(lines)


def _generate_skill_body(spec: LAPSpec) -> str:
    """Generate the markdown body of SKILL.md."""
    sections = []

    # Title
    sections.append(f"# {spec.api_name}")
    if spec.version:
        sections.append(f"API version: {spec.version}")
    sections.append("")

    # Auth
    sections.append("## Auth")
    if spec.auth_scheme:
        sections.append(spec.auth_scheme)
    else:
        detected = _detect_auth_param(spec)
        if detected:
            name, _ = detected
            sections.append(f"Requires API key ({name} parameter)")
        else:
            sections.append("No authentication required.")
    sections.append("")

    # Base URL
    sections.append("## Base URL")
    sections.append(spec.base_url or "Not specified.")
    sections.append("")

    # Setup
    sections.append(_generate_setup(spec))
    sections.append("")

    # Endpoints by group
    sections.append(_generate_endpoint_catalog(spec))
    sections.append("")

    # Common Questions
    questions = _infer_question_mapping(spec)
    if questions:
        sections.append("## Common Questions")
        sections.append("")
        sections.append("Match user requests to endpoints in references/api-spec.lap. Key patterns:")
        for q in questions:
            sections.append(f"- {q}")
        sections.append("")

    # Response Tips
    sections.append(_generate_response_tips(spec))
    sections.append("")

    # CLI
    sections.append(_generate_cli_section(spec))
    sections.append("")

    # References
    sections.append("## References")
    sections.append("- Full spec: See references/api-spec.lap for complete endpoint details, parameter tables, and response schemas")
    sections.append("")

    # Attribution
    sections.append("> Generated from the official API spec by [LAP](https://lap.sh)")
    sections.append("")

    return "\n".join(sections)


def _generate_setup(spec: LAPSpec) -> str:
    """Generate a Setup section."""
    lines = ["## Setup"]

    # Step 1: Auth
    if spec.auth_scheme:
        auth_lower = spec.auth_scheme.lower()
        if "bearer" in auth_lower:
            lines.append("1. Set Authorization header with your Bearer token")
        elif "apikey" in auth_lower or "api_key" in auth_lower or "api-key" in auth_lower:
            lines.append("1. Set your API key in the appropriate header")
        else:
            lines.append(f"1. Configure auth: {spec.auth_scheme}")
    else:
        detected = _detect_auth_param(spec)
        if detected:
            name, _ = detected
            lines.append(f"1. Include your API key via the {name} parameter")
        else:
            lines.append("1. No auth setup needed")

    # Step 2: Find a list endpoint for verification
    list_ep = _find_first_endpoint(spec, "get", is_list=True)
    if list_ep:
        lines.append(f"2. GET {list_ep.path} -- verify access")
    else:
        get_ep = _find_first_endpoint(spec, "get")
        if get_ep:
            lines.append(f"2. GET {get_ep.path} -- verify access")

    # Step 3: Find a create endpoint
    create_ep = _find_first_endpoint(spec, "post")
    if create_ep:
        resource = _resource_from_path(create_ep.path)
        desc = f"create first {resource}" if resource else "create first resource"
        lines.append(f"3. POST {create_ep.path} -- {desc}")

    return "\n".join(lines)


def _generate_endpoint_catalog(spec: LAPSpec) -> str:
    """Generate the endpoint catalog grouped by resource."""
    groups = _get_groups(spec)
    ep_count = len(spec.endpoints)
    group_count = len(groups)
    lines = [
        "## Endpoints",
        "",
        f"{ep_count} endpoints across {group_count} groups. See references/api-spec.lap for full details.",
    ]

    for group_name, endpoints in groups.items():
        lines.append("")
        lines.append(f"### {group_name}")
        lines.append("| Method | Path | Description |")
        lines.append("|--------|------|-------------|")
        for ep in endpoints:
            method = ep.method.upper()
            desc = ep.summary or ""
            lines.append(f"| {method} | {ep.path} | {desc} |")

    return "\n".join(lines)


def _infer_question_mapping(spec: LAPSpec) -> list:
    """Infer natural language question-to-endpoint mappings mechanically.

    Algorithm:
    - GET  /resources           -> "List all {resources}?"
    - GET  /resources/{id}      -> "Get {resource} details?"
    - POST /resources           -> "Create a {resource}?"
    - PUT  /resources/{id}      -> "Update a {resource}?"
    - PATCH /resources/{id}     -> "Partially update a {resource}?"
    - DELETE /resources/{id}    -> "Delete a {resource}?"
    - GET  with q/query/search  -> "Search {resources}?"
    - Any endpoint with @auth   -> "How to authenticate?"
    """
    questions = []
    seen = set()
    has_auth_question = False

    for ep in spec.endpoints:
        method = ep.method.upper()
        path = ep.path

        # Check for search endpoint
        search_params = {"q", "query", "search"}
        ep_param_names = {p.name.lower() for p in ep.optional_params + ep.required_params}
        is_search = bool(search_params & ep_param_names)

        resource = _resource_from_path(path)
        singular = _singularize(resource) if resource else None
        has_id_param = bool(re.search(r'\{[^}]+\}', _last_segment_raw(path)))

        q = None

        if method == "GET" and is_search and resource:
            q = f'"Search {resource}?" -> {method} {path}'
        elif method == "GET" and not has_id_param and resource:
            q = f'"List all {resource}?" -> GET {path}'
        elif method == "GET" and has_id_param and singular:
            q = f'"Get {singular} details?" -> GET {path}'
        elif method == "POST" and not has_id_param and singular:
            q = f'"Create a {singular}?" -> POST {path}'
        elif method == "PUT" and has_id_param and singular:
            q = f'"Update a {singular}?" -> PUT {path}'
        elif method == "PATCH" and has_id_param and singular:
            q = f'"Partially update a {singular}?" -> PATCH {path}'
        elif method == "DELETE" and has_id_param and singular:
            q = f'"Delete a {singular}?" -> DELETE {path}'

        if q and q not in seen:
            seen.add(q)
            questions.append(q)

        # Auth question
        if not has_auth_question and (ep.auth or spec.auth_scheme):
            has_auth_question = True

    if has_auth_question:
        questions.append('"How to authenticate?" -> See Auth section')

    return questions


def _generate_response_tips(spec: LAPSpec) -> str:
    """Generate response interpretation tips."""
    tips = ["## Response Tips"]
    tips.append("- Check response schemas in references/api-spec.lap for field details")

    # Detect pagination patterns
    pagination_params = {"limit", "offset", "cursor", "page", "per_page", "page_size"}
    has_pagination = False
    for ep in spec.endpoints:
        param_names = {p.name.lower() for p in ep.optional_params + ep.required_params}
        if pagination_params & param_names:
            has_pagination = True
            break

    if has_pagination:
        tips.append("- List endpoints may support pagination; check for limit, offset, or cursor params")

    # Check for create/update return patterns
    has_create = any(ep.method.upper() == "POST" for ep in spec.endpoints)
    has_update = any(ep.method.upper() in ("PUT", "PATCH") for ep in spec.endpoints)
    if has_create or has_update:
        tips.append("- Create/update endpoints typically return the created/updated object")

    # Detect error patterns
    error_fields = set()
    for ep in spec.endpoints:
        for es in ep.error_schemas:
            if es.type:
                error_fields.add(es.type)
    if error_fields:
        tips.append(f"- Error responses use types: {', '.join(sorted(error_fields))}")

    return "\n".join(tips)


def _generate_cli_section(spec: LAPSpec) -> str:
    """Generate CLI section with npx commands for spec management."""
    slug = _slugify(spec.api_name)
    lines = [
        "## CLI",
        "",
        "```bash",
        "# Update this spec to the latest version",
        f"npx @lap-platform/lapsh get {slug} -o references/api-spec.lap",
        "",
        "# Search for related APIs",
        f"npx @lap-platform/lapsh search {slug}",
        "```",
    ]
    return "\n".join(lines)


# ── Helpers ──────────────────────────────────────────────────────────

def _get_groups(spec: LAPSpec) -> OrderedDict:
    """Group endpoints by resource name, preserving order."""
    groups = OrderedDict()
    for ep in spec.endpoints:
        gname = _group_name(ep.path)
        if gname not in groups:
            groups[gname] = []
        groups[gname].append(ep)
    return groups


def _find_first_endpoint(spec: LAPSpec, method: str, is_list: bool = False) -> Optional[Endpoint]:
    """Find the first endpoint matching a method. If is_list, prefer paths without {id}."""
    method = method.lower()
    if is_list:
        # First pass: prefer endpoints with NO path params at all
        for ep in spec.endpoints:
            if ep.method.lower() == method and '{' not in ep.path:
                return ep
        # Fall back: allow trailing {id} filter
        for ep in spec.endpoints:
            if ep.method.lower() != method:
                continue
            if re.search(r'\{[^}]+\}$', ep.path.rstrip('/')):
                continue
            return ep
        return None
    for ep in spec.endpoints:
        if ep.method.lower() == method:
            return ep
    return None


def _resource_from_path(path: str) -> str:
    """Extract resource name from the last non-parameter path segment."""
    parts = [p for p in path.strip('/').split('/') if p]
    # Walk backwards to find the last non-param segment
    for part in reversed(parts):
        if not part.startswith('{'):
            # Skip version prefixes
            if re.match(r'^v\d+$', part):
                continue
            return part
    return ""


def _last_segment_raw(path: str) -> str:
    """Get the raw last segment of a path."""
    parts = [p for p in path.strip('/').split('/') if p]
    return parts[-1] if parts else ""


def _singularize(word: str) -> str:
    """Naive singularization -- strips trailing 's' if present."""
    if not word:
        return word
    # Don't singularize words ending in ss, us, is (already singular or ambiguous)
    if word.endswith(("ss", "us", "is")):
        return word
    # Common API exceptions that break naive rules
    _EXCEPTIONS = {
        "responses": "response",
        "databases": "database",
        "purchases": "purchase",
        "analyses": "analysis",
        "releases": "release",
        "licenses": "license",
        "resources": "resource",
        "expenses": "expense",
        "invoices": "invoice",
        "messages": "message",
        "courses": "course",
    }
    if word in _EXCEPTIONS:
        return _EXCEPTIONS[word]
    if word.endswith("ies") and len(word) > 3:
        return word[:-3] + "y"
    # "oes" -> "o" (heroes -> hero, potatoes -> potato)
    if word.endswith("oes") and len(word) > 3:
        return word[:-2]
    # vowel+"ses" -> strip only "s" (cases -> case, bases -> base)
    if word.endswith("ses") and len(word) > 3:
        if len(word) > 3 and word[-4] in "aeiou":
            return word[:-1]
        return word[:-2]
    if word.endswith("s"):
        return word[:-1]
    return word
