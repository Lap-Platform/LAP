#!/usr/bin/env python3
"""
LAP Compiler — OpenAPI → LAP format

Usage:
    python compiler.py <openapi-spec.yaml> [-o output.lap]
"""

import argparse
import datetime
import json
import sys
from pathlib import Path

import yaml

from core.formats.lap import LAPSpec, Endpoint, Param, ResponseSchema, ResponseField, ErrorSchema


def resolve_ref(spec: dict, ref: str, _visited: set = None) -> dict:
    """Resolve a $ref pointer in an OpenAPI spec with cycle detection."""
    if _visited is None:
        _visited = set()
    if ref in _visited:
        raise ValueError(f"Circular $ref detected: {ref}")
    _visited.add(ref)
    parts = ref.lstrip("#/").split("/")
    node = spec
    for part in parts:
        node = node.get(part, {})
    # If the resolved node itself contains a $ref, resolve it too
    if isinstance(node, dict) and "$ref" in node:
        return resolve_ref(spec, node["$ref"], _visited)
    return node


def extract_type(schema: dict, spec: dict) -> str:
    """Extract a concise type string from an OpenAPI schema."""
    if "$ref" in schema:
        schema = resolve_ref(spec, schema["$ref"])

    t = schema.get("type", "any")
    # OpenAPI 3.1 allows type as a list, e.g. ["integer", "null"]
    if isinstance(t, list):
        non_null = [x for x in t if x != "null"]
        t = non_null[0] if non_null else "any"
    fmt = schema.get("format", "")

    if t == "string" and fmt:
        return f"str({fmt})"
    if t == "string":
        return "str"
    if t == "integer":
        return f"int({fmt})" if fmt else "int"
    if t == "number":
        return f"num({fmt})" if fmt else "num"
    if t == "boolean":
        return "bool"
    if t == "array":
        items_type = extract_type(schema.get("items", {}), spec)
        return f"[{items_type}]"
    if t == "object":
        return "map"
    return t


def extract_type_inline(schema: dict, spec: dict, depth: int = 0, max_depth: int = 1) -> str:
    """Extract type string, inlining object properties up to max_depth.

    Never returns bare 'map' for objects with known properties.
    Uses '!' suffix on required nested field names.
    """
    if "$ref" in schema:
        schema = resolve_ref(spec, schema["$ref"])

    t = schema.get("type", "any")
    if isinstance(t, list):
        non_null = [x for x in t if x != "null"]
        t = non_null[0] if non_null else "any"

    if t == "object" and schema.get("properties") and depth < max_depth:
        props = schema.get("properties", {})
        required_names = set(schema.get("required", []))
        parts = []
        for prop_name, prop_schema in props.items():
            if "$ref" in prop_schema:
                prop_schema = resolve_ref(spec, prop_schema["$ref"])
            prop_type = extract_type_inline(prop_schema, spec, depth + 1, max_depth)
            req_marker = "!" if prop_name in required_names else ""
            parts.append(f"{prop_name}{req_marker}: {prop_type}")
        return f"map{{{', '.join(parts)}}}"

    if t == "array":
        items_schema = schema.get("items", {})
        items_type = extract_type_inline(items_schema, spec, depth, max_depth)
        return f"[{items_type}]"

    # Fall back to regular extract_type for scalars or objects at max depth
    return extract_type(schema, spec)


def extract_params(param_list: list, spec: dict) -> tuple[list, list]:
    """Extract required and optional params from OpenAPI parameters."""
    required = []
    optional = []

    for p in param_list:
        if "$ref" in p:
            p = resolve_ref(spec, p["$ref"])

        if "name" not in p or not p["name"].strip():
            continue  # skip malformed params

        schema = p.get("schema", {})
        enum_vals = [v for v in schema.get("enum", []) if v is not None]
        param = Param(
            name=p["name"],
            type=extract_type(schema, spec),
            required=p.get("required", False),
            description=p.get("description", "").replace('\n', ' ').strip(),
            enum=enum_vals,
            default=str(schema["default"]) if "default" in schema else None,
        )

        if param.required:
            required.append(param)
        else:
            optional.append(param)

    return required, optional


