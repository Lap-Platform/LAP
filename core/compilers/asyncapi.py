#!/usr/bin/env python3
"""
AsyncAPI → LAP Compiler

Compiles AsyncAPI 2.x and 3.x specifications into LAP format.
Channels map to endpoints with pub/sub methods.
"""

import json
from pathlib import Path
from typing import Optional

import yaml

from core.formats.lap import (
    LAPSpec, Endpoint, Param, ResponseSchema, ResponseField, ErrorSchema
)


def resolve_ref(spec: dict, ref: str, _visited: set = None) -> dict:
    """Resolve a $ref pointer in an AsyncAPI spec with cycle detection."""
    if _visited is None:
        _visited = set()
    if ref in _visited:
        raise ValueError(f"Circular $ref detected: {ref}")
    _visited.add(ref)
    parts = ref.lstrip("#/").split("/")
    node = spec
    for part in parts:
        node = node.get(part, {})
    if isinstance(node, dict) and "$ref" in node:
        return resolve_ref(spec, node["$ref"], _visited)
    return node


def _maybe_resolve(spec: dict, obj: dict) -> dict:
    """If obj has $ref, resolve it; otherwise return obj."""
    if not isinstance(obj, dict):
        return obj
    if "$ref" in obj:
        return resolve_ref(spec, obj["$ref"])
    return obj


def extract_type(schema: dict, spec: dict) -> str:
    """Extract a concise type string from a JSON Schema."""
    if not schema:
        return "any"
    schema = _maybe_resolve(spec, schema)

    t = schema.get("type", "any")
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


def extract_fields_from_schema(schema: dict, spec: dict, depth: int = 0, max_depth: int = 2) -> list:
    """Extract ResponseField list from a JSON Schema object."""
    schema = _maybe_resolve(spec, schema)
    fields = []
    properties = schema.get("properties", {})
    for name, prop in properties.items():
        prop = _maybe_resolve(spec, prop)
        type_str = extract_type(prop, spec)
        nullable = prop.get("nullable", False)
        children = []
        if prop.get("type") == "object" and depth < max_depth and prop.get("properties"):
            children = extract_fields_from_schema(prop, spec, depth + 1, max_depth)
        fields.append(ResponseField(name=name, type=type_str, nullable=nullable, children=children))
    return fields


def extract_params_from_schema(schema: dict, spec: dict) -> list:
    """Extract Param list from a JSON Schema (message payload or headers)."""
    schema = _maybe_resolve(spec, schema)
    if not schema or schema.get("type") != "object":
        return []

    params = []
    required_names = set(schema.get("required", []))
    for name, prop in schema.get("properties", {}).items():
        prop = _maybe_resolve(spec, prop)
        params.append(Param(
            name=name,
            type=extract_type(prop, spec),
            required=name in required_names,
            description=prop.get("description", "").replace("\n", " ").strip(),
            enum=prop.get("enum", []),
            default=str(prop["default"]) if "default" in prop else None,
        ))
    return params


def _extract_protocol_binding(bindings: dict, spec: dict) -> str:
    """Extract a short protocol binding summary string."""
    if not bindings:
        return ""
    bindings = _maybe_resolve(spec, bindings)
    parts = []
    for proto in ("mqtt", "kafka", "ws", "amqp", "http"):
        if proto in bindings:
            b = _maybe_resolve(spec, bindings[proto])
            details = []
            for key in ("qos", "retain", "groupId", "clientId", "acks", "key",
                        "topic", "exchange", "queue", "method", "type", "is", "durable"):
                if key in b:
                    val = b[key]
                    if isinstance(val, dict):
                        val = val.get("type", val)
                    details.append(f"{key}={val}")
            detail_str = f"({', '.join(details)})" if details else ""
            parts.append(f"{proto}{detail_str}")
    return "; ".join(parts)


def _detect_version(spec: dict) -> int:
    """Return 2 or 3 for AsyncAPI major version."""
    ver = spec.get("asyncapi", "2.0.0")
    return int(str(ver).split(".")[0])


def _get_servers_url(spec: dict) -> str:
    """Extract first server URL."""
    servers = spec.get("servers", {})
    if isinstance(servers, dict):
        for name, srv in servers.items():
            srv = _maybe_resolve(spec, srv)
            url = srv.get("url", "")
            protocol = srv.get("protocol", "")
            if url:
                if "://" not in url and protocol:
                    return f"{protocol}://{url}"
                return url
    return ""


