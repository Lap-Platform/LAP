#!/usr/bin/env python3
"""
LAP Compiler — Protobuf/gRPC → LAP format

Parses .proto files (text-based, no protoc needed) and compiles
service RPCs into LAP endpoints and message types into schemas.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from lap.core.formats.lap import (
    LAPSpec, Endpoint, Param, ResponseSchema, ResponseField, ErrorSchema,
    LAP_VERSION,
)


# ---------------------------------------------------------------------------
# Proto AST types
# ---------------------------------------------------------------------------

@dataclass
class ProtoEnum:
    name: str
    values: list  # [(name, number), ...]
    parent: str = ""  # fully-qualified parent message name

    @property
    def fqn(self):
        return f"{self.parent}.{self.name}" if self.parent else self.name


@dataclass
class ProtoField:
    name: str
    type: str
    number: int
    label: str = ""       # repeated, optional, required (proto2)
    map_key: str = ""     # non-empty if map field
    map_value: str = ""
    oneof_group: str = ""
    comment: str = ""


@dataclass
class ProtoMessage:
    name: str
    fields: list = field(default_factory=list)      # ProtoField
    enums: list = field(default_factory=list)        # ProtoEnum
    messages: list = field(default_factory=list)     # nested ProtoMessage
    oneofs: dict = field(default_factory=dict)       # group_name → [ProtoField]
    parent: str = ""

    @property
    def fqn(self):
        return f"{self.parent}.{self.name}" if self.parent else self.name


@dataclass
class ProtoRPC:
    name: str
    request_type: str
    response_type: str
    client_streaming: bool = False
    server_streaming: bool = False
    comment: str = ""


@dataclass
class ProtoService:
    name: str
    rpcs: list = field(default_factory=list)  # ProtoRPC
    comment: str = ""


@dataclass
class ProtoFile:
    syntax: str = "proto3"
    package: str = ""
    services: list = field(default_factory=list)   # ProtoService
    messages: list = field(default_factory=list)    # ProtoMessage
    enums: list = field(default_factory=list)       # ProtoEnum
    imports: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def _find_line_comment(line: str) -> int:
    """Find the start index of a // comment, respecting string literals. Returns -1 if none."""
    in_string = False
    quote_char = None
    i = 0
    while i < len(line):
        c = line[i]
        if in_string:
            if c == '\\':
                i += 2
                continue
            if c == quote_char:
                in_string = False
        else:
            if c == '"' or c == "'":
                in_string = True
                quote_char = c
            elif c == '/' and i + 1 < len(line) and line[i + 1] == '/':
                return i
        i += 1
    return -1


def _strip_block_comments(text: str) -> str:
    """Remove /* ... */ comments while respecting string literals and // comments."""
    result = []
    i = 0
    while i < len(text):
        c = text[i]
        if c == '"' or c == "'":
            # Copy string literal verbatim
            quote = c
            j = i + 1
            while j < len(text):
                if text[j] == '\\':
                    j += 2
                    continue
                if text[j] == quote:
                    j += 1
                    break
                j += 1
            result.append(text[i:j])
            i = j
        elif c == '/' and i + 1 < len(text) and text[i + 1] == '/':
            # Line comment - copy until newline
            j = text.find('\n', i)
            if j == -1:
                result.append(text[i:])
                break
            result.append(text[i:j + 1])
            i = j + 1
        elif c == '/' and i + 1 < len(text) and text[i + 1] == '*':
            # Block comment - skip until */
            j = text.find('*/', i + 2)
            if j == -1:
                break
            i = j + 2
        else:
            result.append(c)
            i += 1
    return ''.join(result)


def _strip_comments(text: str) -> tuple:
    """Strip comments but collect them for associating with next declaration."""
    text = _strip_block_comments(text)
    comments = {}
    lines = text.split('\n')
    clean_lines = []
    pending_comment = []
    for i, line in enumerate(lines):
        comment_pos = _find_line_comment(line)
        comment = ""
        if comment_pos >= 0:
            comment = line[comment_pos + 2:].strip()
            line = line[:comment_pos]
        if line.strip():
            if pending_comment:
                comments[len(clean_lines)] = ' '.join(pending_comment)
                pending_comment = []
            elif comment:
                comments[len(clean_lines)] = comment
                comment = ""
            clean_lines.append(line)
        if comment and not line.strip():
            pending_comment.append(comment)
    return '\n'.join(clean_lines), comments


