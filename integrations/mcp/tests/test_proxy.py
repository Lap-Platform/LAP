#!/usr/bin/env python3
"""
Phase 2 MCP Proxy Tests — End-to-end validation of LAP MCP proxy.

Tests:
1. Round-trip fidelity for all 7 server manifests
2. MCP protocol simulation (tools/list, tools/call)
3. Token benchmarks (tiktoken cl100k_base)
4. Edge cases (empty tools, no params, nested schemas, unicode, etc.)
"""

import json
import sys
from pathlib import Path

import pytest
import tiktoken

# Ensure project root on path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from integrations.mcp.lap_mcp_proxy import (
    LapMcpProxy,
    spec_to_json_schema,
    bundle_to_manifest,
    measure_fidelity,
    _reverse_type,
)
from lap.core.compilers.lap_tools import compile_mcp_manifest, compile_mcp_tool
from lap.core.formats.lap_tools import LAPToolSpec, LAPToolBundle, ToolParam

FIXTURES = Path(__file__).resolve().parent.parent / "test_fixtures"
FIXTURE_FILES = sorted(FIXTURES.glob("*.json"))
ENC = tiktoken.get_encoding("cl100k_base")


# ── Helpers ──────────────────────────────────────────────────────────

def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def all_fixtures():
    return [(f.stem, json.loads(f.read_text())) for f in FIXTURE_FILES]


# ═══════════════════════════════════════════════════════════════════
# 1. Round-Trip Fidelity
# ═══════════════════════════════════════════════════════════════════

