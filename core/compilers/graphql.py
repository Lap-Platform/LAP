#!/usr/bin/env python3
"""
GraphQL SDL / Introspection JSON → LAP compiler.

Produces a compact GraphQL-native LAP representation that defines
types once and references them by name, avoiding the massive expansion
that comes from inlining response fields in every endpoint.
"""

import json
from pathlib import Path
from graphql import (
    build_schema,
    build_client_schema,
    GraphQLObjectType,
    GraphQLInputObjectType,
    GraphQLEnumType,
    GraphQLInterfaceType,
    GraphQLUnionType,
    GraphQLList,
    GraphQLNonNull,
    GraphQLScalarType,
    GraphQLField,
    GraphQLArgument,
    GraphQLSchema,
    Undefined,
)

from core.formats.lap import LAPSpec, Endpoint, Param, ResponseSchema, ResponseField, ErrorSchema


# ── Type string helpers ──────────────────────────────────────────────

SCALAR_MAP = {
    'String': 'str', 'Int': 'int', 'Float': 'num',
    'Boolean': 'bool', 'ID': 'id',
}


def _unwrap(gql_type):
    """Unwrap NonNull/List wrappers, return (base_type, type_string, nullable)."""
    nullable = True
    if isinstance(gql_type, GraphQLNonNull):
        nullable = False
        gql_type = gql_type.of_type

    if isinstance(gql_type, GraphQLList):
        inner_type, inner_str, _ = _unwrap(gql_type.of_type)
        return inner_type, f"[{inner_str}]", nullable

    if isinstance(gql_type, GraphQLNonNull):
        inner_type, inner_str, _ = _unwrap(gql_type)
        return inner_type, inner_str, False

    name = getattr(gql_type, 'name', 'any')
    return gql_type, SCALAR_MAP.get(name, name), nullable


def _type_string(gql_type) -> str:
    _, s, _ = _unwrap(gql_type)
    return s


def _is_nullable(gql_type) -> bool:
    return not isinstance(gql_type, GraphQLNonNull)


def _type_ref(gql_type) -> str:
    """Compact type reference like SDL: User!, [Issue!]!, String"""
    if isinstance(gql_type, GraphQLNonNull):
        inner = _type_ref(gql_type.of_type)
        return f"{inner}!"
    if isinstance(gql_type, GraphQLList):
        inner = _type_ref(gql_type.of_type)
        return f"[{inner}]"
    name = getattr(gql_type, 'name', 'any')
    return SCALAR_MAP.get(name, name)


# ── Compact type serialization ───────────────────────────────────────

def _compact_field(fname, field_obj) -> str:
    """Serialize a field compactly: name(args): Type!"""
    tref = _type_ref(field_obj.type)
    args_str = ""
    if hasattr(field_obj, 'args') and field_obj.args:
        arg_parts = []
        for aname, arg in field_obj.args.items():
            aref = _type_ref(arg.type)
            default = ""
            if arg.default_value is not Undefined and arg.default_value is not None:
                default = f"={arg.default_value}"
            arg_parts.append(f"{aname}:{aref}{default}")
        args_str = f"({','.join(arg_parts)})"
    return f"{fname}{args_str}:{tref}"


def _is_connection_type(name, t):
    """Check if this is a standard Relay connection pattern."""
    if not isinstance(t, GraphQLObjectType):
        return False
    fnames = set(t.fields.keys())
    # Must have pageInfo and at least edges or nodes
    if 'pageInfo' not in fnames:
        return False
    return bool(fnames & {'edges', 'nodes'}) and fnames <= {'edges', 'nodes', 'pageInfo', 'totalCount'}


def _is_edge_type(name, t):
    """Check if this is a standard Relay edge type: cursor + node."""
    if not isinstance(t, GraphQLObjectType):
        return False
    fnames = set(t.fields.keys())
    return fnames == {'cursor', 'node'} or fnames <= {'cursor', 'node'}


def _get_connection_node_type(t):
    """Extract the node type name from a Connection type."""
    # Try edges first
    edges_field = t.fields.get('edges')
    if edges_field:
        base, _, _ = _unwrap(edges_field.type)
        if isinstance(base, GraphQLList):
            base, _, _ = _unwrap(base.of_type)
        if isinstance(base, GraphQLObjectType) and 'node' in base.fields:
            node_field = base.fields['node']
            node_base, _, _ = _unwrap(node_field.type)
            return getattr(node_base, 'name', None)
    # Try nodes
    nodes_field = t.fields.get('nodes')
    if nodes_field:
        base, _, _ = _unwrap(nodes_field.type)
        if isinstance(base, GraphQLList):
            base, _, _ = _unwrap(base.of_type)
        return getattr(base, 'name', None)
    return None