def _find_block(text: str, start: int) -> tuple:
    """Find matching { } block starting from position of '{'. Returns (content, end_pos).
    Skips braces inside string literals."""
    assert text[start] == '{', f"Expected '{{' at {start}, got '{text[start]}'"
    depth = 1
    i = start + 1
    while i < len(text) and depth > 0:
        c = text[i]
        if c == '"':
            # Skip string literal
            i += 1
            while i < len(text) and text[i] != '"':
                if text[i] == '\\':
                    i += 1  # skip escaped char
                i += 1
            i += 1  # skip closing quote
            continue
        elif c == "'":
            i += 1
            while i < len(text) and text[i] != "'":
                if text[i] == '\\':
                    i += 1
                i += 1
            i += 1
            continue
        elif c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
        i += 1
    return text[start + 1:i - 1], i


def _parse_enum(name: str, body: str, parent: str = "") -> ProtoEnum:
    values = []
    for line in body.split(';'):
        line = line.strip()
        m = re.match(r'(\w+)\s*=\s*(-?\d+)', line)
        if m:
            values.append((m.group(1), int(m.group(2))))
    return ProtoEnum(name=name, values=values, parent=parent)


def _parse_message(name: str, body: str, parent: str = "") -> ProtoMessage:
    msg = ProtoMessage(name=name, parent=parent)
    fqn = msg.fqn
    pos = 0
    current_oneof = None

    while pos < len(body):
        # Skip whitespace
        while pos < len(body) and body[pos] in ' \t\n\r':
            pos += 1
        if pos >= len(body):
            break

        rest = body[pos:]

        # Nested enum
        m = re.match(r'enum\s+(\w+)\s*\{', rest)
        if m:
            brace = pos + m.end() - 1
            block, end = _find_block(body, brace)
            msg.enums.append(_parse_enum(m.group(1), block, parent=fqn))
            pos = end
            continue

        # Nested message
        m = re.match(r'message\s+(\w+)\s*\{', rest)
        if m:
            brace = pos + m.end() - 1
            block, end = _find_block(body, brace)
            msg.messages.append(_parse_message(m.group(1), block, parent=fqn))
            pos = end
            continue

        # Oneof
        m = re.match(r'oneof\s+(\w+)\s*\{', rest)
        if m:
            oneof_name = m.group(1)
            brace = pos + m.end() - 1
            block, end = _find_block(body, brace)
            oneof_fields = []
            for line in block.split(';'):
                line = line.strip()
                fm = re.match(r'(\w[\w.]*)\s+(\w+)\s*=\s*(\d+)', line)
                if fm:
                    f = ProtoField(
                        name=fm.group(2), type=fm.group(1),
                        number=int(fm.group(3)), oneof_group=oneof_name,
                    )
                    oneof_fields.append(f)
                    msg.fields.append(f)
            msg.oneofs[oneof_name] = oneof_fields
            pos = end
            continue

        # Map field
        m = re.match(r'map\s*<\s*(\w+)\s*,\s*([\w.]+)\s*>\s+(\w+)\s*=\s*(\d+)\s*;', rest)
        if m:
            f = ProtoField(
                name=m.group(3), type="map",
                number=int(m.group(4)),
                map_key=m.group(1), map_value=m.group(2),
            )
            msg.fields.append(f)
            pos += m.end()
            continue

        # Regular field: optional/repeated/required type name = number;
        m = re.match(r'(repeated|optional|required)?\s*([\w.]+)\s+(\w+)\s*=\s*(\d+)\s*;', rest)
        if m:
            f = ProtoField(
                name=m.group(3), type=m.group(2),
                number=int(m.group(4)),
                label=m.group(1) or "",
            )
            msg.fields.append(f)
            pos += m.end()
            continue

        # reserved, option, extensions, etc — skip to next semicolon or past it
        m = re.match(r'(reserved|option|extensions)\s+[^;]*;', rest)
        if m:
            pos += m.end()
            continue

        # Skip unknown char
        pos += 1

    return msg


