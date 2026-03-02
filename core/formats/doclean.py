"""
DocLean Format Spec & Serializer

DocLean is a compressed, structured representation of API documentation
optimized for LLM agent consumption.
"""

import re
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Optional

DOCLEAN_VERSION = "v0.3"


@dataclass
class Param:
    name: str
    type: str
    required: bool = False
    description: str = ""
    enum: list = field(default_factory=list)
    default: Optional[str] = None

    def to_doclean(self, lean: bool = False) -> str:
        parts = [f"{self.name}: {self.type}"]
        if self.enum and len(self.enum) > 1:
            parts[0] += f"({'/'.join(str(e) for e in self.enum)})"
        if self.default is not None:
            parts[0] += f"={self.default}"
        if self.description and not lean:
            parts.append(f"# {self.description}")
        return " ".join(parts)


@dataclass
class ResponseField:
    """A field in a response schema."""
    name: str
    type: str
    nullable: bool = False
    children: list = field(default_factory=list)

    def to_doclean(self, lean: bool = False, depth: int = 0) -> str:
        nullable = "?" if self.nullable else ""
        if self.children:
            child_str = ", ".join(c.to_doclean(lean=lean, depth=depth + 1) for c in self.children)
            return f"{self.name}: {self.type}{nullable}{{{child_str}}}"
        return f"{self.name}: {self.type}{nullable}"


@dataclass
class ResponseSchema:
    """Compiled response schema — typed contract, not an example."""
    status_code: str
    description: str = ""
    fields: list = field(default_factory=list)

    def to_doclean(self, lean: bool = False) -> str:
        if not self.fields:
            if lean and not self.description.startswith("→"):
                return f"@returns({self.status_code})"
            if self.description:
                return f"@returns({self.status_code}) {self.description}"
            return f"@returns({self.status_code})"
        fields_str = ", ".join(f.to_doclean(lean=lean) for f in self.fields)
        line = f"@returns({self.status_code}) {{{fields_str}}}"
        if self.description and not lean:
            line += f" # {self.description}"
        return line


@dataclass
class ErrorSchema:
    """Compiled error contract."""
    code: str
    type: str = ""
    description: str = ""

    def to_doclean(self, lean: bool = False) -> str:
        parts = [self.code]
        if self.type:
            parts[0] += f":{self.type}"
        if self.description and not lean:
            parts.append(self.description)
        return ": ".join(parts) if (self.description and not lean) else parts[0]


@dataclass
class Endpoint:
    method: str
    path: str
    summary: str = ""
    auth: str = ""
    required_params: list = field(default_factory=list)
    optional_params: list = field(default_factory=list)
    request_body: list = field(default_factory=list)
    response_schemas: list = field(default_factory=list)
    error_schemas: list = field(default_factory=list)
    responses: dict = field(default_factory=dict)
    errors: dict = field(default_factory=dict)
    example_request: str = ""

    def to_doclean(self, lean: bool = False) -> str:
        lines = [f"@endpoint {self.method.upper()} {self.path}"]
        if self.summary and not lean:
            lines.append(f"@desc {self.summary}")
        if self.auth:
            lines.append(f"@auth {self.auth}")

        # Check for type reference shorthand
        req_type_ref = getattr(self, '_req_type_ref', None)
        if req_type_ref:
            lines.append(f"@body → {req_type_ref}")
        else:
            if self.required_params or self.request_body:
                req = self.required_params + [p for p in self.request_body if p.required]
                if req:
                    fields = ", ".join(p.to_doclean(lean=lean) for p in req)
                    lines.append(f"@required {{{fields}}}")

            opt = self.optional_params + [p for p in self.request_body if not p.required]
            if opt:
                fields = ", ".join(p.to_doclean(lean=lean) for p in opt)
                lines.append(f"@optional {{{fields}}}")

        if self.response_schemas:
            for rs in self.response_schemas:
                lines.append(rs.to_doclean(lean=lean))
        elif self.responses:
            for code, desc in self.responses.items():
                if lean:
                    lines.append(f"@returns({code})")
                else:
                    lines.append(f"@returns({code}) {desc}")

        if self.error_schemas:
            err_str = ", ".join(e.to_doclean(lean=lean) for e in self.error_schemas)
            lines.append(f"@errors {{{err_str}}}")
        elif self.errors:
            if lean:
                err_str = ", ".join(self.errors.keys())
            else:
                err_str = ", ".join(f"{code}: {msg}" for code, msg in self.errors.items())
            lines.append(f"@errors {{{err_str}}}")

        if self.example_request and not lean:
            lines.append(f"@example_request {self.example_request}")

        return "\n".join(lines)


