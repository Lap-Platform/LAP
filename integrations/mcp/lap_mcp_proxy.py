#!/usr/bin/env python3
"""
LAP MCP Proxy — Transparent LAP compression for MCP tool discovery.

Sits between MCP server and LLM host:
1. Intercepts tools/list response → compiles to LAP (saves ~35-50% tokens)
2. LLM sees compact LAP format instead of verbose JSON Schema
3. For tools/call, reconstructs JSON Schema params (transparent to server)
"""

import json
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.compilers.lap_tools import compile_mcp_manifest, compile_mcp_tool
from core.formats.lap_tools import LAPToolSpec, LAPToolBundle

# ── Type reverse mapping ────────────────────────────────────────────

_LEAN_TO_JSON = {
    "str": "string",
    "int": "integer",
    "num": "number",
    "float": "number",
    "bool": "boolean",
    "map": "object",
    "obj": "object",
    "list": "array",
    "any": "string",
}


def _reverse_type(lean_type: str) -> dict:
    """Convert LAP type back to JSON Schema."""
    # Handle list types like [str]
    if lean_type.startswith("[") and lean_type.endswith("]"):
        inner = lean_type[1:-1]
        return {"type": "array", "items": {"type": _LEAN_TO_JSON.get(inner, inner)}}
    return {"type": _LEAN_TO_JSON.get(lean_type, lean_type)}


def spec_to_json_schema(spec: LAPToolSpec) -> dict:
    """Reconstruct MCP tool JSON from a LAPToolSpec."""
    properties = {}
    required = []
    for p in spec.inputs:
        prop = _reverse_type(p.type)
        if p.description:
            prop["description"] = p.description
        if p.enum:
            prop["enum"] = p.enum
        if p.default is not None:
            prop["default"] = p.default
        properties[p.name] = prop
        if p.required:
            required.append(p.name)
    
    schema = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    
    return {
        "name": spec.name,
        "description": spec.description,
        "inputSchema": schema,
    }


def bundle_to_manifest(bundle: LAPToolBundle) -> dict:
    """Reconstruct full MCP manifest from a LAPToolBundle."""
    return {
        "name": bundle.name,
        "description": bundle.description,
        "tools": [spec_to_json_schema(t) for t in bundle.tools],
    }


class LapMcpProxy:
    """Proxy that compresses MCP tool discovery via LAP."""
    
    def __init__(self):
        self._bundles: dict[str, LAPToolBundle] = {}  # server_name -> bundle
    
    def compress_tools_list(self, manifest: dict) -> str:
        """Compress a tools/list response to LAP format."""
        bundle = compile_mcp_manifest(manifest)
        self._bundles[bundle.name] = bundle
        return bundle.to_lap()
    
    def reconstruct_manifest(self, server_name: str) -> Optional[dict]:
        """Reconstruct JSON Schema manifest from stored LAP."""
        bundle = self._bundles.get(server_name)
        if not bundle:
            return None
        return bundle_to_manifest(bundle)
    
    def get_tool_schema(self, server_name: str, tool_name: str) -> Optional[dict]:
        """Get a single tool's JSON Schema (for tools/call validation)."""
        bundle = self._bundles.get(server_name)
        if not bundle:
            return None
        for tool in bundle.tools:
            if tool.name == tool_name:
                return spec_to_json_schema(tool)
        return None


def measure_fidelity(original: dict, reconstructed: dict) -> dict:
    """Measure round-trip fidelity between original and reconstructed manifests."""
    orig_tools = {t["name"]: t for t in original.get("tools", [])}
    recon_tools = {t["name"]: t for t in reconstructed.get("tools", [])}
    
    results = {"tools_matched": 0, "tools_total": len(orig_tools), "param_issues": []}
    
    for name, orig in orig_tools.items():
        if name not in recon_tools:
            results["param_issues"].append(f"Missing tool: {name}")
            continue
        results["tools_matched"] += 1
        recon = recon_tools[name]
        
        # Check params
        orig_props = orig.get("inputSchema", {}).get("properties", {})
        recon_props = recon.get("inputSchema", {}).get("properties", {})
        
        for pname in orig_props:
            if pname not in recon_props:
                results["param_issues"].append(f"{name}.{pname}: missing")
            else:
                orig_type = orig_props[pname].get("type")
                recon_type = recon_props[pname].get("type")
                if orig_type != recon_type:
                    results["param_issues"].append(f"{name}.{pname}: type {orig_type} → {recon_type}")
        
        # Check required
        orig_req = set(orig.get("inputSchema", {}).get("required", []))
        recon_req = set(recon.get("inputSchema", {}).get("required", []))
        if orig_req != recon_req:
            results["param_issues"].append(f"{name}: required mismatch {orig_req} vs {recon_req}")
    
    results["fidelity"] = results["tools_matched"] / results["tools_total"] if results["tools_total"] else 1.0
    return results


# ── CLI demo ────────────────────────────────────────────────────────

if __name__ == "__main__":
    import tiktoken
    enc = tiktoken.get_encoding("cl100k_base")
    
    FIXTURES = Path(__file__).parent / "test_fixtures"
    proxy = LapMcpProxy()
    
    print("LAP MCP Proxy — Round-trip Fidelity Test")
    print("=" * 60)
    
    for f in sorted(FIXTURES.glob("*.json")):
        data = json.loads(f.read_text())
        if not data.get("tools"):
            continue
        
        # Compress
        lap = proxy.compress_tools_list(data)
        
        # Reconstruct
        reconstructed = proxy.reconstruct_manifest(data.get("name", f.stem))
        
        # Measure fidelity
        fidelity = measure_fidelity(data, reconstructed)
        
        status = "✓" if not fidelity["param_issues"] else "⚠"
        print(f"\n{status} {f.stem}: {fidelity['tools_matched']}/{fidelity['tools_total']} tools, fidelity={fidelity['fidelity']:.0%}")
        if fidelity["param_issues"]:
            for issue in fidelity["param_issues"][:5]:
                print(f"    {issue}")