def _parse_service(name: str, body: str) -> ProtoService:
    svc = ProtoService(name=name)
    # Collapse whitespace so multi-line RPCs match
    collapsed = re.sub(r'\s+', ' ', body)
    for m in re.finditer(
        r'rpc\s+(\w+)\s*\(\s*(stream\s+)?([\w.]+)\s*\)\s*returns\s*\(\s*(stream\s+)?([\w.]+)\s*\)\s*[;{]',
        collapsed
    ):
        rpc = ProtoRPC(
            name=m.group(1),
            request_type=m.group(3),
            response_type=m.group(5),
            client_streaming=bool(m.group(2)),
            server_streaming=bool(m.group(4)),
        )
        svc.rpcs.append(rpc)
    return svc


def parse_proto(text: str) -> ProtoFile:
    """Parse a .proto file text into a ProtoFile AST."""
    text, comments = _strip_comments(text)
    pf = ProtoFile()

    # Syntax
    m = re.search(r'syntax\s*=\s*"(proto[23])"\s*;', text)
    if m:
        pf.syntax = m.group(1)

    # Package
    m = re.search(r'package\s+([\w.]+)\s*;', text)
    if m:
        pf.package = m.group(1)

    # Imports
    for m in re.finditer(r'import\s+"([^"]+)"\s*;', text):
        pf.imports.append(m.group(1))

    # Services
    for m in re.finditer(r'service\s+(\w+)\s*\{', text):
        brace = m.end() - 1
        block, end = _find_block(text, brace)
        pf.services.append(_parse_service(m.group(1), block))

    # Top-level messages
    # We need to find message blocks that aren't inside service/message blocks.
    # Simple approach: find all top-level message/enum declarations.
    _parse_top_level(text, pf)

    return pf


def _parse_top_level(text: str, pf: ProtoFile):
    """Parse top-level message and enum declarations."""
    pos = 0
    length = len(text)
    # Precompile pattern for top-level declarations
    _TOP_RE = re.compile(r'(service|enum|message)\s+(\w+)\s*\{')

    while pos < length:
        m = _TOP_RE.search(text, pos)
        if not m:
            break
        kind = m.group(1)
        name = m.group(2)
        brace = m.end() - 1
        try:
            block, end = _find_block(text, brace)
        except (AssertionError, IndexError):
            pos = m.end()
            continue

        if kind == 'service':
            pass  # already parsed
        elif kind == 'enum':
            pf.enums.append(_parse_enum(name, block))
        elif kind == 'message':
            pf.messages.append(_parse_message(name, block))

        pos = end


# ---------------------------------------------------------------------------
# Compiler: Proto AST → LAP
# ---------------------------------------------------------------------------

# Well-known type mappings
_WKT_MAP = {
    "google.protobuf.Timestamp": "str(timestamp)",
    "google.protobuf.Duration": "str(duration)",
    "google.protobuf.Empty": "(empty)",
    "google.protobuf.Any": "any",
    "google.protobuf.Struct": "map",
    "google.protobuf.Value": "any",
    "google.protobuf.StringValue": "str?",
    "google.protobuf.Int32Value": "int?",
    "google.protobuf.Int64Value": "int?",
    "google.protobuf.BoolValue": "bool?",
    "google.protobuf.FloatValue": "num?",
    "google.protobuf.DoubleValue": "num?",
    "google.protobuf.BytesValue": "bytes?",
}

_SCALAR_MAP = {
    "double": "num(f64)", "float": "num(f32)",
    "int32": "int", "int64": "int(i64)", "uint32": "int(u32)", "uint64": "int(u64)",
    "sint32": "int", "sint64": "int(i64)",
    "fixed32": "int(u32)", "fixed64": "int(u64)",
    "sfixed32": "int", "sfixed64": "int(i64)",
    "bool": "bool", "string": "str", "bytes": "bytes",
}