class TestRoundTripFidelity:
    """Verify JSON → LAP → JSON preserves all tool metadata."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.proxy = LapMcpProxy()

    @pytest.mark.parametrize("name,manifest", all_fixtures(), ids=[f.stem for f in FIXTURE_FILES])
    def test_all_tool_names_preserved(self, name, manifest):
        self.proxy.compress_tools_list(manifest)
        recon = self.proxy.reconstruct_manifest(manifest.get("name", name))
        orig_names = {t["name"] for t in manifest.get("tools", [])}
        recon_names = {t["name"] for t in recon.get("tools", [])}
        assert orig_names == recon_names, f"Tool name mismatch: missing={orig_names - recon_names}, extra={recon_names - orig_names}"

    @pytest.mark.parametrize("name,manifest", all_fixtures(), ids=[f.stem for f in FIXTURE_FILES])
    def test_all_param_names_preserved(self, name, manifest):
        self.proxy.compress_tools_list(manifest)
        recon = self.proxy.reconstruct_manifest(manifest.get("name", name))
        recon_tools = {t["name"]: t for t in recon.get("tools", [])}
        for tool in manifest.get("tools", []):
            rt = recon_tools.get(tool["name"])
            assert rt is not None
            orig_params = set(tool.get("inputSchema", {}).get("properties", {}).keys())
            recon_params = set(rt.get("inputSchema", {}).get("properties", {}).keys())
            assert orig_params == recon_params, f"{tool['name']}: param mismatch"

    @pytest.mark.parametrize("name,manifest", all_fixtures(), ids=[f.stem for f in FIXTURE_FILES])
    def test_param_types_preserved(self, name, manifest):
        self.proxy.compress_tools_list(manifest)
        recon = self.proxy.reconstruct_manifest(manifest.get("name", name))
        recon_tools = {t["name"]: t for t in recon.get("tools", [])}
        for tool in manifest.get("tools", []):
            rt = recon_tools[tool["name"]]
            orig_props = tool.get("inputSchema", {}).get("properties", {})
            recon_props = rt.get("inputSchema", {}).get("properties", {})
            for pname, pschema in orig_props.items():
                orig_type = pschema.get("type")
                recon_type = recon_props[pname].get("type")
                assert orig_type == recon_type, f"{tool['name']}.{pname}: {orig_type} → {recon_type}"

    @pytest.mark.parametrize("name,manifest", all_fixtures(), ids=[f.stem for f in FIXTURE_FILES])
    def test_required_flags_preserved(self, name, manifest):
        self.proxy.compress_tools_list(manifest)
        recon = self.proxy.reconstruct_manifest(manifest.get("name", name))
        recon_tools = {t["name"]: t for t in recon.get("tools", [])}
        for tool in manifest.get("tools", []):
            rt = recon_tools[tool["name"]]
            orig_req = set(tool.get("inputSchema", {}).get("required", []))
            recon_req = set(rt.get("inputSchema", {}).get("required", []))
            assert orig_req == recon_req, f"{tool['name']}: required {orig_req} → {recon_req}"

    @pytest.mark.parametrize("name,manifest", all_fixtures(), ids=[f.stem for f in FIXTURE_FILES])
    def test_descriptions_preserved(self, name, manifest):
        self.proxy.compress_tools_list(manifest)
        recon = self.proxy.reconstruct_manifest(manifest.get("name", name))
        recon_tools = {t["name"]: t for t in recon.get("tools", [])}
        for tool in manifest.get("tools", []):
            rt = recon_tools[tool["name"]]
            # Tool description preserved
            assert rt["description"] == tool["description"]
            # Param descriptions preserved
            orig_props = tool.get("inputSchema", {}).get("properties", {})
            recon_props = rt.get("inputSchema", {}).get("properties", {})
            for pname, pschema in orig_props.items():
                orig_desc = pschema.get("description", "")
                recon_desc = recon_props[pname].get("description", "")
                assert orig_desc == recon_desc, f"{tool['name']}.{pname} desc mismatch"

    @pytest.mark.parametrize("name,manifest", all_fixtures(), ids=[f.stem for f in FIXTURE_FILES])
    def test_enum_values_preserved(self, name, manifest):
        self.proxy.compress_tools_list(manifest)
        recon = self.proxy.reconstruct_manifest(manifest.get("name", name))
        recon_tools = {t["name"]: t for t in recon.get("tools", [])}
        for tool in manifest.get("tools", []):
            rt = recon_tools[tool["name"]]
            orig_props = tool.get("inputSchema", {}).get("properties", {})
            recon_props = rt.get("inputSchema", {}).get("properties", {})
            for pname, pschema in orig_props.items():
                if "enum" in pschema:
                    assert recon_props[pname].get("enum") == pschema["enum"], \
                        f"{tool['name']}.{pname} enum mismatch"

    @pytest.mark.parametrize("name,manifest", all_fixtures(), ids=[f.stem for f in FIXTURE_FILES])
    def test_defaults_preserved(self, name, manifest):
        self.proxy.compress_tools_list(manifest)
        recon = self.proxy.reconstruct_manifest(manifest.get("name", name))
        recon_tools = {t["name"]: t for t in recon.get("tools", [])}
        for tool in manifest.get("tools", []):
            rt = recon_tools[tool["name"]]
            orig_props = tool.get("inputSchema", {}).get("properties", {})
            recon_props = rt.get("inputSchema", {}).get("properties", {})
            for pname, pschema in orig_props.items():
                if "default" in pschema:
                    # Default is stringified during round-trip
                    assert "default" in recon_props[pname], \
                        f"{tool['name']}.{pname} missing default"

    @pytest.mark.parametrize("name,manifest", all_fixtures(), ids=[f.stem for f in FIXTURE_FILES])
    def test_fidelity_measure(self, name, manifest):
        self.proxy.compress_tools_list(manifest)
        recon = self.proxy.reconstruct_manifest(manifest.get("name", name))
        result = measure_fidelity(manifest, recon)
        assert result["fidelity"] == 1.0, f"Fidelity {result['fidelity']}: {result['param_issues']}"


# ═══════════════════════════════════════════════════════════════════
# 2. MCP Protocol Simulation
# ═══════════════════════════════════════════════════════════════════

class TestMCPProtocol:
    """Simulate real MCP message flow through the proxy."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.proxy = LapMcpProxy()
        self.github = load_fixture("github.json")

    def test_tools_list_compress(self):
        """tools/list → proxy compresses → LAP output is valid."""
        lap = self.proxy.compress_tools_list(self.github)
        assert "@tool" in lap
        assert "create_or_update_file" in lap

    def test_tools_list_then_reconstruct(self):
        """After compress, can reconstruct full manifest."""
        self.proxy.compress_tools_list(self.github)
        recon = self.proxy.reconstruct_manifest("github")
        assert recon is not None
        assert len(recon["tools"]) == len(self.github["tools"])

    def test_get_tool_schema(self):
        """Can retrieve individual tool schema for tools/call."""
        self.proxy.compress_tools_list(self.github)
        schema = self.proxy.get_tool_schema("github", "create_or_update_file")
        assert schema is not None
        assert schema["name"] == "create_or_update_file"
        assert "owner" in schema["inputSchema"]["properties"]

    def test_tools_call_param_reconstruction(self):
        """tools/call: proxy reconstructs JSON Schema params correctly."""
        self.proxy.compress_tools_list(self.github)
        schema = self.proxy.get_tool_schema("github", "create_or_update_file")
        props = schema["inputSchema"]["properties"]
        # Verify types match for the server
        assert props["owner"]["type"] == "string"
        assert props["repo"]["type"] == "string"
        assert "owner" in schema["inputSchema"]["required"]

    def test_tools_call_various_types(self):
        """Test parameter type round-trip for various JSON Schema types."""
        manifest = {
            "name": "test_types",
            "description": "Type test",
            "tools": [{
                "name": "multi_type_tool",
                "description": "Tests various types",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "s": {"type": "string", "description": "a string"},
                        "i": {"type": "integer", "description": "an int"},
                        "n": {"type": "number", "description": "a number"},
                        "b": {"type": "boolean", "description": "a bool"},
                        "a": {"type": "array", "items": {"type": "string"}, "description": "string array"},
                        "e": {"type": "string", "enum": ["x", "y", "z"], "description": "an enum"},
                    },
                    "required": ["s", "i", "b"]
                }
            }]
        }
        self.proxy.compress_tools_list(manifest)
        schema = self.proxy.get_tool_schema("test_types", "multi_type_tool")
        props = schema["inputSchema"]["properties"]
        assert props["s"]["type"] == "string"
        assert props["i"]["type"] == "integer"
        assert props["n"]["type"] == "number"
        assert props["b"]["type"] == "boolean"
        assert props["a"]["type"] == "array"
        assert props["a"]["items"]["type"] == "string"
        assert props["e"]["enum"] == ["x", "y", "z"]
        assert set(schema["inputSchema"]["required"]) == {"s", "i", "b"}

    def test_unknown_server_returns_none(self):
        assert self.proxy.reconstruct_manifest("nonexistent") is None
        assert self.proxy.get_tool_schema("nonexistent", "tool") is None

    def test_unknown_tool_returns_none(self):
        self.proxy.compress_tools_list(self.github)
        assert self.proxy.get_tool_schema("github", "nonexistent_tool") is None


