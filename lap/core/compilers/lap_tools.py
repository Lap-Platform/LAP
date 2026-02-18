#!/usr/bin/env python3
"""
LAP Compiler — Various tool manifest formats → LAP

Supports:
  - MCP tool manifests (JSON)
  - OpenClaw SKILL.md files
  - Generic JSON tool definitions
"""

import json
import re
from pathlib import Path
from typing import Optional

from lap.core.formats.lap_tools import LAPToolSpec, LAPToolBundle, ToolParam, ToolOutput, ToolExample


# ── Type Mapping ────────────────────────────────────────────────────

_JSON_TYPE_MAP = {
    "string": "str",
    "integer": "int",
    "number": "num",
    "boolean": "bool",
    "object": "map",
    "array": "list",
    "null": "null",
}


def _map_type(json_type: str, fmt: str = "", items: Optional[dict] = None) -> str:
    """Map JSON Schema type to LAP compact type."""
    base = _JSON_TYPE_MAP.get(json_type, json_type or "any")
    if fmt:
        base = f"{base}({fmt})"
    if json_type == "array" and items:
        inner = _map_type(items.get("type", "any"), items.get("format", ""))
        return f"[{inner}]"
    return base


# ── MCP Compiler ────────────────────────────────────────────────────

def compile_mcp_tool(tool: dict) -> LAPToolSpec:
    """Compile a single MCP tool definition to LAP."""
    name = tool.get("name", "unknown")
    desc = tool.get("description", "")
    schema = tool.get("inputSchema") or tool.get("input_schema", {})

    inputs = []
    required_names = set(schema.get("required", []))
    properties = schema.get("properties", {})

    for pname, pschema in properties.items():
        ptype = _map_type(
            pschema.get("type", "any"),
            pschema.get("format", ""),
            pschema.get("items"),
        )
        inputs.append(ToolParam(
            name=pname,
            type=ptype,
            required=pname in required_names,
            description=pschema.get("description", ""),
            enum=pschema.get("enum", []),
            default=str(pschema["default"]) if "default" in pschema else None,
        ))

    return LAPToolSpec(name=name, description=desc, inputs=inputs)


def compile_mcp_manifest(manifest: dict) -> LAPToolBundle:
    """Compile a full MCP server manifest (with multiple tools) to LAP."""
    server_name = manifest.get("name", manifest.get("server", {}).get("name", ""))
    server_desc = manifest.get("description", manifest.get("server", {}).get("description", ""))
    tools_list = manifest.get("tools", [])

    tools = [compile_mcp_tool(t) for t in tools_list]
    return LAPToolBundle(name=server_name, description=server_desc, tools=tools)


def compile_mcp_file(path: str) -> LAPToolBundle:
    """Compile an MCP manifest JSON file."""
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if isinstance(data, list):
        # Raw list of tools
        tools = [compile_mcp_tool(t) for t in data]
        return LAPToolBundle(name=Path(path).stem, tools=tools)
    return compile_mcp_manifest(data)


# ── OpenClaw SKILL.md Compiler ──────────────────────────────────────

def compile_skill_md(text: str, source: str = "") -> LAPToolSpec:
    """Compile an OpenClaw SKILL.md file to LAP."""
    name = ""
    desc = ""
    tags = []
    auth = "none"
    requires = []
    inputs = []
    examples = []

    # Parse YAML frontmatter if present
    frontmatter = {}
    body = text
    fm_match = re.match(r'^---\s*\n(.*?)\n---\s*\n', text, re.DOTALL)
    if fm_match:
        fm_text = fm_match.group(1)
        body = text[fm_match.end():]
        # Simple YAML parsing for key: value pairs
        for fm_line in fm_text.split("\n"):
            kv = re.match(r'^(\w[\w-]*)\s*:\s*"?(.+?)"?\s*$', fm_line.strip())
            if kv:
                frontmatter[kv.group(1)] = kv.group(2)
        if "name" in frontmatter:
            name = frontmatter["name"]
        if "description" in frontmatter:
            desc = frontmatter["description"]

    lines = body.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Extract name from first H1
        if not name and line.startswith("# "):
            name = line[2:].strip()
            # Clean common suffixes
            for suffix in [" Skill", " Tool", " Plugin"]:
                if name.endswith(suffix):
                    name = name[:-len(suffix)]
            name = re.sub(r'[^a-zA-Z0-9_-]', '-', name.lower()).strip('-')

        # Extract description from first paragraph after title
        elif not desc and name and line and not line.startswith("#") and not line.startswith("-"):
            desc = line

        # Tags from "Tags:" or "Categories:" lines
        elif re.match(r'^(?:tags|categories)\s*:', line, re.IGNORECASE):
            tag_text = line.split(":", 1)[1].strip()
            tags = [t.strip().lower() for t in tag_text.split(",") if t.strip()]

        # Auth from "Auth:" or "Authentication:" lines
        elif re.match(r'^(?:auth|authentication)\s*:', line, re.IGNORECASE):
            auth_text = line.split(":", 1)[1].strip().lower()
            if "oauth" in auth_text:
                auth = "oauth"
            elif "api" in auth_text or "key" in auth_text:
                auth = "apikey"
            elif "token" in auth_text:
                auth = "token"

        # Requirements from "Requires:" or dependency sections
        elif re.match(r'^(?:requires|dependencies)\s*:', line, re.IGNORECASE):
            req_text = line.split(":", 1)[1].strip()
            if req_text:
                requires.append(req_text)

        # Parameters from "## Parameters" or "## Inputs" sections
        elif re.match(r'^##\s+(?:parameters|inputs|arguments)', line, re.IGNORECASE):
            i += 1
            while i < len(lines):
                pline = lines[i].strip()
                if pline.startswith("#"):
                    i -= 1
                    break
                # Parse "- `name` (type): description" or "- name: type - description"
                pm = re.match(r'^[-*]\s+`?(\w+)`?\s*[:(]\s*(\w+)\)?\s*[-:]?\s*(.*)', pline)
                if pm:
                    pname, ptype, pdesc = pm.group(1), pm.group(2), pm.group(3)
                    required = "required" in pdesc.lower() or "optional" not in pdesc.lower()
                    inputs.append(ToolParam(
                        name=pname,
                        type=_JSON_TYPE_MAP.get(ptype.lower(), ptype),
                        required=required,
                        description=pdesc.rstrip('.').strip(),
                    ))
                i += 1

        # Examples from "## Example" sections
        elif re.match(r'^##\s+(?:examples?|usage)', line, re.IGNORECASE):
            i += 1
            in_code = False
            code_lines = []
            while i < len(lines):
                eline = lines[i]
                if eline.strip().startswith("#") and not in_code:
                    i -= 1
                    break
                if eline.strip().startswith("```"):
                    if in_code:
                        examples.append(ToolExample(input_text=" ".join(code_lines)))
                        code_lines = []
                    in_code = not in_code
                elif in_code:
                    code_lines.append(eline.strip())
                i += 1

        i += 1

    # If no examples found from ## Example sections, extract from code blocks in body
    if not examples:
        code_blocks = re.findall(r'```(?:bash|json|sh)?\n(.*?)```', body, re.DOTALL)
        for block in code_blocks[:4]:  # Limit to 4 examples
            snippet = block.strip()
            if snippet and len(snippet) < 300:
                examples.append(ToolExample(input_text=snippet.split("\n")[0]))

    return LAPToolSpec(
        name=name or "unknown",
        description=desc,
        auth=auth,
        tags=tags,
        inputs=inputs,
        examples=examples,
        requires=requires,
        source=source,
    )