def _get_protocol(spec: dict) -> str:
    """Extract primary protocol from servers."""
    servers = spec.get("servers", {})
    if isinstance(servers, dict):
        for name, srv in servers.items():
            srv = _maybe_resolve(spec, srv)
            return srv.get("protocol", "")
    return ""


def _compile_message(msg: dict, spec: dict) -> tuple:
    """Compile a message object into (params, headers_params, summary, response_fields).
    
    Returns (payload_params, header_params, summary, response_fields).
    """
    msg = _maybe_resolve(spec, msg)
    summary = msg.get("summary", msg.get("name", msg.get("description", ""))).strip()
    if isinstance(summary, str):
        summary = summary.split("\n")[0].strip()

    # Payload
    payload = msg.get("payload", {})
    payload = _maybe_resolve(spec, payload)
    payload_params = extract_params_from_schema(payload, spec)
    response_fields = extract_fields_from_schema(payload, spec)

    # Headers
    headers = msg.get("headers", {})
    headers = _maybe_resolve(spec, headers)
    header_params = extract_params_from_schema(headers, spec)

    return payload_params, header_params, summary, response_fields


def _compile_v2(spec: dict) -> LAPSpec:
    """Compile AsyncAPI 2.x spec."""
    info = spec.get("info", {})
    lap = LAPSpec(
        api_name=info.get("title", "AsyncAPI"),
        base_url=_get_servers_url(spec),
        version=info.get("version", ""),
        auth_scheme=_get_protocol(spec),
    )

    channels = spec.get("channels", {})
    for channel_name, channel_def in channels.items():
        channel_def = _maybe_resolve(spec, channel_def)
        bindings_str = _extract_protocol_binding(channel_def.get("bindings", {}), spec)
        parameters = channel_def.get("parameters", {})

        # Channel parameters become path params
        channel_params = []
        for pname, pdef in parameters.items():
            pdef = _maybe_resolve(spec, pdef)
            schema = pdef.get("schema", {})
            channel_params.append(Param(
                name=pname,
                type=extract_type(schema, spec),
                required=True,
                description=pdef.get("description", "").replace("\n", " ").strip(),
            ))

        for operation in ("subscribe", "publish"):
            op_def = channel_def.get(operation)
            if not op_def:
                continue
            op_def = _maybe_resolve(spec, op_def)

            method = "SUB" if operation == "subscribe" else "PUB"
            op_summary = (op_def.get("summary") or op_def.get("description") or "").strip().split("\n")[0]

            # Merge channel + operation bindings
            op_bindings_str = _extract_protocol_binding(op_def.get("bindings", {}), spec)
            combined_bindings = bindings_str or op_bindings_str

            message = op_def.get("message", {})
            # Handle oneOf messages
            if "oneOf" in message:
                messages = message["oneOf"]
            else:
                messages = [message]

            for msg in messages:
                payload_params, header_params, msg_summary, response_fields = _compile_message(msg, spec)
                summary = op_summary or msg_summary

                required = [p for p in payload_params if p.required] + channel_params
                optional = [p for p in payload_params if not p.required]

                # Headers as optional params with "header:" prefix
                for hp in header_params:
                    hp.name = f"header:{hp.name}"
                    optional.append(hp)

                response_schemas = []
                if response_fields:
                    response_schemas.append(ResponseSchema(
                        status_code=method,
                        description="message payload",
                        fields=response_fields,
                    ))

                desc_parts = [summary] if summary else []
                if combined_bindings:
                    desc_parts.append(f"[{combined_bindings}]")

                endpoint = Endpoint(
                    method=method,
                    path=channel_name,
                    summary=" ".join(desc_parts),
                    required_params=required,
                    optional_params=optional,
                    response_schemas=response_schemas,
                )
                lap.endpoints.append(endpoint)

    return lap