def _build_type_index(pf: ProtoFile) -> dict:
    """Build a lookup of message/enum name → definition."""
    index = {}

    def _index_msg(msg: ProtoMessage):
        index[msg.name] = msg
        index[msg.fqn] = msg
        for sub in msg.messages:
            _index_msg(sub)
        for e in msg.enums:
            index[e.name] = e
            index[e.fqn] = e

    for msg in pf.messages:
        _index_msg(msg)
    for e in pf.enums:
        index[e.name] = e
        index[e.fqn] = e

    return index


def _strip_enum_prefix(values: list) -> list:
    """Strip common prefix from enum value names.
    
    E.g., ['USER_ROLE_ADMIN', 'USER_ROLE_EDITOR'] → ['ADMIN', 'EDITOR']
    """
    if len(values) < 2:
        return values
    # Find common prefix up to last underscore
    prefix = values[0]
    for v in values[1:]:
        while prefix and not v.startswith(prefix):
            # Remove last segment (exclude trailing _)
            trimmed = prefix.rstrip('_')
            idx = trimmed.rfind('_')
            if idx == -1:
                prefix = ""
            else:
                prefix = trimmed[:idx + 1]
    if prefix and '_' in prefix:
        return [v[len(prefix):] for v in values]
    return values


def _resolve_type(type_name: str, type_index: dict) -> str:
    """Resolve a proto type to a LAP type string."""
    if type_name in _WKT_MAP:
        return _WKT_MAP[type_name]
    if type_name in _SCALAR_MAP:
        return _SCALAR_MAP[type_name]
    # Check type index
    defn = type_index.get(type_name)
    if isinstance(defn, ProtoEnum):
        vals = [v[0] for v in defn.values if v[1] != 0]  # skip UNSPECIFIED
        if vals:
            vals = _strip_enum_prefix(vals)
            return f"enum({'/'.join(vals)})"
        return "enum"
    if isinstance(defn, ProtoMessage):
        return defn.name
    return type_name


def _message_to_fields(msg: ProtoMessage, type_index: dict, depth: int = 0, max_depth: int = 2, defined_types: set = None) -> list:
    """Convert a ProtoMessage to a list of ResponseField."""
    if defined_types is None:
        defined_types = set()
    fields = []
    for f in msg.fields:
        if f.type == "map":
            key_t = _resolve_type(f.map_key, type_index)
            val_t = _resolve_type(f.map_value, type_index)
            type_str = f"map<{key_t},{val_t}>"
            fields.append(ResponseField(name=f.name, type=type_str))
        else:
            type_str = _resolve_type(f.type, type_index)
            if f.label == "repeated":
                type_str = f"[{type_str}]"

            children = []
            defn = type_index.get(f.type)
            # Only inline if not a reused/defined type and within depth limit
            if depth < max_depth and isinstance(defn, ProtoMessage) and defn.fields and defn.name not in defined_types:
                children = _message_to_fields(defn, type_index, depth + 1, max_depth, defined_types)

            rf = ResponseField(
                name=f.name, type=type_str,
                nullable=bool(f.oneof_group),
                children=children,
            )
            fields.append(rf)
    return fields


def _message_to_params(msg: ProtoMessage, type_index: dict) -> list:
    """Convert a ProtoMessage's fields to Param list."""
    params = []
    for f in msg.fields:
        if f.type == "map":
            key_t = _resolve_type(f.map_key, type_index)
            val_t = _resolve_type(f.map_value, type_index)
            type_str = f"map<{key_t},{val_t}>"
        else:
            type_str = _resolve_type(f.type, type_index)
            if f.label == "repeated":
                type_str = f"[{type_str}]"

        p = Param(
            name=f.name,
            type=type_str,
            required=False,  # proto3 fields are all optional by default
            description="",
        )
        params.append(p)
    return params