# ═══════════════════════════════════════════════════════════════════
# 3. Token Benchmarks
# ═══════════════════════════════════════════════════════════════════

class TestTokenBenchmarks:
    """Measure token savings with tiktoken cl100k_base."""

    @pytest.mark.parametrize("name,manifest", all_fixtures(), ids=[f.stem for f in FIXTURE_FILES])
    def test_lap_saves_tokens_vs_pretty(self, name, manifest):
        pretty = json.dumps(manifest, indent=2)
        bundle = compile_mcp_manifest(manifest)
        lap = bundle.to_lap()
        pretty_tokens = len(ENC.encode(pretty))
        lap_tokens = len(ENC.encode(lap))
        # LAP should use fewer tokens than pretty JSON
        assert lap_tokens < pretty_tokens, f"LAP ({lap_tokens}) >= pretty ({pretty_tokens})"

    @pytest.mark.parametrize("name,manifest", all_fixtures(), ids=[f.stem for f in FIXTURE_FILES])
    def test_lap_saves_tokens_vs_compact(self, name, manifest):
        compact = json.dumps(manifest, separators=(",", ":"))
        bundle = compile_mcp_manifest(manifest)
        lap = bundle.to_lap()
        compact_tokens = len(ENC.encode(compact))
        lap_tokens = len(ENC.encode(lap))
        # LAP should use fewer tokens than compact JSON
        assert lap_tokens < compact_tokens, f"LAP ({lap_tokens}) >= compact ({compact_tokens})"

    @pytest.mark.parametrize("name,manifest", all_fixtures(), ids=[f.stem for f in FIXTURE_FILES])
    def test_lean_saves_more_than_regular(self, name, manifest):
        bundle = compile_mcp_manifest(manifest)
        lap = bundle.to_lap(lean=False)
        lean = bundle.to_lap(lean=True)
        lap_tokens = len(ENC.encode(lap))
        lean_tokens = len(ENC.encode(lean))
        assert lean_tokens <= lap_tokens


