#!/usr/bin/env python3
"""
LAP Parser — LAP text → structured Python objects

The reverse of the compiler: proves LAP is a true protocol
by enabling round-trip: source → LAP → structured data.
"""

import re
import warnings

from core.formats.lap_tools import LAPToolSpec, LAPToolBundle, ToolParam, ToolOutput, ToolExample


class ParseError(Exception):
    """Raised when LAP parsing encounters invalid syntax."""
    def __init__(self, message: str, line_number: int = 0):
        self.line_number = line_number
        super().__init__(f"Line {line_number}: {message}" if line_number else message)


def _parse_param_line(text: str) -> ToolParam:
    """Parse '@in name:type? description' into a ToolParam."""
    # Match name:type with optional ? and optional (enum) and optional =default
    m = re.match(r'^([\w.-]+):(\w[\w()/]*)(\?)?\s*(.*)', text)
    if not m:
        warnings.warn(f"Malformed @in: '{text[:50]}'")
        return ToolParam(name=text.split(":")[0] if ":" in text else text, type="any")

    name = m.group(1)
    type_str = m.group(2)
    required = m.group(3) is None
    rest = m.group(4).strip()

    # Extract enum from type like str(a/b/c)
    enum = []
    enum_m = re.match(r'^(\w+)\(([^)]+)\)$', type_str)
    if enum_m and '/' in enum_m.group(2):
        type_str = enum_m.group(1)
        enum = [v.strip() for v in enum_m.group(2).split('/')]

    # Extract default from =value at start of rest
    default = None
    if rest.startswith("="):
        eq_end = rest.find(" ")
        if eq_end == -1:
            default = rest[1:]
            rest = ""
        else:
            default = rest[1:eq_end]
            rest = rest[eq_end + 1:].strip()

    return ToolParam(
        name=name, type=type_str, required=required,
        description=rest, enum=enum, default=default,
    )


def _parse_output_line(text: str) -> ToolOutput:
    """Parse '@out name:type description' into a ToolOutput."""
    m = re.match(r'^([\w.-]+):(\w[\w()/]*)(?:\{([^}]*)\})?\s*(.*)', text)
    if not m:
        warnings.warn(f"Malformed @out: '{text[:50]}'")
        return ToolOutput(name=text.split(":")[0] if ":" in text else text, type="any")

    name = m.group(1)
    type_str = m.group(2)
    children_str = m.group(3)
    desc = m.group(4).strip()

    children = []
    if children_str:
        for part in children_str.split(","):
            part = part.strip()
            if part:
                children.append(_parse_output_line(part))

    return ToolOutput(name=name, type=type_str, description=desc, children=children)


def parse_lap_tools(text: str) -> LAPToolBundle:
    """Parse LAP text into a LAPToolBundle (one or more tools).
    
    Returns a bundle even for single tools, for consistency.
    """
    tools = []
    current = None
    current_example = None
    bundle_name = ""
    bundle_desc = ""

    lines = text.split("\n")
    for i, raw in enumerate(lines, 1):
        line = raw.strip()

        if not line:
            if current_example and current:
                current.examples.append(current_example)
                current_example = None
            continue

        # Bundle-level comments
        if line.startswith("# ") and current is None and not tools:
            if not bundle_name:
                bundle_name = line[2:].strip()
            else:
                bundle_desc = line[2:].strip()
            continue

        # Example continuation lines
        if current_example is not None:
            if line.startswith("> "):
                current_example.input_text = line[2:].strip()
                continue
            elif line.startswith("< "):
                current_example.output_text = line[2:].strip()
                continue
            else:
                current.examples.append(current_example)
                current_example = None

        if line.startswith("@lap "):
            continue  # version header

        elif line.startswith("@tool "):
            if current:
                tools.append(current)
            current = LAPToolSpec(name=line[6:].strip())

        elif line.startswith("@desc ") and current:
            current.description = line[6:].strip()

        elif line.startswith("@auth ") and current:
            current.auth = line[6:].strip()

        elif line.startswith("@tags ") and current:
            current.tags = [t.strip() for t in line[6:].split(",") if t.strip()]

        elif line.startswith("@source ") and current:
            current.source = line[8:].strip()

        elif line.startswith("@requires ") and current:
            current.requires.append(line[10:].strip())

        elif line.startswith("@in ") and current:
            current.inputs.append(_parse_param_line(line[4:].strip()))

        elif line.startswith("@out ") and current:
            current.outputs.append(_parse_output_line(line[5:].strip()))

        elif line.startswith("@example") and current:
            desc = line[8:].strip()
            current_example = ToolExample(description=desc)

    # Flush
    if current_example and current:
        current.examples.append(current_example)
    if current:
        tools.append(current)

    return LAPToolBundle(name=bundle_name, description=bundle_desc, tools=tools)


def parse_single_tool(text: str) -> LAPToolSpec:
    """Parse LAP text expected to contain a single tool."""
    bundle = parse_lap_tools(text)
    if not bundle.tools:
        raise ParseError("No @tool found in input")
    return bundle.tools[0]
