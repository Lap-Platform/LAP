#!/usr/bin/env python3
"""Comprehensive median vs mean benchmark across all 5 LAP formats."""
import sys, os, json, glob, statistics, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

import tiktoken
enc = tiktoken.get_encoding("o200k_base")

def count_tokens(text):
    return len(enc.encode(text))

from core.compilers.openapi import compile_openapi
from core.compilers.graphql import compile_graphql
from core.compilers.asyncapi import compile_asyncapi
from core.compilers.protobuf import compile_protobuf
from core.compilers.postman import compile_postman

def process_spec(name, raw_text, compile_fn, filepath):
    try:
        print(f"  {name}...", end=" ", flush=True)
        result = compile_fn(filepath)
        std = result.to_doclean()
        lean = result.to_doclean(lean=True)
        raw_tok = count_tokens(raw_text)
        std_tok = count_tokens(std)
        lean_tok = count_tokens(lean)
        r = {
            "name": name,
            "raw_tokens": raw_tok,
            "standard_tokens": std_tok,
            "lean_tokens": lean_tok,
            "std_ratio": round(std_tok / raw_tok, 4) if raw_tok else 0,
            "lean_ratio": round(lean_tok / raw_tok, 4) if raw_tok else 0,
        }
        print(f"raw={raw_tok} std={std_tok} lean={lean_tok}", flush=True)
        return r
    except Exception as e:
        print(f"SKIP: {e}", flush=True)
        return None

results = {}

# OpenAPI
print("=== OpenAPI ===")
specs = []
for f in sorted(glob.glob("examples/verbose/openapi/*.yaml")):
    if "jira.yaml" in f:
        continue
    name = Path(f).stem
    raw = open(f).read()
    r = process_spec(name, raw, compile_openapi, f)
    if r:
        specs.append(r)
results["openapi"] = specs

# GraphQL
print("\n=== GraphQL ===")
specs = []
for f in sorted(glob.glob("examples/verbose/graphql/*.graphql")):
    name = Path(f).stem
    raw = open(f).read()
    r = process_spec(name, raw, compile_graphql, f)
    if r:
        specs.append(r)

results["graphql"] = specs

# AsyncAPI
print("\n=== AsyncAPI ===")
specs = []
for f in sorted(glob.glob("examples/verbose/asyncapi/*.yaml")):
    name = Path(f).stem
    raw = open(f).read()
    r = process_spec(name, raw, compile_asyncapi, f)
    if r:
        specs.append(r)

results["asyncapi"] = specs

# Protobuf
print("\n=== Protobuf ===")
specs = []
for f in sorted(glob.glob("examples/verbose/protobuf/*.proto")):
    name = Path(f).stem
    raw = open(f).read()
    r = process_spec(name, raw, compile_protobuf, f)
    if r:
        specs.append(r)

results["protobuf"] = specs

# Postman
print("\n=== Postman ===")
specs = []
for f in sorted(glob.glob("examples/verbose/postman/*.json")):
    name = Path(f).stem
    raw = open(f).read()
    r = process_spec(name, raw, compile_postman, f)
    if r:
        specs.append(r)

results["postman"] = specs

# Aggregates
def percentile(data, p):
    s = sorted(data)
    k = (len(s) - 1) * p / 100
    f = int(k)
    c = f + 1
    if c >= len(s):
        return s[f]
    return s[f] + (k - f) * (s[c] - s[f])

aggregates = {}
for fmt, specs in results.items():
    if not specs:
        continue
    std_ratios = [s["std_ratio"] for s in specs]
    lean_ratios = [s["lean_ratio"] for s in specs]
    aggregates[fmt] = {
        "count": len(specs),
        "std_compression": {
            "median": round(statistics.median(std_ratios), 4),
            "mean": round(statistics.mean(std_ratios), 4),
            "min": round(min(std_ratios), 4),
            "max": round(max(std_ratios), 4),
            "p25": round(percentile(std_ratios, 25), 4),
            "p75": round(percentile(std_ratios, 75), 4),
        },
        "lean_compression": {
            "median": round(statistics.median(lean_ratios), 4),
            "mean": round(statistics.mean(lean_ratios), 4),
            "min": round(min(lean_ratios), 4),
            "max": round(max(lean_ratios), 4),
            "p25": round(percentile(lean_ratios, 25), 4),
            "p75": round(percentile(lean_ratios, 75), 4),
        },
    }