def extract_request_body(body: dict, spec: dict) -> list:
    """Extract params from request body, inlining nested object schemas."""
    if not body:
        return []

    if "$ref" in body:
        body = resolve_ref(spec, body["$ref"])

    content = body.get("content", {})
    json_schema = content.get("application/json", {}).get("schema", {})

    if "$ref" in json_schema:
        json_schema = resolve_ref(spec, json_schema["$ref"])

    params = []
    required_names = set(json_schema.get("required", []))
    properties = json_schema.get("properties", {})

    for name, schema in properties.items():
        if not name.strip():
            continue
        if "$ref" in schema:
            schema = resolve_ref(spec, schema["$ref"])

        # Use inline expansion for object-type params to avoid bare 'map'
        type_str = extract_type_inline(schema, spec, depth=0, max_depth=1)

        enum_vals = [v for v in schema.get("enum", []) if v is not None]
        params.append(Param(
            name=name,
            type=type_str,
            required=name in required_names,
            description=schema.get("description", "").replace('\n', ' ').strip(),
            enum=enum_vals,
            default=str(schema["default"]) if "default" in schema else None,
        ))

    return params


def extract_response_fields(schema: dict, spec: dict, depth: int = 0, max_depth: int = 2, max_properties: int = 500) -> list:
    """Recursively extract typed fields from a response schema."""
    if "$ref" in schema:
        schema = resolve_ref(spec, schema["$ref"])

    fields = []
    properties = schema.get("properties", {})

    for count, (name, prop) in enumerate(properties.items()):
        if count >= max_properties:
            break
        if "$ref" in prop:
            prop = resolve_ref(spec, prop["$ref"])

        type_str = extract_type(prop, spec)
        nullable = prop.get("nullable", False) or "null" in str(prop.get("type", ""))

        children = []
        if prop.get("type") == "object" and depth < max_depth and prop.get("properties"):
            children = extract_response_fields(prop, spec, depth + 1, max_depth)

        fields.append(ResponseField(
            name=name,
            type=type_str,
            nullable=nullable,
            children=children,
        ))

    return fields


def extract_response_schemas(responses: dict, spec: dict) -> tuple:
    """Extract typed response and error schemas from OpenAPI responses."""
    response_schemas = []
    error_schemas = []

    for code, resp in responses.items():
        if "$ref" in resp:
            resp = resolve_ref(spec, resp["$ref"])

        desc = resp.get("description", "").replace('\n', ' ').strip()

        # Extract response body schema
        content = resp.get("content", {})
        json_content = content.get("application/json", {})
        schema = json_content.get("schema", {})

        if "$ref" in schema:
            schema = resolve_ref(spec, schema["$ref"])

        if code.startswith("2"):
            fields = extract_response_fields(schema, spec) if schema.get("properties") else []
            response_schemas.append(ResponseSchema(
                status_code=code,
                description=desc,
                fields=fields,
            ))
        elif code != "default":
            error_schemas.append(ErrorSchema(
                code=code,
                description=desc,
            ))

    return response_schemas, error_schemas


def extract_auth(spec: dict) -> str:
    """Extract auth scheme from security definitions."""
    schemes = spec.get("components", {}).get("securitySchemes", {})
    security = spec.get("security", [])

    if not schemes:
        return ""

    parts = []
    for scheme_name, scheme in schemes.items():
        t = scheme.get("type", "")
        if t == "http":
            parts.append(f"Bearer {scheme.get('scheme', 'token')}")
        elif t == "apiKey":
            parts.append(f"ApiKey {scheme.get('name', 'key')} in {scheme.get('in', 'header')}")
        elif t == "oauth2":
            parts.append("OAuth2")
        else:
            parts.append(t)

    return " | ".join(parts)


def _json_default(obj):
    """Handle non-serializable types in OpenAPI examples (datetime, date, etc.)."""
    if isinstance(obj, (datetime.datetime, datetime.date)):
        return obj.isoformat()
    return str(obj)


def extract_request_example(body: dict, spec: dict) -> str:
    """Extract a request example from OpenAPI requestBody as compact JSON."""
    if not body:
        return ""

    if "$ref" in body:
        body = resolve_ref(spec, body["$ref"])

    content = body.get("content", {})
    json_content = content.get("application/json", {})

    # Direct example on media type
    example = json_content.get("example")
    if example:
        return json.dumps(example, separators=(',', ':'), default=_json_default)

    # Named examples
    examples = json_content.get("examples", {})
    if examples:
        first = next(iter(examples.values()), {})
        if isinstance(first, dict):
            if "$ref" in first:
                first = resolve_ref(spec, first["$ref"])
            value = first.get("value")
            if value:
                return json.dumps(value, separators=(',', ':'), default=_json_default)

    return ""


