"""
Skill compiler -- generates Claude Code skill directories from LAPSpec objects.

Layer 1 is fully mechanical (parser-based, no LLM). Layer 2 (optional) uses
LLM enhancement at publish time (see skill_llm.py).
"""

import re
from collections import OrderedDict
from dataclasses import dataclass
from typing import Optional

from lap.core.formats.lap import LAPSpec, Endpoint, _group_name
from lap.core.utils import count_tokens


SKILL_MD_TOKEN_BUDGET = 3000


@dataclass
class SkillOptions:
    layer: int = 1           # 1 = mechanical, 2 = LLM-enhanced
    lean: bool = True
    clawhub: bool = False    # include metadata.openclaw block
    version: str = "1.0.0"   # skill version in frontmatter


@dataclass
class SkillOutput:
    name: str                # skill directory name (slugified api name)
    file_map: dict[str, str] # {relative_path: content_string}
    token_count: int         # total tokens across all files
    endpoint_count: int


def generate_skill(spec: LAPSpec, options: Optional[SkillOptions] = None) -> SkillOutput:
    """Generate a Claude Code skill directory from a LAPSpec.

    Returns a SkillOutput with file_map containing all files to write.
    """
    if options is None:
        options = SkillOptions()

    if not spec.endpoints:
        raise ValueError("Cannot generate skill from spec with no endpoints.")

    name = _slugify(spec.api_name)
    file_map = {}

    # SKILL.md -- main skill file
    skill_md = _generate_skill_md(spec, options)
    file_map["SKILL.md"] = skill_md

    # references/api-spec.lap -- lean LAP spec
    lean_spec = spec.to_lap(lean=options.lean)
    file_map["references/api-spec.lap"] = lean_spec

    total_tokens = sum(count_tokens(content) for content in file_map.values())

    return SkillOutput(
        name=name,
        file_map=file_map,
        token_count=total_tokens,
        endpoint_count=len(spec.endpoints),
    )


def _slugify(name: str) -> str:
    """Convert API name to a valid skill directory name."""
    slug = name.lower().replace(" ", "-").replace("_", "-")
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


def _generate_frontmatter(spec: LAPSpec, options: SkillOptions) -> str:
    """Generate YAML frontmatter with name, description, version, and generator."""
    name = _slugify(spec.api_name)
    groups = _get_groups(spec)
    top_groups = list(groups.keys())[:3]
    group_text = ", ".join(top_groups) if top_groups else "API operations"
    ep_count = len(spec.endpoints)

    desc = (
        f"{spec.api_name} API skill. "
        f"Use when working with {spec.api_name} for {group_text}. "
        f"Covers {ep_count} endpoint{'s' if ep_count != 1 else ''}."
    )

    desc_escaped = desc.replace('"', '\\"')
    lines = [
        "---",
        f"name: {name}",
        f'description: "{desc_escaped}"',
        f"version: {options.version}",
        "generator: lap-platform",
    ]

    if options.clawhub and spec.auth_scheme:
        env_var = _slugify(spec.api_name).upper().replace("-", "_") + "_API_KEY"
        lines.append("metadata:")
        lines.append("  openclaw:")
        lines.append("    requires:")
        lines.append("      env:")
        lines.append(f"        - {env_var}")

    lines.append("---")
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
