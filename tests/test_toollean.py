#!/usr/bin/env python3
"""Tests for LAP format, compiler, and parser."""

import sys
import os

import json
import pytest
from pathlib import Path

from core.formats.lap_tools import (
    ToolParam, ToolOutput, ToolExample, LAPToolSpec, LAPToolBundle, LAP_TOOL_VERSION,
)
from core.compilers.lap_tools import (
    compile_mcp_tool, compile_mcp_manifest, compile_skill_md,
    compile_generic_json, _map_type,
)
from core.compilers.lap_tools_parser import (
    parse_lap_tools, parse_single_tool, _parse_param_line, _parse_output_line, ParseError,
)


# ══════════════════════════════════════════════════════════════════════
# Format dataclass tests
# ══════════════════════════════════════════════════════════════════════

class TestToolParam:
    def test_basic(self):
        p = ToolParam(name="query", type="str")
        assert p.to_lap() == "query:str"

    def test_optional(self):
        p = ToolParam(name="limit", type="int", required=False)
        assert p.to_lap() == "limit:int?"

    def test_with_description(self):
        p = ToolParam(name="q", type="str", description="Search query")
        assert p.to_lap() == "q:str Search query"

    def test_lean_strips_description(self):
        p = ToolParam(name="q", type="str", description="Search query")
        assert p.to_lap(lean=True) == "q:str"

    def test_enum(self):
        p = ToolParam(name="mode", type="str", enum=["fast", "slow"])
        assert p.to_lap() == "mode:str(fast/slow)"

    def test_default(self):
        p = ToolParam(name="n", type="int", default="10")
        assert p.to_lap() == "n:int=10"

    def test_optional_enum_default_desc(self):
        p = ToolParam(name="fmt", type="str", required=False, enum=["json", "xml"], default="json", description="Output format")
        result = p.to_lap()
        assert "fmt:str?" in result
        assert "(json/xml)" in result
        assert "=json" in result
        assert "Output format" in result


class TestToolOutput:
    def test_basic(self):
        o = ToolOutput(name="result", type="str")
        assert o.to_lap() == "result:str"

    def test_with_description(self):
        o = ToolOutput(name="result", type="str", description="The result")
        assert o.to_lap() == "result:str The result"

    def test_nested_children(self):
        child = ToolOutput(name="id", type="int")
        o = ToolOutput(name="items", type="list", children=[child])
        assert o.to_lap() == "items:list{id:int}"

    def test_lean_strips_desc(self):
        o = ToolOutput(name="r", type="str", description="desc")
        assert o.to_lap(lean=True) == "r:str"


class TestToolExample:
    def test_full(self):
        ex = ToolExample(input_text="search cats", output_text="Found 5 results", description="Basic search")
        result = ex.to_lap()
        assert "@example Basic search" in result
        assert "> search cats" in result
        assert "< Found 5 results" in result

    def test_lean_strips_desc(self):
        ex = ToolExample(description="Test", input_text="hi")
        result = ex.to_lap(lean=True)
        assert "@example" in result
        assert "Test" not in result

    def test_input_only(self):
        ex = ToolExample(input_text="go")
        result = ex.to_lap()
        assert "> go" in result
        assert "<" not in result


class TestLAPToolSpec:
    def test_minimal(self):
        spec = LAPToolSpec(name="ping")
        result = spec.to_lap()
        assert f"@lap {LAP_TOOL_VERSION}" in result
        assert "@tool ping" in result

    def test_full(self):
        spec = LAPToolSpec(
            name="search",
            description="Search the web",
            auth="apikey",
            tags=["web", "search"],
            source="https://example.com",
            requires=["network"],
            inputs=[ToolParam(name="q", type="str")],
            outputs=[ToolOutput(name="results", type="list")],
            examples=[ToolExample(input_text="search cats")],
        )
        result = spec.to_lap()
        assert "@desc Search the web" in result
        assert "@auth apikey" in result
        assert "@tags web,search" in result
        assert "@source https://example.com" in result
        assert "@requires network" in result
        assert "@in q:str" in result
        assert "@out results:list" in result
        assert "@example" in result

    def test_auth_none_omitted(self):
        spec = LAPToolSpec(name="t", auth="none")
        assert "@auth" not in spec.to_lap()


