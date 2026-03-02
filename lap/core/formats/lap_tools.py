"""
LAP Format Spec & Serializer

LAP is a compressed, structured representation of AI tool/skill manifests
optimized for LLM agent discovery and invocation. Part of the LAP protocol.

Supports: MCP servers, OpenClaw/ClawHub skills, Claude skills, generic agent tools.
"""

from dataclasses import dataclass, field
from typing import Optional

LAP_TOOL_VERSION = "v0.1"


def _enum_str(v) -> str:
    """Convert enum value to string, fixing YAML boolean corruption."""
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v)


@dataclass
class ToolParam:
    """An input parameter for a tool."""
    name: str
    type: str
    required: bool = True
    description: str = ""
    enum: list = field(default_factory=list)
    default: Optional[str] = None

    def to_lap(self, lean: bool = False) -> str:
        opt = "" if self.required else "?"
        parts = [f"{self.name}:{self.type}{opt}"]
        if self.enum:
            parts[0] += f"({'/'.join(_enum_str(e) for e in self.enum)})"
        if self.default is not None:
            parts[0] += f"={self.default}"
        if self.description and not lean:
            parts.append(self.description)
        return " ".join(parts)


@dataclass
class ToolOutput:
    """An output field from a tool."""
    name: str
    type: str
    description: str = ""
    children: list = field(default_factory=list)

    def to_lap(self, lean: bool = False, depth: int = 0) -> str:
        if self.children:
            child_str = ", ".join(c.to_lap(lean=lean, depth=depth + 1) for c in self.children)
            base = f"{self.name}:{self.type}{{{child_str}}}"
        else:
            base = f"{self.name}:{self.type}"
        if self.description and not lean:
            return f"{base} {self.description}"
        return base


@dataclass
class ToolExample:
    """A usage example for a tool."""
    input_text: str = ""
    output_text: str = ""
    description: str = ""

    def to_lap(self, lean: bool = False) -> str:
        lines = ["@example"]
        if self.description and not lean:
            lines[0] += f" {self.description}"
        if self.input_text:
            lines.append(f"  > {self.input_text}")
        if self.output_text:
            lines.append(f"  < {self.output_text}")
        return "\n".join(lines)


@dataclass
class LAPToolSpec:
    """A complete LAP document for a tool or skill."""
    name: str
    description: str = ""
    auth: str = "none"  # none/apikey/oauth/token
    tags: list = field(default_factory=list)
    inputs: list = field(default_factory=list)
    outputs: list = field(default_factory=list)
    examples: list = field(default_factory=list)
    requires: list = field(default_factory=list)
    source: str = ""

    def to_lap(self, lean: bool = False) -> str:
        lines = [f"@lap {LAP_TOOL_VERSION}"]
        lines.append(f"@tool {self.name}")
        if self.description:
            lines.append(f"@desc {self.description}")
        if self.auth and self.auth != "none":
            lines.append(f"@auth {self.auth}")
        if self.tags:
            lines.append(f"@tags {','.join(self.tags)}")
        if self.source:
            lines.append(f"@source {self.source}")
        for dep in self.requires:
            lines.append(f"@requires {dep}")

        if self.inputs:
            for p in self.inputs:
                lines.append(f"@in {p.to_lap(lean=lean)}")

        if self.outputs:
            for o in self.outputs:
                lines.append(f"@out {o.to_lap(lean=lean)}")

        for ex in self.examples:
            lines.append(ex.to_lap(lean=lean))

        return "\n".join(lines)


@dataclass
class LAPToolBundle:
    """A bundle of multiple tools (e.g., from an MCP server)."""
    name: str = ""
    description: str = ""
    source: str = ""
    tools: list = field(default_factory=list)

    def to_lap(self, lean: bool = False) -> str:
        parts = []
        if self.name:
            parts.append(f"# {self.name}")
            if self.description and not lean:
                parts.append(f"# {self.description}")
            parts.append("")
        for tool in self.tools:
            parts.append(tool.to_lap(lean=lean))
            parts.append("")
        return "\n".join(parts)