# ═══════════════════════════════════════════════════════════════════
# 4. Edge Cases
# ═══════════════════════════════════════════════════════════════════

class TestEdgeCases:

    @pytest.fixture(autouse=True)
    def setup(self):
        self.proxy = LapMcpProxy()

    def test_empty_tool_list(self):
        manifest = {"name": "empty", "description": "No tools", "tools": []}
        lap = self.proxy.compress_tools_list(manifest)
        recon = self.proxy.reconstruct_manifest("empty")
        assert recon["tools"] == []

    def test_tool_no_parameters(self):
        manifest = {
            "name": "noparam",
            "description": "test",
            "tools": [{
                "name": "ping",
                "description": "Ping the server",
                "inputSchema": {"type": "object", "properties": {}}
            }]
        }
        self.proxy.compress_tools_list(manifest)
        recon = self.proxy.reconstruct_manifest("noparam")
        assert len(recon["tools"]) == 1
        assert recon["tools"][0]["inputSchema"]["properties"] == {}

    def test_deeply_nested_object(self):
        """Tool with nested object params — note: LAP flattens to 'map' type."""
        manifest = {
            "name": "nested",
            "description": "test",
            "tools": [{
                "name": "deep_tool",
                "description": "Has nested objects",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "config": {
                            "type": "object",
                            "description": "A config object",
                            "properties": {
                                "inner": {"type": "string"}
                            }
                        }
                    },
                    "required": ["config"]
                }
            }]
        }
        self.proxy.compress_tools_list(manifest)
        schema = self.proxy.get_tool_schema("nested", "deep_tool")
        assert schema is not None
        # LAP maps object → map → object round-trip
        assert schema["inputSchema"]["properties"]["config"]["type"] == "object"

    def test_array_of_objects(self):
        manifest = {
            "name": "arrobj",
            "description": "test",
            "tools": [{
                "name": "bulk",
                "description": "Bulk op",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "items": {
                            "type": "array",
                            "description": "List of items",
                            "items": {"type": "object"}
                        }
                    }
                }
            }]
        }
        self.proxy.compress_tools_list(manifest)
        schema = self.proxy.get_tool_schema("arrobj", "bulk")
        props = schema["inputSchema"]["properties"]
        assert props["items"]["type"] == "array"

    def test_very_long_description(self):
        long_desc = "A" * 5000
        manifest = {
            "name": "longdesc",
            "description": "test",
            "tools": [{
                "name": "verbose",
                "description": long_desc,
                "inputSchema": {"type": "object", "properties": {}}
            }]
        }
        self.proxy.compress_tools_list(manifest)
        schema = self.proxy.get_tool_schema("longdesc", "verbose")
        assert schema["description"] == long_desc

    def test_unicode_descriptions(self):
        manifest = {
            "name": "unicode",
            "description": "Ünïcödé server 🚀",
            "tools": [{
                "name": "café_tool",
                "description": "Outil pour gérer les données 日本語テスト",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "名前": {"type": "string", "description": "名前を入力 🎉"}
                    },
                    "required": ["名前"]
                }
            }]
        }
        self.proxy.compress_tools_list(manifest)
        schema = self.proxy.get_tool_schema("unicode", "café_tool")
        assert schema is not None
        assert "名前" in schema["inputSchema"]["properties"]
        assert schema["inputSchema"]["properties"]["名前"]["description"] == "名前を入力 🎉"
        assert "名前" in schema["inputSchema"]["required"]

    def test_default_values_roundtrip(self):
        manifest = {
            "name": "defaults",
            "description": "test",
            "tools": [{
                "name": "with_defaults",
                "description": "Tool with defaults",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "page": {"type": "integer", "default": 1, "description": "Page number"},
                        "size": {"type": "integer", "default": 10, "description": "Page size"},
                    }
                }
            }]
        }
        self.proxy.compress_tools_list(manifest)
        schema = self.proxy.get_tool_schema("defaults", "with_defaults")
        assert "default" in schema["inputSchema"]["properties"]["page"]
        assert "default" in schema["inputSchema"]["properties"]["size"]

    def test_reverse_type_mapping(self):
        assert _reverse_type("str") == {"type": "string"}
        assert _reverse_type("int") == {"type": "integer"}
        assert _reverse_type("num") == {"type": "number"}
        assert _reverse_type("bool") == {"type": "boolean"}
        assert _reverse_type("map") == {"type": "object"}
        assert _reverse_type("[str]") == {"type": "array", "items": {"type": "string"}}
        assert _reverse_type("[int]") == {"type": "array", "items": {"type": "integer"}}