# Threshold: a body param must appear in this fraction of body-having
# endpoints to be considered "common" and extracted into @common_fields.
_COMMON_FIELD_THRESHOLD = 0.95


def compile_openapi(spec_path: str) -> LAPSpec:
    """Compile an OpenAPI spec to LAP format."""
    path = Path(spec_path)
    file_size = path.stat().st_size
    if file_size > 50 * 1024 * 1024:
        raise ValueError(f"OpenAPI spec too large: {file_size} bytes (max 50MB)")
    raw = path.read_text()

    if path.suffix in (".yaml", ".yml"):
        spec = yaml.safe_load(raw)
    else:
        spec = json.loads(raw)

    if not isinstance(spec, dict):
        raise ValueError("Invalid OpenAPI spec: expected a YAML mapping")

    info = spec.get("info", {})
    servers = spec.get("servers", [])
    base_url = servers[0]["url"] if servers else ""

    lap = LAPSpec(
        api_name=info.get("title", path.stem),
        base_url=base_url,
        version=info.get("version", ""),
        auth_scheme=extract_auth(spec),
    )

    paths = spec.get("paths", {})
    for path_str, methods in paths.items():
        for method, details in methods.items():
            if method in ("get", "post", "put", "patch", "delete", "head", "options"):
                req_params, opt_params = extract_params(
                    details.get("parameters", []), spec
                )
                body_params = extract_request_body(
                    details.get("requestBody", {}), spec
                )

                response_schemas, error_schemas = extract_response_schemas(
                    details.get("responses", {}), spec
                )

                # Extract request example
                example = extract_request_example(
                    details.get("requestBody", {}), spec
                )

                endpoint = Endpoint(
                    method=method,
                    path=path_str,
                    summary=(details.get("summary") or details.get("description") or "").strip().split('\n')[0].strip(),
                    required_params=req_params,
                    optional_params=opt_params,
                    request_body=body_params,
                    response_schemas=response_schemas,
                    error_schemas=error_schemas,
                    example_request=example,
                )
                lap.endpoints.append(endpoint)

    # Deduplicate common fields -- any param (body, query, path, header)
    # appearing in >95% of all endpoints gets extracted into @common_fields.
    if len(lap.endpoints) > 5:
        from collections import Counter
        name_counts = Counter()
        for ep in lap.endpoints:
            seen = set()
            for p in ep.request_body + ep.required_params + ep.optional_params:
                if p.name not in seen:
                    name_counts[p.name] += 1
                    seen.add(p.name)

        threshold = len(lap.endpoints) * _COMMON_FIELD_THRESHOLD
        common_names = {name for name, count in name_counts.items()
                        if count >= threshold}

        if common_names:
            # Collect param objects from first endpoint that has each
            common_params = []
            found = set()
            for ep in lap.endpoints:
                for p in ep.request_body + ep.required_params + ep.optional_params:
                    if p.name in common_names and p.name not in found:
                        common_params.append(p)
                        found.add(p.name)
            # Strip from all endpoints
            for ep in lap.endpoints:
                ep.request_body = [p for p in ep.request_body
                                  if p.name not in common_names]
                ep.required_params = [p for p in ep.required_params
                                     if p.name not in common_names]
                ep.optional_params = [p for p in ep.optional_params
                                     if p.name not in common_names]
            lap.common_fields = common_params

    return lap


def main():
    parser = argparse.ArgumentParser(description="Compile OpenAPI spec to LAP format")
    parser.add_argument("spec", help="Path to OpenAPI spec (YAML/JSON)")
    parser.add_argument("-o", "--output", help="Output file (default: stdout)")
    parser.add_argument("--verbose", action="store_true", help="Also output verbose version for comparison")
    parser.add_argument("--lean", action="store_true", help="Strip all description comments for maximum compression")
    args = parser.parse_args()

    lap = compile_openapi(args.spec)
    result = lap.to_lap(lean=args.lean)

    if args.output:
        Path(args.output).write_text(result)
        print(f"✅ Compiled to {args.output}")
        if args.verbose:
            verbose_path = args.output.replace(".lap", ".verbose.md")
            Path(verbose_path).write_text(lap.to_original_text())
            print(f"📝 Verbose version: {verbose_path}")
    else:
        print(result)


if __name__ == "__main__":
    main()