# Pagination argument patterns to compress
_PAGINATION_ARGS = {'first', 'after', 'last', 'before'}
_FORWARD_PAGE_ARGS = {'first', 'after'}


def _compact_field_lean(fname, field_obj, conn_types):
    """Serialize a field compactly with lean optimizations."""
    tref = _type_ref(field_obj.type)

    # Replace Connection type refs with shorthand
    for conn_name, node_name in conn_types.items():
        if conn_name in tref:
            tref = tref.replace(conn_name, f"[{node_name}]~")

    args_str = ""
    if hasattr(field_obj, 'args') and field_obj.args:
        arg_names = set(field_obj.args.keys())
        remaining_args = {}
        page_shorthand = ""

        # Detect pagination patterns
        if arg_names >= _PAGINATION_ARGS:
            page_shorthand = "@page"
            remaining_args = {k: v for k, v in field_obj.args.items() if k not in _PAGINATION_ARGS}
        elif arg_names >= _FORWARD_PAGE_ARGS:
            page_shorthand = "@pg"
            remaining_args = {k: v for k, v in field_obj.args.items() if k not in _FORWARD_PAGE_ARGS}
        else:
            remaining_args = dict(field_obj.args.items())

        arg_parts = []
        if page_shorthand:
            arg_parts.append(page_shorthand)
        for aname, arg in remaining_args.items():
            aref = _type_ref(arg.type)
            default = ""
            if arg.default_value is not Undefined and arg.default_value is not None:
                default = f"={arg.default_value}"
            arg_parts.append(f"{aname}:{aref}{default}")
        if arg_parts:
            args_str = f"({','.join(arg_parts)})"
    return f"{fname}{args_str}:{tref}"


def _get_interface_field_names(t):
    """Get field names inherited from interfaces."""
    inherited = set()
    if hasattr(t, 'interfaces') and t.interfaces:
        for iface in t.interfaces:
            inherited.update(iface.fields.keys())
    return inherited


def _compact_type_def(name, t, lean=False, conn_types=None) -> str:
    """One-line compact type definition."""
    conn_types = conn_types or {}

    if isinstance(t, GraphQLEnumType) and name not in ('Boolean',):
        values = ",".join(t.values.keys())
        # Use bracket notation in lean mode for better tokenization
        if lean:
            return f"enum {name}[{values}]"
        else:
            return f"enum {name}={values.replace(',','|')}"

    if isinstance(t, GraphQLInputObjectType):
        fields = []
        for fn, f in t.fields.items():
            tref = _type_ref(f.type)
            # Replace Connection types in input fields too
            for cn, nn in conn_types.items():
                if cn in tref:
                    tref = tref.replace(cn, f"[{nn}]~")
            default = ""
            if f.default_value is not Undefined and f.default_value is not None:
                default = f"={f.default_value}"
            fields.append(f"{fn}:{tref}{default}")
        return f"input {name}{{{','.join(fields)}}}"

    if isinstance(t, GraphQLInterfaceType):
        field_fn = (lambda fn, fv: _compact_field_lean(fn, fv, conn_types)) if lean else _compact_field
        fields = [field_fn(fn, fv) for fn, fv in t.fields.items()]
        return f"iface {name}{{{','.join(fields)}}}"

    if isinstance(t, GraphQLUnionType):
        members = [m.name for m in t.types]
        if lean:
            return f"union {name}[{','.join(members)}]"
        else:
            return f"union {name}={'|'.join(members)}"

    if isinstance(t, GraphQLObjectType):
        # In lean mode, connection and edge types are eliminated
        if lean and (_is_connection_type(name, t) or _is_edge_type(name, t)):
            return None

        impls = ""
        if t.interfaces:
            impls = ":" + ",".join(i.name for i in t.interfaces)

        # In lean mode, skip fields inherited from interfaces
        inherited = _get_interface_field_names(t) if lean else set()
        if lean:
            fields = [_compact_field_lean(fn, fv, conn_types) for fn, fv in t.fields.items() if fn not in inherited]
        else:
            fields = [_compact_field(fn, fv) for fn, fv in t.fields.items() if fn not in inherited]

        # Replace Connection type refs in field type strings
        return f"type {name}{impls}{{{','.join(fields)}}}"

    return None


# ── Endpoint compilation ─────────────────────────────────────────────

def _arg_to_param(name: str, arg: GraphQLArgument) -> Param:
    """Convert a GraphQL argument to a LAP Param."""
    base, type_str, nullable = _unwrap(arg.type)
    has_default = arg.default_value is not Undefined
    required = not nullable and not has_default

    enum_values = []
    if isinstance(base, GraphQLEnumType):
        enum_values = list(base.values.keys())

    desc = arg.description or ""
    default = None
    if has_default and arg.default_value is not None:
        try:
            default = str(arg.default_value)
        except Exception:
            pass

    return Param(
        name=name,
        type=type_str,
        required=required,
        description=desc.replace('\n', ' ').strip(),
        enum=enum_values,
        default=default,
    )