def compile_skill_file(path: str) -> LAPToolSpec:
    """Compile an OpenClaw SKILL.md file from disk."""
    text = Path(path).read_text(encoding='utf-8')
    return compile_skill_md(text, source=path)


# ── Generic JSON Tool Compiler ──────────────────────────────────────

def compile_generic_json(tool: dict) -> LAPToolSpec:
    """Compile a generic JSON tool definition to LAP.
    
    Expects a dict with keys like: name, description, parameters/inputs,
    returns/outputs, auth, tags, etc.
    """
    name = tool.get("name", "unknown")
    desc = tool.get("description", "")
    auth = tool.get("auth", "none")
    tags = tool.get("tags", [])
    source = tool.get("source", tool.get("url", ""))
    requires = tool.get("requires", tool.get("dependencies", []))
    if isinstance(requires, str):
        requires = [requires]

    # Parse inputs from parameters/inputs/input_schema
    inputs = []
    params = tool.get("parameters", tool.get("inputs", tool.get("input_schema", {})))
    if isinstance(params, dict):
        required_names = set(params.get("required", []))
        properties = params.get("properties", params)
        # If it's a flat dict of param definitions
        if not any(k in properties for k in ("required", "properties", "type")):
            for pname, pdef in properties.items():
                if isinstance(pdef, dict):
                    inputs.append(ToolParam(
                        name=pname,
                        type=_map_type(pdef.get("type", "any"), pdef.get("format", ""), pdef.get("items")),
                        required=pname in required_names,
                        description=pdef.get("description", ""),
                        enum=pdef.get("enum", []),
                    ))
        else:
            for pname, pdef in properties.get("properties", {}).items():
                if isinstance(pdef, dict):
                    inputs.append(ToolParam(
                        name=pname,
                        type=_map_type(pdef.get("type", "any"), pdef.get("format", ""), pdef.get("items")),
                        required=pname in required_names,
                        description=pdef.get("description", ""),
                        enum=pdef.get("enum", []),
                    ))
    elif isinstance(params, list):
        for p in params:
            inputs.append(ToolParam(
                name=p.get("name", ""),
                type=_map_type(p.get("type", "any")),
                required=p.get("required", True),
                description=p.get("description", ""),
            ))

    # Parse outputs
    outputs = []
    out_schema = tool.get("returns", tool.get("outputs", tool.get("output_schema", {})))
    if isinstance(out_schema, dict):
        for fname, fdef in out_schema.items():
            if isinstance(fdef, dict):
                outputs.append(ToolOutput(
                    name=fname,
                    type=_map_type(fdef.get("type", "any")),
                    description=fdef.get("description", ""),
                ))
            elif isinstance(fdef, str):
                outputs.append(ToolOutput(name=fname, type=fdef))

    return LAPToolSpec(
        name=name,
        description=desc,
        auth=auth,
        tags=tags if isinstance(tags, list) else [tags],
        inputs=inputs,
        outputs=outputs,
        requires=requires,
        source=source,
    )


def compile_generic_file(path: str) -> LAPToolSpec:
    """Compile a generic JSON tool definition file."""
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    return compile_generic_json(data)