class TestLAPToolBundle:
    def test_empty(self):
        b = LAPToolBundle(name="empty")
        result = b.to_lap()
        assert "# empty" in result

    def test_multiple_tools(self):
        b = LAPToolBundle(
            name="MyServer",
            description="A test server",
            tools=[LAPToolSpec(name="a"), LAPToolSpec(name="b")],
        )
        result = b.to_lap()
        assert "# MyServer" in result
        assert "# A test server" in result
        assert "@tool a" in result
        assert "@tool b" in result

    def test_lean_omits_bundle_desc(self):
        b = LAPToolBundle(name="S", description="Desc", tools=[LAPToolSpec(name="x")])
        result = b.to_lap(lean=True)
        assert "# S" in result
        assert "Desc" not in result


# ══════════════════════════════════════════════════════════════════════
# Type mapping tests
# ══════════════════════════════════════════════════════════════════════

class TestTypeMapping:
    @pytest.mark.parametrize("json_type,expected", [
        ("string", "str"), ("integer", "int"), ("number", "num"),
        ("boolean", "bool"), ("object", "map"), ("array", "list"), ("null", "null"),
    ])
    def test_basic_types(self, json_type, expected):
        assert _map_type(json_type) == expected

    def test_unknown_type_passthrough(self):
        assert _map_type("custom") == "custom"

    def test_format(self):
        assert _map_type("string", "date-time") == "str(date-time)"

    def test_array_with_items(self):
        assert _map_type("array", "", {"type": "string"}) == "[str]"

    def test_empty_type(self):
        assert _map_type("") == "any"


# ══════════════════════════════════════════════════════════════════════
# MCP Compiler tests
# ══════════════════════════════════════════════════════════════════════

MCP_TOOL_FIXTURE = {
    "name": "get_weather",
    "description": "Get current weather for a location",
    "inputSchema": {
        "type": "object",
        "required": ["location"],
        "properties": {
            "location": {"type": "string", "description": "City name"},
            "units": {"type": "string", "enum": ["celsius", "fahrenheit"], "default": "celsius"},
        },
    },
}

MCP_MANIFEST_FIXTURE = {
    "name": "WeatherServer",
    "description": "Weather data provider",
    "tools": [
        MCP_TOOL_FIXTURE,
        {
            "name": "get_forecast",
            "description": "Get 5-day forecast",
            "inputSchema": {
                "type": "object",
                "required": ["location"],
                "properties": {
                    "location": {"type": "string"},
                    "days": {"type": "integer", "default": "5"},
                },
            },
        },
    ],
}


class TestMCPCompiler:
    def test_single_tool(self):
        spec = compile_mcp_tool(MCP_TOOL_FIXTURE)
        assert spec.name == "get_weather"
        assert spec.description == "Get current weather for a location"
        assert len(spec.inputs) == 2
        loc = next(p for p in spec.inputs if p.name == "location")
        assert loc.required is True
        assert loc.type == "str"
        units = next(p for p in spec.inputs if p.name == "units")
        assert units.required is False
        assert units.enum == ["celsius", "fahrenheit"]
        assert units.default == "celsius"

    def test_manifest(self):
        bundle = compile_mcp_manifest(MCP_MANIFEST_FIXTURE)
        assert bundle.name == "WeatherServer"
        assert len(bundle.tools) == 2
        assert bundle.tools[0].name == "get_weather"
        assert bundle.tools[1].name == "get_forecast"

    def test_input_schema_alt_key(self):
        tool = {"name": "t", "input_schema": {"properties": {"x": {"type": "integer"}}, "required": ["x"]}}
        spec = compile_mcp_tool(tool)
        assert spec.inputs[0].name == "x"
        assert spec.inputs[0].type == "int"

    def test_empty_tool(self):
        spec = compile_mcp_tool({})
        assert spec.name == "unknown"
        assert spec.inputs == []

    def test_array_param(self):
        tool = {"name": "t", "inputSchema": {"properties": {"ids": {"type": "array", "items": {"type": "integer"}}}, "required": []}}
        spec = compile_mcp_tool(tool)
        assert spec.inputs[0].type == "[int]"