def _compile_v3(spec: dict) -> LAPSpec:
    """Compile AsyncAPI 3.x spec."""
    info = spec.get("info", {})
    lap = LAPSpec(
        api_name=info.get("title", "AsyncAPI"),
        base_url=_get_servers_url(spec),
        version=info.get("version", ""),
        auth_scheme=_get_protocol(spec),
    )

    # In v3, operations are top-level and reference channels
    channels = spec.get("channels", {})
    operations = spec.get("operations", {})

    if operations:
        for op_id, op_def in operations.items():
            op_def = _maybe_resolve(spec, op_def)
            action = op_def.get("action", "send")  # send or receive
            method = "PUB" if action == "send" else "SUB"

            channel_ref = op_def.get("channel", {})
            if isinstance(channel_ref, dict) and "$ref" in channel_ref:
                ref_path = channel_ref["$ref"]
                channel_name = ref_path.split("/")[-1]
                channel_def = resolve_ref(spec, ref_path)
            elif isinstance(channel_ref, str):
                channel_name = channel_ref
                channel_def = channels.get(channel_ref, {})
            else:
                channel_name = op_id
                channel_def = {}

            channel_def = _maybe_resolve(spec, channel_def)
            bindings_str = _extract_protocol_binding(
                {**channel_def.get("bindings", {}), **op_def.get("bindings", {})}, spec
            )

            op_summary = (op_def.get("summary") or op_def.get("description") or "").strip().split("\n")[0]
            address = channel_def.get("address", channel_name)

            # Messages from operation or channel
            op_messages = op_def.get("messages", {})
            if not op_messages:
                ch_messages = channel_def.get("messages", {})
                op_messages = ch_messages

            if isinstance(op_messages, dict):
                msg_list = list(op_messages.values())
            elif isinstance(op_messages, list):
                msg_list = op_messages
            else:
                msg_list = [op_messages] if op_messages else []

            if not msg_list:
                msg_list = [{}]

            for msg in msg_list:
                payload_params, header_params, msg_summary, response_fields = _compile_message(msg, spec)
                summary = op_summary or msg_summary

                required = [p for p in payload_params if p.required]
                optional = [p for p in payload_params if not p.required]

                for hp in header_params:
                    hp.name = f"header:{hp.name}"
                    optional.append(hp)

                response_schemas = []
                if response_fields:
                    response_schemas.append(ResponseSchema(
                        status_code=method,
                        description="message payload",
                        fields=response_fields,
                    ))

                desc_parts = [summary] if summary else []
                if bindings_str:
                    desc_parts.append(f"[{bindings_str}]")

                endpoint = Endpoint(
                    method=method,
                    path=address,
                    summary=" ".join(desc_parts),
                    required_params=required,
                    optional_params=optional,
                    response_schemas=response_schemas,
                )
                lap.endpoints.append(endpoint)
    else:
        # Fallback: v3 without operations block, just channels
        for channel_name, channel_def in channels.items():
            channel_def = _maybe_resolve(spec, channel_def)
            address = channel_def.get("address", channel_name)
            messages = channel_def.get("messages", {})

            for msg_name, msg in messages.items():
                payload_params, header_params, msg_summary, response_fields = _compile_message(msg, spec)

                required = [p for p in payload_params if p.required]
                optional = [p for p in payload_params if not p.required]

                response_schemas = []
                if response_fields:
                    response_schemas.append(ResponseSchema(
                        status_code="MSG",
                        description="message payload",
                        fields=response_fields,
                    ))

                endpoint = Endpoint(
                    method="MSG",
                    path=address,
                    summary=msg_summary,
                    required_params=required,
                    optional_params=optional,
                    response_schemas=response_schemas,
                )
                lap.endpoints.append(endpoint)

    return lap


def compile_asyncapi(spec_path: str) -> LAPSpec:
    """Compile an AsyncAPI spec to LAP format."""
    path = Path(spec_path)
    file_size = path.stat().st_size
    if file_size > 50 * 1024 * 1024:
        raise ValueError(f"AsyncAPI spec too large: {file_size} bytes (max 50MB)")
    raw = path.read_text()

    if path.suffix in (".yaml", ".yml"):
        spec = yaml.safe_load(raw)
    else:
        spec = json.loads(raw)

    if not isinstance(spec, dict):
        raise ValueError("Invalid AsyncAPI spec: expected a YAML/JSON mapping")

    version = _detect_version(spec)
    if version >= 3:
        return _compile_v3(spec)
    else:
        return _compile_v2(spec)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Compile AsyncAPI spec to LAP format")
    parser.add_argument("spec", help="Path to AsyncAPI spec (YAML/JSON)")
    parser.add_argument("-o", "--output", help="Output file (default: stdout)")
    parser.add_argument("--lean", action="store_true", help="Strip descriptions for max compression")
    args = parser.parse_args()

    lap = compile_asyncapi(args.spec)
    result = lap.to_lap(lean=args.lean)

    if args.output:
        Path(args.output).write_text(result)
        print(f"✅ Compiled to {args.output}")
    else:
        print(result)


if __name__ == "__main__":
    main()