def _extract_response_fields(gql_type, schema, visited=None, depth=0, max_depth=2):
    """Extract response fields from a GraphQL output type."""
    if visited is None:
        visited = set()
    base, _, _ = _unwrap(gql_type)
    if isinstance(base, (GraphQLScalarType, GraphQLEnumType)):
        return []
    if isinstance(base, GraphQLUnionType):
        fields = []
        for member in base.types:
            if member.name not in visited:
                fields.extend(_extract_response_fields(member, schema, visited, depth, max_depth))
        return fields
    if isinstance(base, (GraphQLObjectType, GraphQLInterfaceType)):
        type_name = base.name
        if type_name in visited or depth >= max_depth:
            return [ResponseField(name="...", type=type_name, nullable=True)]
        visited = visited | {type_name}
        result = []
        for fname, field in base.fields.items():
            fbase, ftype_str, fnullable = _unwrap(field.type)
            children = []
            if isinstance(fbase, (GraphQLObjectType, GraphQLInterfaceType, GraphQLUnionType)):
                children = _extract_response_fields(field.type, schema, visited, depth + 1, max_depth)
            result.append(ResponseField(name=fname, type=ftype_str, nullable=fnullable, children=children))
        return result
    return []


def _compile_field(field_name, field, method, schema):
    """Compile a single Query/Mutation/Subscription field to an Endpoint."""
    required_params = []
    optional_params = []
    for arg_name, arg in (field.args or {}).items():
        param = _arg_to_param(arg_name, arg)
        if param.required:
            required_params.append(param)
        else:
            optional_params.append(param)

    response_fields = _extract_response_fields(field.type, schema)
    response_schemas = []
    if response_fields:
        response_schemas.append(ResponseSchema(
            status_code="200" if method != "EVENT" else "event",
            description="",
            fields=response_fields,
        ))

    path = f"/{field_name}"
    summary = (field.description or "").replace('\n', ' ').strip()

    return Endpoint(
        method=method,
        path=path,
        summary=summary,
        required_params=required_params,
        optional_params=optional_params,
        response_schemas=response_schemas,
    )


# ── Schema loading ───────────────────────────────────────────────────

def _load_schema(path: Path) -> GraphQLSchema:
    """Load a GraphQL schema from SDL or introspection JSON."""
    if path.suffix.lower() == '.json':
        raw = json.loads(path.read_text(encoding='utf-8'))
        # Unwrap {"data": {"__schema": ...}} wrapper if present
        if 'data' in raw and isinstance(raw['data'], dict):
            raw = raw['data']
        return build_client_schema(raw)
    else:
        sdl = path.read_text(encoding='utf-8')
        return build_schema(sdl, assume_valid_sdl=True)


# ── Main compile function ────────────────────────────────────────────

def compile_graphql(spec_path: str) -> 'GraphQLLAPSpec':
    """Compile a GraphQL SDL or introspection JSON file to LAP format."""
    path = Path(spec_path)
    schema = _load_schema(path)

    api_name = path.stem.replace('-', ' ').replace('_', ' ').title()

    # Collect type definitions and operations
    type_defs_lines = []
    type_map = schema.type_map
    builtin_roots = set()
    if schema.query_type:
        builtin_roots.add(schema.query_type.name)
    if schema.mutation_type:
        builtin_roots.add(schema.mutation_type.name)
    if schema.subscription_type:
        builtin_roots.add(schema.subscription_type.name)

    # Store raw type map for lean-mode rendering
    user_types = {}
    for name, t in sorted(type_map.items()):
        if name.startswith('__') or name in builtin_roots:
            continue
        if isinstance(t, GraphQLScalarType) and name in SCALAR_MAP:
            continue
        user_types[name] = t
        line = _compact_type_def(name, t, lean=False)
        if line:
            type_defs_lines.append(line)

    # Collect operations
    ops_lines = []
    op_map = {'Q': schema.query_type, 'M': schema.mutation_type, 'S': schema.subscription_type}
    for prefix, root in op_map.items():
        if not root:
            continue
        for fname, field in root.fields.items():
            args_str = ""
            if field.args:
                arg_parts = []
                for aname, arg in field.args.items():
                    aref = _type_ref(arg.type)
                    default = ""
                    if arg.default_value is not Undefined and arg.default_value is not None:
                        default = f"={arg.default_value}"
                    arg_parts.append(f"{aname}:{aref}{default}")
                args_str = f"({','.join(arg_parts)})"
            ret = _type_ref(field.type)
            desc = ""
            if field.description:
                desc = f" # {field.description.replace(chr(10), ' ').strip()}"
            ops_lines.append(f"{prefix} {fname}{args_str}->{ret}{desc}")

    compact_body = "\n".join(type_defs_lines) + "\n\n" + "\n".join(ops_lines)

    # Also build the legacy endpoints for backward compatibility
    lap = GraphQLLAPSpec(
        api_name=api_name,
        base_url="/graphql",
        version="",
        auth_scheme="",
        type_defs="\n".join(type_defs_lines),
        compact_body=compact_body,
        user_types=user_types,
        ops_lines=ops_lines,
    )

    if schema.query_type:
        for fname, field in schema.query_type.fields.items():
            lap.endpoints.append(_compile_field(fname, field, "GET", schema))
    if schema.mutation_type:
        for fname, field in schema.mutation_type.fields.items():
            lap.endpoints.append(_compile_field(fname, field, "POST", schema))
    if schema.subscription_type:
        for fname, field in schema.subscription_type.fields.items():
            lap.endpoints.append(_compile_field(fname, field, "EVENT", schema))

    return lap