# ══════════════════════════════════════════════════════════════════════
# SKILL.md Compiler tests
# ══════════════════════════════════════════════════════════════════════

SKILL_MD_FIXTURE = """\
# Weather Skill

Get weather information for any city.

Tags: weather, api
Auth: API Key required

Requires: network access

## Parameters

- `location` (string): City name, required
- `units` (string): Temperature units, optional

## Examples

```
get_weather London
```
"""


class TestSkillMDCompiler:
    def test_basic(self):
        spec = compile_skill_md(SKILL_MD_FIXTURE)
        assert spec.name == "weather"
        assert "weather" in spec.description.lower() or "city" in spec.description.lower()
        assert spec.auth == "apikey"
        assert "weather" in spec.tags
        assert len(spec.inputs) == 2
        assert spec.inputs[0].name == "location"
        assert spec.inputs[0].type == "str"
        assert len(spec.examples) == 1

    def test_empty_skill(self):
        spec = compile_skill_md("")
        assert spec.name == "unknown"

    def test_oauth_auth(self):
        spec = compile_skill_md("# T\n\ndesc\n\nAuth: OAuth 2.0")
        assert spec.auth == "oauth"

    def test_token_auth(self):
        spec = compile_skill_md("# T\n\ndesc\n\nAuth: Bearer token")
        assert spec.auth == "token"

    def test_name_suffix_stripped(self):
        spec = compile_skill_md("# My Tool\n\ndesc")
        assert "tool" not in spec.name

    def test_source_preserved(self):
        spec = compile_skill_md("# T\n\ndesc", source="/path/to/SKILL.md")
        assert spec.source == "/path/to/SKILL.md"


# ══════════════════════════════════════════════════════════════════════
# Generic JSON Compiler tests
# ══════════════════════════════════════════════════════════════════════

class TestGenericJSONCompiler:
    def test_basic(self):
        tool = {
            "name": "search",
            "description": "Search things",
            "parameters": {
                "properties": {"q": {"type": "string", "description": "Query"}},
                "required": ["q"],
            },
            "returns": {"result": {"type": "string", "description": "The answer"}},
        }
        spec = compile_generic_json(tool)
        assert spec.name == "search"
        assert len(spec.inputs) == 1
        assert spec.inputs[0].name == "q"
        assert len(spec.outputs) == 1
        assert spec.outputs[0].name == "result"

    def test_list_params(self):
        tool = {
            "name": "t",
            "parameters": [
                {"name": "x", "type": "integer", "required": True},
                {"name": "y", "type": "string", "required": False},
            ],
        }
        spec = compile_generic_json(tool)
        assert len(spec.inputs) == 2
        assert spec.inputs[0].type == "int"
        assert spec.inputs[1].required is False

    def test_empty(self):
        spec = compile_generic_json({})
        assert spec.name == "unknown"

    def test_string_tags(self):
        spec = compile_generic_json({"name": "t", "tags": "web"})
        assert spec.tags == ["web"]

    def test_string_requires(self):
        spec = compile_generic_json({"name": "t", "requires": "network"})
        assert spec.requires == ["network"]

    def test_output_string_type(self):
        spec = compile_generic_json({"name": "t", "returns": {"data": "str"}})
        assert spec.outputs[0].type == "str"


# ══════════════════════════════════════════════════════════════════════
# Parser tests
# ══════════════════════════════════════════════════════════════════════

