#!/usr/bin/env python3
"""
DocLean Compiler — OpenAPI → DocLean format

Usage:
    python compiler.py <openapi-spec.yaml> [-o output.doclean]
"""

import argparse
import json
import sys
from pathlib import Path

import yaml

from core.formats.doclean import DocLeanSpec, Endpoint, Param, ResponseSchema, ResponseField, ErrorSchema


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
        param = Param(
            name=p["name"],
            type=extract_type(schema, spec),
            required=p.get("required", False),
            description=p.get("description", "").replace('\n', ' ').strip(),
            enum=schema.get("enum", []),
            default=str(schema["default"]) if "default" in schema else None,
        )

        if param.required:
            required.append(param)
        else:
            optional.append(param)

    return required, optional


def extract_request_body(body: dict, spec: dict) -> list:
    """Extract params from request body."""
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

        params.append(Param(
            name=name,
            type=extract_type(schema, spec),
            required=name in required_names,
            description=schema.get("description", "").replace('\n', ' ').strip(),
            enum=schema.get("enum", []),
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

        desc = resp.get("description", "")

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


def compile_openapi(spec_path: str) -> DocLeanSpec:
    """Compile an OpenAPI spec to DocLean format."""
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

    doclean = DocLeanSpec(
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

                endpoint = Endpoint(
                    method=method,
                    path=path_str,
                    summary=(details.get("summary") or details.get("description") or "").strip().split('\n')[0].strip(),
                    required_params=req_params,
                    optional_params=opt_params,
                    request_body=body_params,
                    response_schemas=response_schemas,
                    error_schemas=error_schemas,
                )
                doclean.endpoints.append(endpoint)

    return doclean


def main():
    parser = argparse.ArgumentParser(description="Compile OpenAPI spec to DocLean format")
    parser.add_argument("spec", help="Path to OpenAPI spec (YAML/JSON)")
    parser.add_argument("-o", "--output", help="Output file (default: stdout)")
    parser.add_argument("--verbose", action="store_true", help="Also output verbose version for comparison")
    parser.add_argument("--lean", action="store_true", help="Strip all description comments for maximum compression")
    args = parser.parse_args()

    doclean = compile_openapi(args.spec)
    result = doclean.to_doclean(lean=args.lean)

    if args.output:
        Path(args.output).write_text(result)
        print(f"✅ Compiled to {args.output}")
        if args.verbose:
            verbose_path = args.output.replace(".doclean", ".verbose.md")
            Path(verbose_path).write_text(doclean.to_original_text())
            print(f"📝 Verbose version: {verbose_path}")
    else:
        print(result)


if __name__ == "__main__":
    main()