def _rpc_to_endpoint(rpc: ProtoRPC, service: ProtoService, type_index: dict, package: str, defined_types: set = None) -> Endpoint:
    """Convert a single RPC to a LAP Endpoint."""
    # Path: /ServiceName/RPCName (package is in @base)
    path = f"/{service.name}/{rpc.name}"

    # Determine streaming pattern label
    if rpc.client_streaming and rpc.server_streaming:
        method = "BIDI-STREAM"
    elif rpc.client_streaming:
        method = "CLIENT-STREAM"
    elif rpc.server_streaming:
        method = "SERVER-STREAM"
    else:
        method = "UNARY"

    # Request params
    req_msg = type_index.get(rpc.request_type)
    body_params = []
    req_type_ref = None
    dt = defined_types or set()
    if isinstance(req_msg, ProtoMessage):
        if req_msg.name in dt:
            req_type_ref = req_msg.name
        else:
            body_params = _message_to_params(req_msg, type_index)

    # Response
    resp_msg = type_index.get(rpc.response_type)
    response_schemas = []
    if rpc.response_type in _WKT_MAP and _WKT_MAP[rpc.response_type] == "(empty)":
        response_schemas.append(ResponseSchema(status_code="OK", description="Empty response"))
    elif isinstance(resp_msg, ProtoMessage):
        dt = defined_types or set()
        if resp_msg.name in dt:
            # Type is defined via @type, just reference it by name
            response_schemas.append(ResponseSchema(
                status_code="OK",
                description=f"→ {resp_msg.name}",
                fields=[],
            ))
        else:
            resp_fields = _message_to_fields(resp_msg, type_index, defined_types=dt)
            response_schemas.append(ResponseSchema(
                status_code="OK",
                description=resp_msg.name,
                fields=resp_fields,
            ))

    # Only add summary if there's a meaningful comment (not just the RPC name)
    summary = ""
    if rpc.comment and rpc.comment != rpc.name:
        summary = rpc.comment

    ep = Endpoint(
        method=method,
        path=path,
        summary=summary,
        request_body=body_params,
        response_schemas=response_schemas,
    )
    if req_type_ref:
        ep._req_type_ref = req_type_ref
    return ep


def _count_type_refs(pf: ProtoFile, type_index: dict) -> dict:
    """Count how many times each message type is referenced in RPC responses/requests."""
    counts = {}
    for svc in pf.services:
        for rpc in svc.rpcs:
            for t in [rpc.request_type, rpc.response_type]:
                defn = type_index.get(t)
                if isinstance(defn, ProtoMessage) and defn.fields:
                    counts[defn.name] = counts.get(defn.name, 0) + 1
                    # Also count nested refs
                    for f in defn.fields:
                        nested = type_index.get(f.type)
                        if isinstance(nested, ProtoMessage) and nested.fields:
                            counts[nested.name] = counts.get(nested.name, 0) + 1
    return counts


def _message_to_type_str(msg: ProtoMessage, type_index: dict, defined_types: set, _visited: set = None, _depth: int = 0) -> str:
    """Serialize a message to compact inline type string."""
    if _depth > 2:
        return msg.name
    if _visited is None:
        _visited = set()
    if msg.name in _visited:
        return msg.name  # break circular reference
    _visited = _visited | {msg.name}
    parts = []
    for f in msg.fields:
        if f.type == "map":
            key_t = _resolve_type(f.map_key, type_index)
            val_t = _resolve_type(f.map_value, type_index)
            parts.append(f"{f.name}: map<{key_t},{val_t}>")
        else:
            type_str = _resolve_type(f.type, type_index)
            if f.label == "repeated":
                type_str = f"[{type_str}]"
            # Inline nested types only if not already defined
            defn = type_index.get(f.type)
            if isinstance(defn, ProtoMessage) and defn.fields and defn.name not in defined_types and defn.name not in _visited:
                nested = _message_to_type_str(defn, type_index, defined_types, _visited, _depth + 1)
                nullable = "?" if f.oneof_group else ""
                parts.append(f"{f.name}: {type_str}{nullable}{{{nested}}}")
            else:
                nullable = "?" if f.oneof_group else ""
                parts.append(f"{f.name}: {type_str}{nullable}")
    return ", ".join(parts)