# ═══════════════════════════════════════════════════════════════════
# 5. Benchmark Data Collection (for results report)
# ═══════════════════════════════════════════════════════════════════

def collect_benchmark_data():
    """Collect all benchmark data for the results report. Not a test — called by report generator."""
    rows = []
    proxy = LapMcpProxy()
    for f in FIXTURE_FILES:
        manifest = json.loads(f.read_text())
        pretty = json.dumps(manifest, indent=2)
        compact = json.dumps(manifest, separators=(",", ":"))
        bundle = compile_mcp_manifest(manifest)
        lap = bundle.to_lap()
        lean = bundle.to_lap(lean=True)

        pt = len(ENC.encode(pretty))
        ct = len(ENC.encode(compact))
        lt = len(ENC.encode(lap))
        lnt = len(ENC.encode(lean))

        # Round-trip fidelity
        proxy.compress_tools_list(manifest)
        recon = proxy.reconstruct_manifest(manifest.get("name", f.stem))
        fidelity = measure_fidelity(manifest, recon)

        rows.append({
            "server": f.stem,
            "tools": len(manifest.get("tools", [])),
            "pretty_tokens": pt,
            "compact_tokens": ct,
            "lap_tokens": lt,
            "lean_tokens": lnt,
            "save_vs_pretty": f"{(1 - lt/pt)*100:.1f}%",
            "save_vs_compact": f"{(1 - lt/ct)*100:.1f}%",
            "lean_save_vs_pretty": f"{(1 - lnt/pt)*100:.1f}%",
            "fidelity": "✅" if fidelity["fidelity"] == 1.0 and not fidelity["param_issues"] else "⚠️",
            "issues": fidelity["param_issues"],
        })
    return rows


if __name__ == "__main__":
    # Generate report
    rows = collect_benchmark_data()
    for r in rows:
        print(f"{r['server']:15s} tools={r['tools']:2d}  pretty={r['pretty_tokens']:5d}  compact={r['compact_tokens']:5d}  "
              f"lap={r['lap_tokens']:5d}  lean={r['lean_tokens']:5d}  "
              f"save_pretty={r['save_vs_pretty']:6s}  save_compact={r['save_vs_compact']:6s}  fidelity={r['fidelity']}")