class TestParamParsing:
    def test_basic(self):
        p = _parse_param_line("query:str Search query")
        assert p.name == "query"
        assert p.type == "str"
        assert p.required is True
        assert p.description == "Search query"

    def test_optional(self):
        p = _parse_param_line("limit:int? Max results")
        assert p.required is False

    def test_enum(self):
        p = _parse_param_line("mode:str(fast/slow)")
        assert p.type == "str"
        assert p.enum == ["fast", "slow"]

    def test_default(self):
        p = _parse_param_line("n:int =10 count")
        assert p.default == "10"
        assert p.description == "count"

    def test_malformed(self):
        with pytest.warns(UserWarning):
            p = _parse_param_line("broken")
        assert p.name == "broken"


class TestOutputParsing:
    def test_basic(self):
        o = _parse_output_line("result:str The answer")
        assert o.name == "result"
        assert o.type == "str"
        assert o.description == "The answer"

    def test_nested(self):
        o = _parse_output_line("items:list{id:int, name:str}")
        assert len(o.children) == 2
        assert o.children[0].name == "id"

    def test_malformed(self):
        with pytest.warns(UserWarning):
            o = _parse_output_line("broken")


class TestParseLAP:
    def test_single_tool(self):
        text = "@lap v0.1\n@tool ping\n@desc Ping a host\n@in host:str Target host"
        bundle = parse_lap_tools(text)
        assert len(bundle.tools) == 1
        assert bundle.tools[0].name == "ping"
        assert bundle.tools[0].inputs[0].name == "host"

    def test_bundle(self):
        text = "# MyBundle\n# Description\n\n@lap v0.1\n@tool a\n@desc Tool A\n\n@lap v0.1\n@tool b\n@desc Tool B"
        bundle = parse_lap_tools(text)
        assert bundle.name == "MyBundle"
        assert bundle.description == "Description"
        assert len(bundle.tools) == 2

    def test_parse_single_tool(self):
        text = "@lap v0.1\n@tool test"
        spec = parse_single_tool(text)
        assert spec.name == "test"

    def test_parse_single_tool_empty(self):
        with pytest.raises(ParseError):
            parse_single_tool("")

    def test_auth_tags_source_requires(self):
        text = "@lap v0.1\n@tool t\n@auth apikey\n@tags web,api\n@source http://x\n@requires network"
        spec = parse_single_tool(text)
        assert spec.auth == "apikey"
        assert spec.tags == ["web", "api"]
        assert spec.source == "http://x"
        assert spec.requires == ["network"]

    def test_example_parsing(self):
        text = "@lap v0.1\n@tool t\n@example Basic\n  > input here\n  < output here"
        spec = parse_single_tool(text)
        assert len(spec.examples) == 1
        assert spec.examples[0].description == "Basic"
        assert spec.examples[0].input_text == "input here"
        assert spec.examples[0].output_text == "output here"


# ══════════════════════════════════════════════════════════════════════
# Round-trip tests (compile → render → parse → compare)
# ══════════════════════════════════════════════════════════════════════

class TestRoundTrip:
    def test_mcp_roundtrip(self):
        spec = compile_mcp_tool(MCP_TOOL_FIXTURE)
        rendered = spec.to_lap()
        parsed = parse_single_tool(rendered)
        assert parsed.name == spec.name
        assert parsed.description == spec.description
        assert len(parsed.inputs) == len(spec.inputs)
        for orig, back in zip(spec.inputs, parsed.inputs):
            assert orig.name == back.name
            assert orig.type == back.type
            assert orig.required == back.required

    def test_bundle_roundtrip(self):
        bundle = compile_mcp_manifest(MCP_MANIFEST_FIXTURE)
        rendered = bundle.to_lap()
        parsed = parse_lap_tools(rendered)
        assert parsed.name == bundle.name
        assert len(parsed.tools) == len(bundle.tools)
        for orig, back in zip(bundle.tools, parsed.tools):
            assert orig.name == back.name

    def test_generic_roundtrip(self):
        tool = {
            "name": "calc",
            "description": "Calculate expression",
            "auth": "none",
            "tags": ["math"],
            "parameters": {"properties": {"expr": {"type": "string"}}, "required": ["expr"]},
            "returns": {"result": {"type": "number"}},
        }
        spec = compile_generic_json(tool)
        rendered = spec.to_lap()
        parsed = parse_single_tool(rendered)
        assert parsed.name == "calc"
        assert parsed.tags == ["math"]
        assert len(parsed.inputs) == 1
        assert len(parsed.outputs) == 1

    def test_full_spec_roundtrip(self):
        spec = LAPToolSpec(
            name="advanced",
            description="An advanced tool",
            auth="oauth",
            tags=["test", "advanced"],
            source="https://example.com",
            requires=["auth-service"],
            inputs=[
                ToolParam(name="q", type="str", description="Query"),
                ToolParam(name="n", type="int", required=False, default="5"),
            ],
            outputs=[ToolOutput(name="data", type="list")],
            examples=[ToolExample(input_text="search x", output_text="found 3", description="Demo")],
        )
        rendered = spec.to_lap()
        parsed = parse_single_tool(rendered)
        assert parsed.name == spec.name
        assert parsed.description == spec.description
        assert parsed.auth == spec.auth
        assert parsed.tags == spec.tags
        assert parsed.source == spec.source
        assert parsed.requires == spec.requires
        assert len(parsed.inputs) == 2
        assert len(parsed.outputs) == 1
        assert len(parsed.examples) == 1
        assert parsed.examples[0].input_text == "search x"
        assert parsed.examples[0].output_text == "found 3"


