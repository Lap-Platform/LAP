#!/usr/bin/env python3
"""Phase 2: Measure REAL token savings from LAP vs JSON Schema manifests."""

import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import tiktoken
from lap.core.compilers.lap_tools import compile_mcp_manifest

enc = tiktoken.get_encoding("cl100k_base")

def count_tokens(text: str) -> int:
    return len(enc.encode(text))

FIXTURES = Path(__file__).parent / "test_fixtures"
results = []

for f in sorted(FIXTURES.glob("*.json")):
    data = json.loads(f.read_text())
    tools = data.get("tools", [])
    if not tools:
        continue
    
    # Baseline: full JSON manifest as would be sent to LLM
    json_text = json.dumps(data, indent=2)
    json_tokens = count_tokens(json_text)
    
    # Compact JSON (no indent) - what some hosts do
    json_compact = json.dumps(data)
    json_compact_tokens = count_tokens(json_compact)
    
    # LAP format
    bundle = compile_mcp_manifest(data)
    lap_text = bundle.to_lap(lean=False)
    lap_tokens = count_tokens(lap_text)
    
    # Lean mode (no descriptions)
    lap_lean = bundle.to_lap(lean=True)
    lap_lean_tokens = count_tokens(lap_lean)
    
    results.append({
        "name": f.stem,
        "num_tools": len(tools),
        "json_pretty": json_tokens,
        "json_compact": json_compact_tokens,
        "lap": lap_tokens,
        "lap_lean": lap_lean_tokens,
        "lap_text": lap_text,
        "json_text": json_text,
    })
    
    savings_vs_pretty = (1 - lap_tokens / json_tokens) * 100
    savings_vs_compact = (1 - lap_tokens / json_compact_tokens) * 100
    
    print(f"\n{'='*60}")
    print(f"Server: {f.stem} ({len(tools)} tools)")
    print(f"  JSON pretty:    {json_tokens:>5} tokens")
    print(f"  JSON compact:   {json_compact_tokens:>5} tokens")
    print(f"  LAP:       {lap_tokens:>5} tokens ({savings_vs_pretty:.1f}% vs pretty, {savings_vs_compact:.1f}% vs compact)")
    print(f"  LAP lean:  {lap_lean_tokens:>5} tokens")

# Aggregates
print(f"\n{'='*60}")
print("AGGREGATE RESULTS")
print(f"{'='*60}")
total_pretty = sum(r["json_pretty"] for r in results)
total_compact = sum(r["json_compact"] for r in results)
total_lap = sum(r["lap"] for r in results)
total_lean = sum(r["lap_lean"] for r in results)

print(f"Total JSON (pretty):   {total_pretty:>6} tokens")
print(f"Total JSON (compact):  {total_compact:>6} tokens")
print(f"Total LAP:        {total_lap:>6} tokens  ({(1-total_lap/total_pretty)*100:.1f}% savings vs pretty)")
print(f"Total LAP lean:   {total_lean:>6} tokens  ({(1-total_lean/total_pretty)*100:.1f}% savings vs pretty)")
print(f"\nSavings vs compact JSON: {(1-total_lap/total_compact)*100:.1f}%")

# Show one example before/after
print(f"\n{'='*60}")
print("EXAMPLE: github server")
print(f"{'='*60}")
gh = next(r for r in results if r["name"] == "github")
print("\n--- LAP output ---")
print(gh["lap_text"][:2000])

# Save data for results doc
with open(Path(__file__).parent / "phase2_data.json", "w") as f:
    json.dump([{k:v for k,v in r.items() if k not in ("lap_text","json_text")} for r in results], f, indent=2)

# Also save one full before/after for the results doc
with open(Path(__file__).parent / "phase2_example_before.json", "w") as f:
    # Just first 2 tools from github
    gh_data = json.loads((FIXTURES / "github.json").read_text())
    gh_data["tools"] = gh_data["tools"][:2]
    json.dump(gh_data, f, indent=2)

with open(Path(__file__).parent / "phase2_example_after.txt", "w") as f:
    gh_bundle = compile_mcp_manifest(json.loads((FIXTURES / "github.json").read_text()))
    gh_bundle.tools = gh_bundle.tools[:2]
    f.write(gh_bundle.to_lap())