output = {"per_spec": results, "aggregates": aggregates}
outdir = Path(__file__).parent / "results"
outdir.mkdir(exist_ok=True)

with open(outdir / "median_benchmark.json", "w") as f:
    json.dump(output, f, indent=2)

# Generate markdown
md = ["# LAP Benchmark: Median vs Mean Compression Ratios\n"]
md.append(f"*Generated: 2026-02-08 | Tokenizer: tiktoken o200k_base*\n")
md.append("## Summary\n")
md.append("Compression ratio = DocLean tokens / Raw tokens (lower = better compression)\n")

# Summary table - Standard
md.append("### Standard DocLean Compression\n")
md.append("| Format | Specs | Median | Mean | Min | Max | P25 | P75 |")
md.append("|--------|-------|--------|------|-----|-----|-----|-----|")
for fmt in ["openapi", "graphql", "asyncapi", "protobuf", "postman"]:
    if fmt not in aggregates:
        continue
    a = aggregates[fmt]
    s = a["std_compression"]
    md.append(f"| {fmt} | {a['count']} | {s['median']:.4f} | {s['mean']:.4f} | {s['min']:.4f} | {s['max']:.4f} | {s['p25']:.4f} | {s['p75']:.4f} |")

md.append("\n### Lean DocLean Compression\n")
md.append("| Format | Specs | Median | Mean | Min | Max | P25 | P75 |")
md.append("|--------|-------|--------|------|-----|-----|-----|-----|")
for fmt in ["openapi", "graphql", "asyncapi", "protobuf", "postman"]:
    if fmt not in aggregates:
        continue
    a = aggregates[fmt]
    s = a["lean_compression"]
    md.append(f"| {fmt} | {a['count']} | {s['median']:.4f} | {s['mean']:.4f} | {s['min']:.4f} | {s['max']:.4f} | {s['p25']:.4f} | {s['p75']:.4f} |")

# Per-format details
for fmt in ["openapi", "graphql", "asyncapi", "protobuf", "postman"]:
    if fmt not in results or not results[fmt]:
        continue
    md.append(f"\n## {fmt.upper()} — Per-Spec Details\n")
    md.append("| Spec | Raw Tokens | Std Tokens | Lean Tokens | Std Ratio | Lean Ratio |")
    md.append("|------|-----------|------------|-------------|-----------|------------|")
    for s in sorted(results[fmt], key=lambda x: x["lean_ratio"]):
        md.append(f"| {s['name']} | {s['raw_tokens']:,} | {s['standard_tokens']:,} | {s['lean_tokens']:,} | {s['std_ratio']:.4f} | {s['lean_ratio']:.4f} |")

# Insights
md.append("\n## Key Insights\n")
all_std = []
all_lean = []
for fmt, specs in results.items():
    for s in specs:
        all_std.append(s["std_ratio"])
        all_lean.append(s["lean_ratio"])

if all_std:
    md.append(f"- **Total specs benchmarked:** {len(all_std)}")
    md.append(f"- **Overall standard compression:** median={statistics.median(all_std):.4f}, mean={statistics.mean(all_std):.4f}")
    md.append(f"- **Overall lean compression:** median={statistics.median(all_lean):.4f}, mean={statistics.mean(all_lean):.4f}")
    md.append(f"- **Lean vs Standard improvement:** {(1 - statistics.median(all_lean)/statistics.median(all_std))*100:.1f}% additional reduction at median")
    
    # Best/worst by format
    best_fmt = min(aggregates, key=lambda f: aggregates[f]["lean_compression"]["median"])
    worst_fmt = max(aggregates, key=lambda f: aggregates[f]["lean_compression"]["median"])
    md.append(f"- **Best compressing format (lean median):** {best_fmt} ({aggregates[best_fmt]['lean_compression']['median']:.4f})")
    md.append(f"- **Least compressing format (lean median):** {worst_fmt} ({aggregates[worst_fmt]['lean_compression']['median']:.4f})")
    md.append(f"- **Median vs Mean gap:** Mean is typically {'higher' if statistics.mean(all_std) > statistics.median(all_std) else 'lower'} than median, suggesting {'right-skewed (some large specs compress less)' if statistics.mean(all_std) > statistics.median(all_std) else 'left-skewed'} distribution")

with open(outdir / "median_benchmark.md", "w") as f:
    f.write("\n".join(md) + "\n")

print(f"\nDone! {len(all_std)} specs benchmarked.")
print(f"Results saved to benchmarks/results/")
