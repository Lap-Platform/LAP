#!/usr/bin/env python3
"""Baseline benchmark: compare LAP compression against simple alternatives."""

import copy
import json
import statistics
import sys
from pathlib import Path

import tiktoken
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.compilers.openapi import compile_openapi

SPEC_DIR = Path(__file__).parent.parent / "examples" / "verbose" / "openapi"
OUT_DIR = Path(__file__).parent / "results"
STRIP_KEYS = {"description", "summary", "example", "examples", "x-codeSamples"}


def count_tokens(text: str, enc) -> int:
    return len(enc.encode(text))


def strip_fields(obj):
    """Recursively strip description/summary/example fields."""
    if isinstance(obj, dict):
        return {k: strip_fields(v) for k, v in obj.items() if k not in STRIP_KEYS}
    if isinstance(obj, list):
        return [strip_fields(i) for i in obj]
    return obj


def main():
    enc = tiktoken.get_encoding("o200k_base")
    specs = sorted(SPEC_DIR.glob("*.yaml"))
    results = []

    for path in specs:
        name = path.stem
        raw_yaml = path.read_text()
        try:
            data = yaml.safe_load(raw_yaml)
        except Exception as e:
            print(f"⚠ Skipping {name}: YAML parse error: {e}")
            continue

        # Raw YAML tokens
        tok_raw = count_tokens(raw_yaml, enc)

        # JSON Minified
        json_min = json.dumps(data, separators=(",", ":"), default=str)
        tok_json = count_tokens(json_min, enc)

        # YAML No-Desc
        stripped = strip_fields(copy.deepcopy(data))
        yaml_nodesc = yaml.dump(stripped, default_flow_style=True, width=99999)
        tok_nodesc = count_tokens(yaml_nodesc, enc)

        # LAP
        try:
            lap_spec = compile_openapi(str(path))
        except Exception as e:
            print(f"⚠ Skipping {name}: compile error: {e}")
            continue

        lap_standard = lap_spec.to_lap(lean=False)
        lap_lean = lap_spec.to_lap(lean=True)
        tok_std = count_tokens(lap_standard, enc)
        tok_lean = count_tokens(lap_lean, enc)

        row = {
            "spec": name,
            "raw_yaml": tok_raw,
            "json_min": tok_json,
            "yaml_nodesc": tok_nodesc,
            "lap_standard": tok_std,
            "lap_lean": tok_lean,
        }
        results.append(row)
        print(f"✓ {name}: raw={tok_raw} json={tok_json} nodesc={tok_nodesc} std={tok_std} lean={tok_lean}")

    if not results:
        print("No results!")
        return

    # Compute ratios (lean / baseline)
    ratios = {"vs_raw": [], "vs_json": [], "vs_nodesc": []}
    for r in results:
        ratios["vs_raw"].append(r["lap_lean"] / r["raw_yaml"])
        ratios["vs_json"].append(r["lap_lean"] / r["json_min"])
        ratios["vs_nodesc"].append(r["lap_lean"] / r["yaml_nodesc"])

    summary = {}
    for key, vals in ratios.items():
        summary[key] = {
            "mean": round(statistics.mean(vals), 4),
            "median": round(statistics.median(vals), 4),
        }

    # Write JSON
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    json_out = {"results": results, "summary": summary}
    (OUT_DIR / "baseline_comparison.json").write_text(json.dumps(json_out, indent=2))

    # Write Markdown
    lines = ["# Baseline Comparison: LAP vs Simple Alternatives", ""]
    lines.append("| Spec | Raw YAML | JSON Min | YAML No-Desc | LAP Std | LAP Lean | Lean/Raw |")
    lines.append("|------|----------|----------|--------------|---------|----------|----------|")
    for r in results:
        ratio = r["lap_lean"] / r["raw_yaml"]
        lines.append(
            f"| {r['spec']} | {r['raw_yaml']:,} | {r['json_min']:,} | {r['yaml_nodesc']:,} "
            f"| {r['lap_standard']:,} | {r['lap_lean']:,} | {ratio:.1%} |"
        )

    lines += [
        "", "## Summary (LAP Lean ratio — lower is better)", "",
        "| Baseline | Mean | Median |",
        "|----------|------|--------|",
    ]
    for key, s in summary.items():
        lines.append(f"| {key} | {s['mean']:.1%} | {s['median']:.1%} |")
    lines.append("")

    (OUT_DIR / "baseline_comparison.md").write_text("\n".join(lines))
    print(f"\n✅ Results written to {OUT_DIR}/")


if __name__ == "__main__":
    main()