def _resolve_imports(pf: ProtoFile, spec_dir: Path, visited: set = None) -> None:
    """Resolve imports by parsing referenced .proto files and merging their types."""
    if visited is None:
        visited = set()

    for imp in pf.imports:
        if imp in visited:
            continue
        visited.add(imp)

        # Try resolving relative to spec directory
        imp_path = spec_dir / imp
        if not imp_path.exists():
            # Try same directory with just the filename
            imp_path = spec_dir / Path(imp).name
        if not imp_path.exists():
            # For google/api/*, google/iam/*, etc. — skip, they're annotations
            continue

        try:
            imp_text = imp_path.read_text(encoding='utf-8')
            imp_pf = parse_proto(imp_text)
            # Recursively resolve imports
            _resolve_imports(imp_pf, spec_dir, visited)
            # Merge types into main file
            pf.messages.extend(imp_pf.messages)
            pf.enums.extend(imp_pf.enums)
        except Exception:
            continue


# Well-known Google protobuf type stubs (message definitions for import resolution)
_WELL_KNOWN_MESSAGES = {
    "google.protobuf.Timestamp": ProtoMessage(name="Timestamp", fields=[
        ProtoField(name="seconds", type="int64", number=1),
        ProtoField(name="nanos", type="int32", number=2),
    ], parent="google.protobuf"),
    "google.protobuf.Duration": ProtoMessage(name="Duration", fields=[
        ProtoField(name="seconds", type="int64", number=1),
        ProtoField(name="nanos", type="int32", number=2),
    ], parent="google.protobuf"),
    "google.protobuf.Empty": ProtoMessage(name="Empty", parent="google.protobuf"),
    "google.protobuf.Any": ProtoMessage(name="Any", fields=[
        ProtoField(name="type_url", type="string", number=1),
        ProtoField(name="value", type="bytes", number=2),
    ], parent="google.protobuf"),
    "google.protobuf.Struct": ProtoMessage(name="Struct", fields=[
        ProtoField(name="fields", type="map", number=1, map_key="string", map_value="Value"),
    ], parent="google.protobuf"),
    "google.protobuf.Value": ProtoMessage(name="Value", parent="google.protobuf"),
    "google.protobuf.FieldMask": ProtoMessage(name="FieldMask", fields=[
        ProtoField(name="paths", type="string", number=1, label="repeated"),
    ], parent="google.protobuf"),
}


def _inject_well_known_types(type_index: dict) -> None:
    """Add well-known types to the type index so they can be resolved."""
    for fqn, msg in _WELL_KNOWN_MESSAGES.items():
        short = msg.name
        if fqn not in type_index:
            type_index[fqn] = msg
        if short not in type_index:
            type_index[short] = msg


def compile_proto(spec_path: str) -> LAPSpec:
    """Compile a .proto file to LAP format."""
    path = Path(spec_path)
    text = path.read_text(encoding='utf-8')
    pf = parse_proto(text)

    # Resolve imports
    _resolve_imports(pf, path.parent)

    type_index = _build_type_index(pf)

    # Inject well-known types
    _inject_well_known_types(type_index)

    # Also index with package prefix for FQ lookups
    if pf.package:
        for msg in pf.messages:
            fqn_with_pkg = f"{pf.package}.{msg.name}"
            if fqn_with_pkg not in type_index:
                type_index[fqn_with_pkg] = msg

    api_name = pf.package or path.stem
    lap = LAPSpec(
        api_name=api_name,
        version=pf.syntax,
        base_url=f"grpc://{pf.package}" if pf.package else "",
    )

    # Find types used more than once — these get @type definitions
    ref_counts = _count_type_refs(pf, type_index)
    reused_types = {name for name, count in ref_counts.items() if count > 1}
    
    # Store type definitions for the spec
    lap._type_defs = {}  # name → field string
    lap._reused_types = reused_types
    for name in reused_types:
        defn = type_index.get(name)
        if isinstance(defn, ProtoMessage) and defn.fields:
            lap._type_defs[name] = _message_to_type_str(defn, type_index, reused_types)

    for svc in pf.services:
        for rpc in svc.rpcs:
            endpoint = _rpc_to_endpoint(rpc, svc, type_index, pf.package, reused_types)
            lap.endpoints.append(endpoint)

    return lap


# Alias for auto-detection in benchmark suite
compile_protobuf = compile_proto


def compile_proto_dir(dir_path: str) -> list:
    """Compile all .proto files in a directory."""
    p = Path(dir_path)
    results = []
    for proto_file in sorted(p.glob("*.proto")):
        results.append(compile_proto(str(proto_file)))
    return results