class GraphQLLAPSpec(LAPSpec):
    """LAPSpec subclass with compact GraphQL-native output."""

    def __init__(self, *args, type_defs: str = "", compact_body: str = "",
                 user_types=None, ops_lines=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._type_defs = type_defs
        self._compact_body = compact_body
        self._user_types = user_types or {}
        self._ops_lines = ops_lines or []

    def to_lap(self, lean: bool = False) -> str:
        """Produce compact GraphQL-native LAP output."""
        lines = [f"@lap v0.1", f"@api {self.api_name}", f"@base {self.base_url}", ""]

        if lean:
            # Build connection type map: ConnectionName -> NodeTypeName
            conn_types = {}
            edge_types = set()
            for name, t in self._user_types.items():
                if _is_connection_type(name, t):
                    node_name = _get_connection_node_type(t)
                    if node_name:
                        conn_types[name] = node_name
                    # Also mark edge types for elimination
                    edges_field = t.fields.get('edges')
                    if edges_field:
                        base, _, _ = _unwrap(edges_field.type)
                        if isinstance(base, GraphQLList):
                            base, _, _ = _unwrap(base.of_type)
                        if hasattr(base, 'name'):
                            edge_types.add(base.name)

            # Find PageInfo types (implied by connection shorthand)
            skip_types = set(conn_types.keys()) | edge_types
            for name, t in self._user_types.items():
                if _is_connection_type(name, t):
                    pi = t.fields.get('pageInfo')
                    if pi:
                        base, _, _ = _unwrap(pi.type)
                        if hasattr(base, 'name'):
                            skip_types.add(base.name)

            # Check if PageInfo is used outside connections
            for name, t in self._user_types.items():
                if name in skip_types:
                    continue
                if isinstance(t, (GraphQLObjectType, GraphQLInterfaceType, GraphQLInputObjectType)):
                    for fn, fv in t.fields.items():
                        base, _, _ = _unwrap(fv.type)
                        bname = getattr(base, 'name', None)
                        if bname in skip_types and bname not in conn_types and bname not in edge_types:
                            skip_types.discard(bname)

            # Regenerate type defs in lean mode
            for name, t in sorted(self._user_types.items()):
                if name in skip_types:
                    continue
                line = _compact_type_def(name, t, lean=True, conn_types=conn_types)
                if line:
                    lines.append(line)
            lines.append("")

            # Operations with lean compression
            for op in self._ops_lines:
                # Strip descriptions
                if ' # ' in op:
                    op = op[:op.index(' # ')]
                # Replace Connection types in operation return types
                for cn, nn in conn_types.items():
                    if cn in op:
                        op = op.replace(cn, f"[{nn}]~")
                # Compress pagination args in operations
                import re
                # Full pagination: first:int,after:str,last:int,before:str -> @page
                op = re.sub(r'first:int!?,after:str!?,last:int!?,before:str!?', '@page', op)
                op = re.sub(r'first:int!?,last:int!?,after:str!?,before:str!?', '@page', op)
                # Forward pagination: first:int,after:str -> @pg
                op = re.sub(r'first:int!?,after:str!?', '@pg', op)
                # Clean up trailing/leading commas from removed args
                op = re.sub(r'\(,', '(', op)
                op = re.sub(r',\)', ')', op)
                op = re.sub(r',,+', ',', op)
                lines.append(op)
        else:
            lines.append(self._compact_body)

        lines.append("")
        return "\n".join(lines)