def _group_name(path: str) -> str:
    """Extract meaningful group name from endpoint path, skipping version prefixes."""
    parts = [p for p in path.strip('/').split('/') if p]
    if not parts:
        return 'root'
    i = 0
    while i < len(parts) and re.match(r'^v\d+$', parts[i]):
        i += 1
    return parts[i] if i < len(parts) else parts[0]


@dataclass
class DocLeanSpec:
    """A complete DocLean document for an API."""
    api_name: str
    base_url: str = ""
    version: str = ""
    auth_scheme: str = ""
    endpoints: list = field(default_factory=list)
    common_fields: list = field(default_factory=list)

    def to_doclean(self, lean: bool = False) -> str:
        lines = [f"@doclean {DOCLEAN_VERSION}"]
        # Self-describing preamble so WebFetch summarizers pass content through faithfully
        lines.append("# Machine-readable API spec. Each @endpoint block is one API call.")
        lines.append(f"@api {self.api_name}")
        if self.base_url:
            lines.append(f"@base {self.base_url}")
        if self.version:
            lines.append(f"@version {self.version}")
        if self.auth_scheme:
            lines.append(f"@auth {self.auth_scheme}")

        # Common fields -- params that repeat across nearly all endpoints
        if self.common_fields:
            fields = ", ".join(p.to_doclean(lean=lean) for p in self.common_fields)
            lines.append(f"@common_fields {{{fields}}}")

        # Completeness header: endpoint count
        lines.append(f"@endpoints {len(self.endpoints)}")

        # Download hint for large specs
        if len(self.endpoints) > 20:
            lines.append("@hint download_for_search")

        # Grouped table of contents
        if self.endpoints:
            groups = OrderedDict()
            for ep in self.endpoints:
                gname = _group_name(ep.path)
                if gname not in groups:
                    groups[gname] = 0
                groups[gname] += 1
            toc_entries = [f"{name}({count})" for name, count in groups.items()]
            lines.append(f"@toc {', '.join(toc_entries)}")

        # Emit @type blocks for reused types (set by protobuf compiler)
        type_defs = getattr(self, '_type_defs', {})
        if type_defs:
            lines.append("")
            for name, fields_str in type_defs.items():
                lines.append(f"@type {name} {{{fields_str}}}")

        lines.append("")

        # Emit endpoints with @group markers, preserving original order
        distinct_groups = OrderedDict()
        for ep in self.endpoints:
            distinct_groups[_group_name(ep.path)] = True
        use_groups = len(distinct_groups) > 1

        current_group = None
        for ep in self.endpoints:
            gname = _group_name(ep.path)
            if use_groups and gname != current_group:
                if current_group is not None:
                    lines.append(f"@endgroup")
                    lines.append("")
                lines.append(f"@group {gname}")
                current_group = gname
            lines.append(ep.to_doclean(lean=lean))
            lines.append("")
        if use_groups and current_group is not None:
            lines.append(f"@endgroup")
            lines.append("")

        # Explicit end marker
        lines.append("@end")
        lines.append("")

        return "\n".join(lines)

    def to_original_text(self) -> str:
        """Generate verbose human-readable version for comparison."""
        lines = [f"# {self.api_name} API Documentation\n"]
        if self.base_url:
            lines.append(f"Base URL: {self.base_url}\n")
        if self.version:
            lines.append(f"Version: {self.version}\n")
        if self.auth_scheme:
            lines.append(f"## Authentication\n\n{self.auth_scheme}\n")

        for ep in self.endpoints:
            lines.append(f"## {ep.method.upper()} {ep.path}\n")
            if ep.summary:
                lines.append(f"{ep.summary}\n")
            if ep.required_params or ep.request_body:
                lines.append("### Required Parameters\n")
                for p in ep.required_params + [x for x in ep.request_body if x.required]:
                    desc = f" - {p.description}" if p.description else ""
                    lines.append(f"- **{p.name}** ({p.type}): {desc}")
                    if p.enum:
                        lines.append(f"  Possible values: {', '.join(str(e) for e in p.enum)}")
                lines.append("")
            opt = ep.optional_params + [x for x in ep.request_body if not x.required]
            if opt:
                lines.append("### Optional Parameters\n")
                for p in opt:
                    desc = f" - {p.description}" if p.description else ""
                    lines.append(f"- **{p.name}** ({p.type}): {desc}")
                lines.append("")

        return "\n".join(lines)