# ══════════════════════════════════════════════════════════════════════
# Edge cases
# ══════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    def test_special_characters_in_description(self):
        spec = LAPToolSpec(name="t", description="Uses <html> & \"quotes\" = fun!")
        rendered = spec.to_lap()
        parsed = parse_single_tool(rendered)
        assert parsed.description == spec.description

    def test_empty_bundle(self):
        b = LAPToolBundle(name="empty", tools=[])
        rendered = b.to_lap()
        parsed = parse_lap_tools(rendered)
        assert len(parsed.tools) == 0

    def test_tool_no_inputs(self):
        spec = LAPToolSpec(name="noop")
        rendered = spec.to_lap()
        parsed = parse_single_tool(rendered)
        assert parsed.inputs == []

    def test_many_tools_in_bundle(self):
        tools = [LAPToolSpec(name=f"tool_{i}") for i in range(20)]
        b = LAPToolBundle(name="big", tools=tools)
        rendered = b.to_lap()
        parsed = parse_lap_tools(rendered)
        assert len(parsed.tools) == 20

    def test_missing_description(self):
        spec = compile_mcp_tool({"name": "bare"})
        assert spec.description == ""

    def test_param_with_dots_in_name(self):
        p = _parse_param_line("config.key:str A setting")
        assert p.name == "config.key"


# ══════════════════════════════════════════════════════════════════════
# Stats / token counting
# ══════════════════════════════════════════════════════════════════════

class TestStats:
    def test_lean_is_shorter(self):
        spec = LAPToolSpec(
            name="verbose",
            description="A tool with lots of descriptions",
            inputs=[
                ToolParam(name="a", type="str", description="First param with long description"),
                ToolParam(name="b", type="int", description="Second param with long description"),
            ],
            outputs=[ToolOutput(name="r", type="str", description="Result with description")],
            examples=[ToolExample(description="An example", input_text="test", output_text="ok")],
        )
        full = spec.to_lap(lean=False)
        lean = spec.to_lap(lean=True)
        assert len(lean) < len(full)

    def test_bundle_token_estimate(self):
        bundle = compile_mcp_manifest(MCP_MANIFEST_FIXTURE)
        full = bundle.to_lap(lean=False)
        lean = bundle.to_lap(lean=True)
        # Rough token estimate: chars / 4
        full_tokens = len(full) / 4
        lean_tokens = len(lean) / 4
        assert lean_tokens < full_tokens

    def test_mcp_vs_lap_size(self):
        """LAP should be more compact than raw JSON."""
        raw_json = json.dumps(MCP_MANIFEST_FIXTURE)
        bundle = compile_mcp_manifest(MCP_MANIFEST_FIXTURE)
        lap = bundle.to_lap()
        assert len(lap) < len(raw_json)
