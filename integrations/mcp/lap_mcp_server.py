"""
MCP (Model Context Protocol) server for LAP specs.

Serves LAP endpoints as MCP tools, demonstrating how LAP complements
MCP rather than competing with it. LAP compresses the documentation that
MCP tools expose.

Example usage (with MCP SDK):
    >>> import asyncio
    >>> from integrations.mcp.lap_mcp_server import LAPMCPServer
    >>> server = LAPMCPServer("examples/lap/openapi/")
    >>> asyncio.run(server.run())

Standalone (without MCP SDK):
    >>> server = LAPMCPServer()
    >>> server.load_spec("examples/lap/openapi/petstore.lap")
    >>> tools = server.list_tools()
    >>> print(tools[0])
    {'name': 'github_get_repos_owner_repo', 'description': '...', 'inputSchema': {...}}
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Optional

_src = str(Path(__file__).resolve().parent.parent.parent / "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

from core.formats.lap import LAPSpec, Endpoint, Param
from core.parser import parse_lap
from core.utils import read_file_safe

# Type map for MCP input schemas (JSON Schema)
_TYPE_MAP = {
    "str": "string",
    "int": "integer",
    "num": "number",
    "bool": "boolean",
    "map": "object",
    "any": "string",
}


def _type_to_json_schema(type_str: str) -> dict[str, Any]:
    """Convert LAP type to JSON Schema for MCP input."""
    if type_str.startswith("[") and type_str.endswith("]"):
        return {"type": "array", "items": _type_to_json_schema(type_str[1:-1])}
    m = re.match(r"^(\w+)\(([^)]+)\)$", type_str)
    if m:
        schema = _type_to_json_schema(m.group(1))
        schema["format"] = m.group(2)
        return schema
    return {"type": _TYPE_MAP.get(type_str, "string")}


def _endpoint_to_tool_name(endpoint: Endpoint, api_prefix: str = "") -> str:
    """Generate MCP tool name from endpoint."""
    clean = endpoint.path.strip("/")
    clean = re.sub(r"\{(\w+)\}", r"\1", clean)
    clean = re.sub(r"[^a-zA-Z0-9/]", "_", clean)
    parts = [p for p in clean.split("/") if p]
    name = endpoint.method.lower() + "_" + "_".join(parts)
    if api_prefix:
        name = api_prefix.lower().replace(" ", "_") + "_" + name
    return re.sub(r"_+", "_", name).strip("_")


def endpoint_to_mcp_tool(endpoint: Endpoint, api_name: str = "") -> dict[str, Any]:
    """Convert a LAP endpoint to an MCP tool definition.

    Returns a dict matching the MCP Tool schema:
    {name, description, inputSchema: {type: 'object', properties: {...}, required: [...]}}
    """
    all_params = endpoint.required_params + endpoint.optional_params + endpoint.request_body
    properties = {}
    required = []

    for param in all_params:
        prop = _type_to_json_schema(param.type)
        if param.description:
            prop["description"] = param.description
        if param.enum:
            prop["enum"] = param.enum
        if param.default is not None:
            prop["default"] = param.default
        properties[param.name] = prop
        if param.required:
            required.append(param.name)

    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
    }
    if required:
        input_schema["required"] = required

    return {
        "name": _endpoint_to_tool_name(endpoint, api_name),
        "description": endpoint.summary or f"{endpoint.method.upper()} {endpoint.path}",
        "inputSchema": input_schema,
    }


class LAPMCPServer:
    """MCP server that exposes LAP API specs as MCP tools.

    Each endpoint in loaded specs becomes an MCP tool with typed parameters.
    This demonstrates LAP complementing MCP: LAP provides the compressed
    documentation format, MCP provides the tool-serving protocol.
    """

    def __init__(self, specs_dir: str = None):
        self._specs: dict[str, LAPSpec] = {}
        self._tools: list[dict[str, Any]] = []
        self._tool_map: dict[str, tuple[LAPSpec, Endpoint]] = {}
        if specs_dir:
            self._load_dir(specs_dir)

    def _load_dir(self, specs_dir: str) -> None:
        for f in Path(specs_dir).glob("*.lap"):
            self.load_spec(str(f))

    def load_spec(self, path: str) -> None:
        """Load a LAP spec file and register its endpoints as tools."""
        text = read_file_safe(path)
        if not text:
            return
        spec = parse_lap(text)
        self.add_spec(spec)

    def add_spec(self, spec: LAPSpec) -> None:
        """Register a parsed LAPSpec."""
        key = spec.api_name.lower().replace(" ", "-")
        self._specs[key] = spec
        for ep in spec.endpoints:
            tool = endpoint_to_mcp_tool(ep, spec.api_name)
            self._tools.append(tool)
            self._tool_map[tool["name"]] = (spec, ep)

    def list_tools(self) -> list[dict[str, Any]]:
        """Return all registered MCP tools."""
        return self._tools

    def call_tool(self, name: str, arguments: dict = None) -> dict[str, Any]:
        """Handle an MCP tool call.

        In a real implementation, this would make the actual API call.
        Here we return the LAP documentation for the endpoint,
        showing what the agent would need to make the call.
        """
        if name not in self._tool_map:
            return {
                "isError": True,
                "content": [{"type": "text", "text": f"Unknown tool: {name}"}],
            }

        spec, endpoint = self._tool_map[name]
        doc = endpoint.to_lap()
        info = {
            "api": spec.api_name,
            "base_url": spec.base_url,
            "endpoint": doc,
            "arguments_received": arguments or {},
        }
        return {
            "content": [{"type": "text", "text": json.dumps(info, indent=2)}],
        }

    def to_mcp_manifest(self) -> dict[str, Any]:
        """Generate a complete MCP server manifest."""
        return {
            "name": "lap-lap-server",
            "version": "0.1.0",
            "description": "Serves API documentation via LAP compressed format",
            "tools": self._tools,
        }

    async def run(self, transport: str = "stdio") -> None:
        """Run as an MCP server (requires mcp SDK).

        This is a reference implementation. In production, you'd use
        the official MCP Python SDK's server framework.
        """
        try:
            from mcp.server import Server
            from mcp.server.stdio import stdio_server
        except ImportError:
            print("MCP SDK not installed. Install with: pip install mcp")
            print("\nServer manifest:")
            print(json.dumps(self.to_mcp_manifest(), indent=2))
            return

        server = Server("lap-lap")

        @server.list_tools()
        async def handle_list_tools():
            return self._tools

        @server.call_tool()
        async def handle_call_tool(name: str, arguments: dict):
            return self.call_tool(name, arguments)

        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream)
